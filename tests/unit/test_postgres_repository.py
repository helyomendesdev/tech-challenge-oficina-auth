from __future__ import annotations

from dataclasses import dataclass

import pytest

from oficina_auth.domain import DependencyUnavailable
from oficina_auth.domain.cpf import CPF
from oficina_auth.infrastructure.postgres_client_repository import (
    AUTH_DATABASE,
    LOOKUP_SQL,
    PostgresClientRepository,
    PostgresRepositoryConfig,
)
from oficina_auth.infrastructure.secrets_manager import DatabaseCredentials

VALID_CPF = "52998224725"


@dataclass
class FakeCredentialsProvider:
    credentials: DatabaseCredentials = DatabaseCredentials(
        username="oficina_auth",
        password="synthetic-password",
    )
    invalidated: int = 0

    def get_credentials(self) -> DatabaseCredentials:
        return self.credentials

    def invalidate(self) -> None:
        self.invalidated += 1


class FakeCursor:
    def __init__(self, row: tuple[object, object] | None = None) -> None:
        self.row = row
        self.executed: tuple[str, tuple[str, ...]] | None = None
        self.closed = False

    def execute(self, sql: str, params: tuple[str, ...]) -> None:
        self.executed = (sql, params)

    def fetchone(self) -> tuple[object, object] | None:
        return self.row

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.fake_cursor = cursor
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def close(self) -> None:
        self.closed = True


class ConnectionFactory:
    def __init__(self, row: tuple[object, object] | None = None, error: Exception | None = None):
        self.cursor = FakeCursor(row)
        self.connection = FakeConnection(self.cursor)
        self.error = error
        self.kwargs: dict[str, object] | None = None

    def __call__(self, **kwargs: object) -> FakeConnection:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.connection


def repository(
    factory: ConnectionFactory,
    credentials: FakeCredentialsProvider | None = None,
) -> tuple[PostgresClientRepository, FakeCredentialsProvider]:
    provider = credentials or FakeCredentialsProvider()
    config = PostgresRepositoryConfig(
        host="db.internal",
        port=5432,
        database=AUTH_DATABASE,
        secret_id="oficina-auth",
        connect_timeout_seconds=2.0,
    )
    return PostgresClientRepository(config, provider, factory), provider


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (None, None),
        ((42, False), ("42", False)),
        ((42, True), ("42", True)),
    ],
)
def test_lookup_returns_only_client_id_and_eligibility(
    row: tuple[object, object] | None,
    expected: tuple[str, bool] | None,
) -> None:
    factory = ConnectionFactory(row)
    repo, _ = repository(factory)

    result = repo.find_by_cpf(CPF(VALID_CPF))

    assert (
        result is None
        if expected is None
        else (result.cliente_id, result.can_authenticate) == expected
    )
    assert factory.connection.closed is True
    assert factory.cursor.closed is True


def test_lookup_is_parameterized_and_supports_normalized_and_legacy_cpf() -> None:
    factory = ConnectionFactory((42, True))
    repo, _ = repository(factory)

    repo.find_by_cpf(CPF("529.982.247-25"))

    assert factory.cursor.executed is not None
    sql, params = factory.cursor.executed
    assert sql == LOOKUP_SQL
    assert "529.982.247-25" not in sql
    assert "52998224725" not in sql
    assert params == (VALID_CPF, "529.982.247-25", VALID_CPF)
    assert "atendimento_cliente" in sql
    assert "SELECT id, ativo" in sql


def test_connection_receives_short_timeout_and_secret_credentials() -> None:
    factory = ConnectionFactory((42, True))
    repo, _ = repository(factory)

    repo.find_by_cpf(CPF(VALID_CPF))

    assert factory.kwargs == {
        "user": "oficina_auth",
        "password": "synthetic-password",
        "host": "db.internal",
        "port": 5432,
        "database": "oficina",
        "timeout": 2.0,
    }


def test_connection_refused_is_generic_and_closes_resources() -> None:
    sensitive = "52998224725 db.internal oficina_auth synthetic-password"
    factory = ConnectionFactory(error=ConnectionError(f"connection failed: {sensitive}"))
    repo, _ = repository(factory)

    with pytest.raises(DependencyUnavailable) as error:
        repo.find_by_cpf(CPF(VALID_CPF))

    assert str(error.value) == "Dependencia temporariamente indisponivel."
    assert sensitive not in str(error.value)


def test_authentication_failure_invalidates_cached_credentials() -> None:
    class AuthenticationFailure(Exception):
        sqlstate = "28P01"

    credentials = FakeCredentialsProvider()
    factory = ConnectionFactory(error=AuthenticationFailure("synthetic authentication failure"))
    repo, _ = repository(factory, credentials)

    with pytest.raises(DependencyUnavailable):
        repo.find_by_cpf(CPF(VALID_CPF))

    assert credentials.invalidated == 1


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        (
            {
                "DB_HOST": "db.internal",
                "DB_PORT": "5432",
                "POSTGRES_DB": "oficina",
                "DB_SECRET_ID": "oficina-auth",
            },
            ("db.internal", 5432, "oficina", "oficina-auth"),
        ),
        (
            {
                "DB_HOST": "db.internal",
                "DB_PORT": "5432",
                "POSTGRES_DB": "other",
                "DB_SECRET_ID": "oficina-auth",
            },
            None,
        ),
    ],
)
def test_production_database_configuration_requires_oficina(
    environment: dict[str, str], expected: tuple[str, int, str, str] | None
) -> None:
    if expected is None:
        with pytest.raises(DependencyUnavailable):
            PostgresRepositoryConfig.from_environment(environment)
        return

    config = PostgresRepositoryConfig.from_environment(environment)
    assert (config.host, config.port, config.database, config.secret_id) == expected


def test_configuration_does_not_use_direct_postgres_user_or_password() -> None:
    config = PostgresRepositoryConfig.from_environment(
        {
            "DB_HOST": "db.internal",
            "DB_PORT": "5432",
            "POSTGRES_DB": "oficina",
            "DB_SECRET_ID": "oficina-auth",
            "POSTGRES_USER": "must-not-be-read",
            "POSTGRES_PASSWORD": "must-not-be-read",
        }
    )

    assert not hasattr(config, "username")
    assert not hasattr(config, "password")

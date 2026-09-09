from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from oficina_auth.domain.client import ClientAuthRecord
from oficina_auth.domain.cpf import CPF
from oficina_auth.domain.exceptions import DependencyUnavailable
from oficina_auth.infrastructure.secrets_manager import (
    SecretsManagerDatabaseCredentialsProvider,
)

AUTH_DATABASE = "oficina"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 3.0
# `documento` (varchar 14, unique) stores the CPF with or without punctuation.
LOOKUP_SQL = """
SELECT id, ativo
FROM atendimento_cliente
WHERE documento = %s OR documento = %s
ORDER BY CASE WHEN documento = %s THEN 0 ELSE 1 END
LIMIT 1
""".strip()


@dataclass(frozen=True)
class PostgresRepositoryConfig:
    host: str
    port: int
    database: str
    secret_id: str
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> PostgresRepositoryConfig:
        host = _required(environment, "DB_HOST")
        secret_id = _required(environment, "DB_SECRET_ID")
        database = _required(environment, "POSTGRES_DB")
        if database != AUTH_DATABASE:
            raise DependencyUnavailable("Configuracao de autenticacao indisponivel.")

        try:
            port = int(_required(environment, "DB_PORT"))
        except (TypeError, ValueError):
            raise DependencyUnavailable("Configuracao de autenticacao indisponivel.") from None

        if not 1 <= port <= 65535:
            raise DependencyUnavailable("Configuracao de autenticacao indisponivel.")

        return cls(host=host, port=port, database=database, secret_id=secret_id)


ConnectionFactory = Callable[..., Any]


class PostgresClientRepository:
    def __init__(
        self,
        config: PostgresRepositoryConfig,
        credentials_provider: SecretsManagerDatabaseCredentialsProvider,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._config = config
        self._credentials_provider = credentials_provider
        self._connection_factory = connection_factory or _connect_with_pg8000

    def find_by_cpf(self, cpf: CPF) -> ClientAuthRecord | None:
        connection = None
        cursor = None
        try:
            credentials = self._credentials_provider.get_credentials()
            connection = self._connection_factory(
                user=credentials.username,
                password=credentials.password,
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                timeout=self._config.connect_timeout_seconds,
            )
            cursor = connection.cursor()
            formatted_cpf = _format_cpf(cpf)
            cursor.execute(LOOKUP_SQL, (cpf.digits, formatted_cpf, cpf.digits))
            row = cursor.fetchone()
            if row is None:
                return None

            cliente_id, can_authenticate = row
            if cliente_id is None:
                raise DependencyUnavailable("Dependencia temporariamente indisponivel.")
            return ClientAuthRecord(
                cliente_id=str(cliente_id),
                can_authenticate=bool(can_authenticate),
            )
        except DependencyUnavailable:
            raise
        except Exception as error:
            if _is_authentication_failure(error):
                self._credentials_provider.invalidate()
            raise DependencyUnavailable("Dependencia temporariamente indisponivel.") from None
        finally:
            _close_quietly(cursor)
            _close_quietly(connection)


def _connect_with_pg8000(**kwargs: Any) -> Any:
    from pg8000 import dbapi

    # RDS enforces rds.force_ssl=1; ssl_context=True enables TLS with default verification.
    return dbapi.connect(ssl_context=True, **kwargs)


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not isinstance(value, str) or not value.strip():
        raise DependencyUnavailable("Configuracao de autenticacao indisponivel.")
    return value


def _format_cpf(cpf: CPF) -> str:
    digits = cpf.digits
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def _is_authentication_failure(error: Exception) -> bool:
    sqlstate = getattr(error, "sqlstate", None)
    if sqlstate in {"28000", "28P01"}:
        return True
    error_name = type(error).__name__.lower()
    return "auth" in error_name or "password" in error_name


def _close_quietly(resource: Any) -> None:
    if resource is None:
        return
    try:
        resource.close()
    except Exception:
        return

from __future__ import annotations

from dataclasses import dataclass

import pytest

from oficina_auth.domain import DependencyUnavailable
from oficina_auth.infrastructure.secrets_manager import (
    SecretsManagerDatabaseCredentialsProvider,
    SecretsManagerPrivateKeyProvider,
)


@dataclass
class FakeClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value


class FakeSecretsManager:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[str] = []

    def get_secret_value(self, *, SecretId: str) -> object:
        self.calls.append(SecretId)
        if self.error is not None:
            raise self.error
        return self.response


def database_secret(password: str = "synthetic-password", username: str = "oficina_auth"):
    return {"SecretString": f'{{"username":"{username}","password":"{password}"}}'}


def test_database_credentials_are_validated_and_cached_until_ttl() -> None:
    clock = FakeClock()
    client = FakeSecretsManager(database_secret())
    provider = SecretsManagerDatabaseCredentialsProvider(
        client,
        "oficina-auth",
        cache_ttl_seconds=10,
        clock=clock.now,
    )

    first = provider.get_credentials()
    clock.value = 9
    second = provider.get_credentials()
    clock.value = 10
    third = provider.get_credentials()

    assert first.username == "oficina_auth"
    assert first.password == "synthetic-password"
    assert second is first
    assert third is not second
    assert client.calls == ["oficina-auth", "oficina-auth"]


def test_database_credentials_can_be_invalidated_for_rotation() -> None:
    client = FakeSecretsManager(database_secret())
    provider = SecretsManagerDatabaseCredentialsProvider(client, "oficina-auth")

    provider.get_credentials()
    provider.invalidate()
    provider.get_credentials()

    assert len(client.calls) == 2


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"SecretString": ""},
        {"SecretString": "not-json"},
        {"SecretString": "[]"},
        {"SecretString": '{"username":"oficina_auth"}'},
        {"SecretString": '{"username":"oficina_auth","password":""}'},
        database_secret(username="other_user"),
    ],
)
def test_malformed_database_secret_fails_without_details(response: object) -> None:
    client = FakeSecretsManager(response)
    provider = SecretsManagerDatabaseCredentialsProvider(client, "oficina-auth")

    with pytest.raises(DependencyUnavailable) as error:
        provider.get_credentials()

    assert str(error.value) == "Dependencia temporariamente indisponivel."
    assert "other_user" not in repr(error.value)


def test_secrets_manager_failure_does_not_expose_secret_or_error_details() -> None:
    sensitive = "synthetic-secret-value"
    client = FakeSecretsManager(error=RuntimeError(f"failed with {sensitive}"))
    provider = SecretsManagerDatabaseCredentialsProvider(client, "oficina-auth")

    with pytest.raises(DependencyUnavailable) as error:
        provider.get_credentials()

    assert sensitive not in str(error.value)
    assert "RuntimeError" not in repr(error.value)


def test_private_key_provider_uses_a_separate_secret_and_cache() -> None:
    clock = FakeClock()
    client = FakeSecretsManager({"SecretString": "synthetic-private-key"})
    provider = SecretsManagerPrivateKeyProvider(
        client,
        "oficina-auth-jwt-private-key",
        cache_ttl_seconds=10,
        clock=clock.now,
    )

    assert provider.get_private_key() == "synthetic-private-key"
    assert provider.get_private_key() == "synthetic-private-key"
    assert client.calls == ["oficina-auth-jwt-private-key"]


@pytest.mark.parametrize("response", [None, {}, {"SecretString": ""}])
def test_private_key_secret_must_be_a_non_empty_string(response: object) -> None:
    provider = SecretsManagerPrivateKeyProvider(
        FakeSecretsManager(response),
        "oficina-auth-jwt-private-key",
    )

    with pytest.raises(DependencyUnavailable) as error:
        provider.get_private_key()

    assert str(error.value) == "Dependencia temporariamente indisponivel."

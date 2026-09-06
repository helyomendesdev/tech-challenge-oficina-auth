from __future__ import annotations

import json
from typing import Any

import pytest

from oficina_auth.domain import AuthenticationRecord, DependencyUnavailable
from oficina_auth.handlers import auth as auth_module


class FakeSecretsClient:
    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
        return {"SecretString": '{"username":"oficina_auth","password":"synthetic"}'}


class FakeRepository:
    def __init__(self, config: Any, credentials_provider: Any) -> None:
        self.config = config
        self.credentials_provider = credentials_provider

    def find_by_cpf(self, cpf: Any) -> AuthenticationRecord:
        return AuthenticationRecord(cliente_id="42", can_authenticate=True)


class FakeIssuer:
    def __init__(self, private_key_provider: Any) -> None:
        self.private_key_provider = private_key_provider

    def issue(self, cliente_id: str) -> str:
        return "synthetic-token"


def event() -> dict[str, Any]:
    return {
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"cpf": "52998224725"}),
        "isBase64Encoded": False,
    }


def production_environment() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "DB_HOST": "db.internal",
        "DB_PORT": "5432",
        "POSTGRES_DB": "oficina",
        "DB_SECRET_ID": "oficina-auth",
        "JWT_PRIVATE_KEY_SECRET_ID": "oficina-auth-jwt-private-key",
    }


def test_production_factory_composes_real_adapters_without_memory_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module, "Boto3SecretsManagerClient", FakeSecretsClient)
    monkeypatch.setattr(auth_module, "PostgresClientRepository", FakeRepository)
    monkeypatch.setattr(auth_module, "Rs256TokenIssuer", FakeIssuer)

    handler = auth_module.create_handler_from_environment(production_environment())
    response = handler(event())

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["access_token"] == "synthetic-token"


def test_production_factory_rejects_shared_database_and_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module, "Boto3SecretsManagerClient", FakeSecretsClient)

    environment = production_environment()
    environment["JWT_PRIVATE_KEY_SECRET_ID"] = environment["DB_SECRET_ID"]

    with pytest.raises(DependencyUnavailable):
        auth_module.create_handler_from_environment(environment)

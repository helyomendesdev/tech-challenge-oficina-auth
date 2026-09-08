from __future__ import annotations

import argparse
import os
import re
from collections.abc import Mapping
from typing import Any

from oficina_auth.domain.cpf import CPF
from oficina_auth.infrastructure.secrets_manager import (
    Boto3SecretsManagerClient,
    SecretsManagerDatabaseCredentialsProvider,
)

DATABASE_NAME = "oficina"
EXPECTED_USERNAME = "oficina_auth"
SECRET_NAME = "oficina-auth"
CONFIRMATION_VALUE = "I_UNDERSTAND_REAL_RDS_SMOKE"
CONNECT_TIMEOUT_SECONDS = 3.0
INSUFFICIENT_PRIVILEGE_SQLSTATE = "42501"
LOOKUP_SQL = """
SELECT id, ativo
FROM atendimento_cliente
WHERE cpf = %s OR cpf = %s
ORDER BY CASE WHEN cpf = %s THEN 0 ELSE 1 END
LIMIT 1
""".strip()
TRACELESS_SECRET_ARN = re.compile(r":secret:oficina-auth(?:-[A-Za-z0-9]+)?$")


class SmokeTestFailure(Exception):
    """A safe, non-sensitive smoke-test failure."""


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicitly authorized RDS smoke test.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm that the current Lab session and RDS preconditions are ready.",
    )
    args = parser.parse_args()

    if not args.confirm or os.environ.get("RUN_REAL_RDS_SMOKE") != CONFIRMATION_VALUE:
        print("rds_smoke=refused explicit_confirmation_required")
        return 2

    try:
        _run_smoke_test(os.environ)
    except SmokeTestFailure as error:
        print(f"rds_smoke=failed reason={error}")
        return 1
    except Exception:
        print("rds_smoke=failed reason=unexpected_dependency_failure")
        return 1

    print("rds_smoke=passed connectivity=ok client_lookup=ok write_permissions=denied")
    return 0


def _run_smoke_test(environment: Mapping[str, str]) -> None:
    host = _required(environment, "DB_HOST")
    port = _port(environment.get("DB_PORT"))
    database = _required(environment, "POSTGRES_DB")
    secret_id = _required(environment, "DB_SECRET_ID")
    cpf = CPF(_required(environment, "SMOKE_TEST_CPF"))
    expected_client_id = _required(environment, "SMOKE_TEST_CLIENT_ID")

    if database != DATABASE_NAME:
        raise SmokeTestFailure("database_configuration_invalid")
    if not _is_auth_secret(secret_id):
        raise SmokeTestFailure("secret_configuration_invalid")

    secrets_client = Boto3SecretsManagerClient()
    credentials_provider = SecretsManagerDatabaseCredentialsProvider(
        secrets_client,
        secret_id,
        expected_username=EXPECTED_USERNAME,
    )
    credentials = credentials_provider.get_credentials()
    if credentials.password == "ALTERAR_SENHA":
        raise SmokeTestFailure("secret_placeholder_detected")

    connection = None
    cursor = None
    try:
        connection = _connect(
            user=credentials.username,
            password=credentials.password,
            host=host,
            port=port,
            database=database,
            timeout=CONNECT_TIMEOUT_SECONDS,
        )
        cursor = connection.cursor()
        _verify_client_lookup(cursor, cpf, expected_client_id)
        _verify_write_permissions(cursor, connection, cpf)
    except SmokeTestFailure:
        raise
    except Exception:
        raise SmokeTestFailure("database_unavailable") from None
    finally:
        _close_quietly(cursor)
        _close_quietly(connection)


def _connect(**kwargs: Any) -> Any:
    from pg8000 import dbapi

    return dbapi.connect(**kwargs)


def _verify_client_lookup(cursor: Any, cpf: CPF, expected_client_id: str) -> None:
    formatted_cpf = _format_cpf(cpf)
    cursor.execute(LOOKUP_SQL, (cpf.digits, formatted_cpf, cpf.digits))
    row = cursor.fetchone()
    if row is None:
        raise SmokeTestFailure("synthetic_client_not_found")

    cliente_id, ativo = row
    if str(cliente_id) != expected_client_id or not isinstance(ativo, bool):
        raise SmokeTestFailure("synthetic_client_contract_invalid")


def _verify_write_permissions(cursor: Any, connection: Any, cpf: CPF) -> None:
    statements = (
        ("INSERT", "INSERT INTO atendimento_cliente (cpf) SELECT %s WHERE false", (cpf.digits,)),
        ("UPDATE", "UPDATE atendimento_cliente SET ativo = ativo WHERE false", ()),
        ("DELETE", "DELETE FROM atendimento_cliente WHERE false", ()),
    )

    for operation, statement, parameters in statements:
        connection.rollback()
        try:
            cursor.execute(statement, parameters)
        except Exception as error:
            connection.rollback()
            if getattr(error, "sqlstate", None) == INSUFFICIENT_PRIVILEGE_SQLSTATE:
                continue
            raise SmokeTestFailure(f"{operation.lower()}_permission_check_failed") from None
        else:
            connection.rollback()
            raise SmokeTestFailure(f"{operation.lower()}_permission_granted")

    connection.rollback()


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not isinstance(value, str) or not value.strip():
        raise SmokeTestFailure(f"missing_{name.lower()}")
    return value


def _port(value: str | None) -> int:
    try:
        port = int(_required({"db_port": value or ""}, "db_port"))
    except (SmokeTestFailure, ValueError):
        raise SmokeTestFailure("invalid_db_port") from None
    if not 1 <= port <= 65535:
        raise SmokeTestFailure("invalid_db_port")
    return port


def _is_auth_secret(secret_id: str) -> bool:
    return secret_id == SECRET_NAME or bool(TRACELESS_SECRET_ARN.search(secret_id))


def _format_cpf(cpf: CPF) -> str:
    digits = cpf.digits
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def _close_quietly(resource: Any) -> None:
    if resource is None:
        return
    try:
        resource.close()
    except Exception:
        return


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from oficina_auth.application import AuthenticateClient
from oficina_auth.domain import AuthenticationRecord, DependencyUnavailable
from oficina_auth.domain.cpf import CPF
from oficina_auth.handlers import (
    HandlerConfig,
    create_auth_handler,
    create_handler_from_environment,
    create_local_demo_handler,
    lambda_handler,
)

VALID_CPF = "52998224725"
FORMATTED_CPF = "529.982.247-25"
ACCESS_TOKEN = "synthetic.jwt.value"
VALID_CORRELATION_ID = "123E4567-E89B-42D3-A456-426614174000"
VALID_TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00"
TRACESTATE = "vendor=value"
AUTH_HEADER = "Author" + "ization"
AUTH_VALUE = "Bearer " + "synthetic-redacted"


@dataclass
class Context:
    aws_request_id: str = "aws-request-001"


class StubTokenIssuer:
    def __init__(self, token: str = ACCESS_TOKEN) -> None:
        self._token = token

    def issue(self, cliente_id: str) -> str:
        return self._token


class ExplodingTokenIssuer:
    def issue(self, cliente_id: str) -> str:
        raise RuntimeError("synthetic issuer failure")


class FailingClientRepository:
    def find_by_cpf(self, cpf: CPF) -> AuthenticationRecord | None:
        raise RuntimeError("synthetic repository failure")


def api_event(
    body: Any = None,
    *,
    headers: dict[str, str] | None = None,
    method: str = "POST",
    is_base64_encoded: bool = False,
) -> dict[str, Any]:
    if body is None:
        raw_body = None
    elif isinstance(body, str):
        raw_body = body
    else:
        raw_body = json.dumps(body)

    if is_base64_encoded and raw_body is not None:
        raw_body = base64.b64encode(raw_body.encode("utf-8")).decode("ascii")

    return {
        "resource": "/auth",
        "path": "/auth",
        "httpMethod": method,
        "headers": headers or {"Content-Type": "application/json"},
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": None,
        "stageVariables": None,
        "requestContext": {
            "requestId": "gateway-request-001",
            "resourcePath": "/auth",
            "httpMethod": method,
        },
        "body": raw_body,
        "isBase64Encoded": is_base64_encoded,
    }


def auth_handler(
    records: dict[str, AuthenticationRecord] | None = None,
    token_issuer: StubTokenIssuer | ExplodingTokenIssuer | None = None,
):
    return create_local_demo_handler(
        records or {},
        token_issuer or StubTokenIssuer(),
        HandlerConfig(service_environment="test"),
    )


def parse_body(response: dict[str, Any]) -> dict[str, Any]:
    return json.loads(response["body"])


def parse_log(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    output = capsys.readouterr().out.strip()
    lines = [line for line in output.splitlines() if line]
    assert len(lines) == 1
    return json.loads(lines[0])


def assert_json_response(response: dict[str, Any], status_code: int) -> None:
    assert response["statusCode"] == status_code
    assert response["headers"]["Content-Type"] == "application/json"
    assert "X-Correlation-Id" in response["headers"]
    assert "X-Request-Id" in response["headers"]
    assert response["isBase64Encoded"] is False


def test_valid_cpf_and_eligible_client_returns_success(capsys: pytest.CaptureFixture[str]) -> None:
    handler = auth_handler(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=True)}
    )
    event = api_event(
        {"cpf": FORMATTED_CPF},
        headers={
            "Content-Type": "application/json",
            AUTH_HEADER: AUTH_VALUE,
            "X-Correlation-Id": VALID_CORRELATION_ID,
            "X-Request-Id": "request-001",
        },
    )

    response = handler(event, Context())

    assert_json_response(response, 200)
    assert response["headers"]["X-Correlation-Id"] == VALID_CORRELATION_ID
    assert response["headers"]["X-Request-Id"] == "request-001"
    assert parse_body(response) == {
        "access_token": ACCESS_TOKEN,
        "token_type": "Bearer",
        "expires_in": 900,
    }
    log = parse_log(capsys)
    assert log["correlation.id"] == VALID_CORRELATION_ID
    assert log["request_id"] == "request-001"
    assert log["http.status_code"] == 200
    assert log["auth.motivo"] == "autenticado"
    assert log["http.method"] == "POST"
    assert log["http.route"] == "/auth"
    assert log["message"] == "Authentication request completed"
    assert "timestamp" in log
    assert log["outcome"] == "success"


def test_invalid_cpf_returns_generic_401(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(api_event({"cpf": "11111111111"}), Context())

    assert_json_response(response, 401)
    error = parse_body(response)["error"]
    assert error["type"] == "invalid_credentials"
    assert error["message"] == "Credenciais invalidas ou cliente nao elegivel."
    assert error["requestId"] == "aws-request-001"
    log = parse_log(capsys)
    assert log["outcome"] == "invalid_credentials"
    assert log["auth.motivo"] == "cpf_invalido"


def test_missing_client_and_not_eligible_client_return_identical_public_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_response = auth_handler()(api_event({"cpf": VALID_CPF}), Context())
    missing_log = parse_log(capsys)
    not_eligible_response = auth_handler(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=False)}
    )(api_event({"cpf": VALID_CPF}), Context())

    assert missing_response["statusCode"] == 401
    assert not_eligible_response["statusCode"] == 401
    assert parse_body(missing_response) == parse_body(not_eligible_response)
    assert parse_body(missing_response) == {
        "error": {
            "type": "invalid_credentials",
            "message": "Credenciais invalidas ou cliente nao elegivel.",
            "requestId": "aws-request-001",
        }
    }
    assert missing_log["auth.motivo"] == "nao_encontrado"
    assert parse_log(capsys)["auth.motivo"] == "inativo"


def test_invalid_cpf_has_same_public_authentication_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid_response = auth_handler()(api_event({"cpf": "11111111111"}), Context())
    invalid_log = parse_log(capsys)
    missing_response = auth_handler()(api_event({"cpf": VALID_CPF}), Context())
    missing_log = parse_log(capsys)

    invalid_error = parse_body(invalid_response)["error"]
    missing_error = parse_body(missing_response)["error"]
    assert invalid_response["statusCode"] == missing_response["statusCode"] == 401
    assert invalid_error["type"] == missing_error["type"] == "invalid_credentials"
    assert invalid_error["message"] == missing_error["message"]
    assert invalid_log["auth.motivo"] == "cpf_invalido"
    assert missing_log["auth.motivo"] == "nao_encontrado"


def test_invalid_json_returns_400(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(api_event("{invalid-json"), Context())

    assert_json_response(response, 400)
    assert parse_body(response) == {
        "error": {
            "type": "invalid_request",
            "message": "Payload ou CPF invalido.",
            "requestId": "aws-request-001",
        }
    }
    log = parse_log(capsys)
    assert log["http.status_code"] == 400
    assert log["auth.motivo"] == "payload_invalido"


def test_base64_body_is_decoded(capsys: pytest.CaptureFixture[str]) -> None:
    handler = auth_handler(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=True)}
    )

    response = handler(api_event({"cpf": VALID_CPF}, is_base64_encoded=True), Context())

    assert_json_response(response, 200)
    assert parse_body(response)["access_token"] == ACCESS_TOKEN
    assert parse_log(capsys)["outcome"] == "success"


def test_headers_are_case_insensitive(capsys: pytest.CaptureFixture[str]) -> None:
    handler = auth_handler(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=True)}
    )
    event = api_event(
        {"cpf": VALID_CPF},
        headers={
            "cOnTeNt-TyPe": "application/json; charset=utf-8",
            "x-correlation-id": VALID_CORRELATION_ID,
        },
    )

    response = handler(event, Context())

    assert_json_response(response, 200)
    assert response["headers"]["X-Correlation-Id"] == VALID_CORRELATION_ID
    assert parse_log(capsys)["correlation.id"] == VALID_CORRELATION_ID


def test_valid_correlation_id_preserves_original_text(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(
        api_event(
            {"cpf": "11111111111"},
            headers={
                "Content-Type": "application/json",
                "X-Correlation-Id": VALID_CORRELATION_ID,
            },
        ),
        Context(),
    )

    assert response["headers"]["X-Correlation-Id"] == VALID_CORRELATION_ID
    assert parse_log(capsys)["correlation.id"] == VALID_CORRELATION_ID


def test_absent_correlation_id_generates_uuid_v4(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(api_event({"cpf": "11111111111"}), Context())

    generated = uuid.UUID(response["headers"]["X-Correlation-Id"])
    assert generated.version == 4
    assert parse_log(capsys)["correlation.id"] == response["headers"]["X-Correlation-Id"]


def test_invalid_correlation_id_generates_canonical_uuid_v4(
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = auth_handler()(
        api_event(
            {"cpf": "11111111111"},
            headers={
                "Content-Type": "application/json",
                "X-Correlation-Id": "not-a-uuid",
            },
        ),
        Context(),
    )

    generated = uuid.UUID(response["headers"]["X-Correlation-Id"])
    assert generated.version == 4
    assert response["headers"]["X-Correlation-Id"] == str(generated)
    assert parse_log(capsys)["correlation.id"] == str(generated)


def test_traceparent_is_propagated_and_tracestate_is_not_fabricated(
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = auth_handler()(
        api_event(
            {"cpf": "11111111111"},
            headers={
                "Content-Type": "application/json",
                "traceparent": VALID_TRACEPARENT,
            },
        ),
        Context(),
    )

    assert response["headers"]["traceparent"] == VALID_TRACEPARENT
    assert "tracestate" not in response["headers"]
    parse_log(capsys)


def test_tracestate_is_propagated_only_when_received(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(
        api_event(
            {"cpf": "11111111111"},
            headers={
                "Content-Type": "application/json",
                "tracestate": TRACESTATE,
            },
        ),
        Context(),
    )

    assert response["headers"]["tracestate"] == TRACESTATE
    parse_log(capsys)


def test_dependency_unavailable_returns_503(capsys: pytest.CaptureFixture[str]) -> None:
    handler = create_auth_handler(
        AuthenticateClient(FailingClientRepository(), StubTokenIssuer()),
        HandlerConfig(service_environment="test"),
    )

    response = handler(api_event({"cpf": VALID_CPF}), Context())

    assert_json_response(response, 503)
    assert parse_body(response) == {
        "error": {
            "type": "dependency_unavailable",
            "message": "Dependencia temporariamente indisponivel.",
            "requestId": "aws-request-001",
        }
    }
    assert parse_log(capsys)["outcome"] == "dependency_unavailable"


def test_unexpected_exception_returns_500_without_stack_trace(
    capsys: pytest.CaptureFixture[str],
) -> None:
    handler = auth_handler(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=True)},
        ExplodingTokenIssuer(),
    )

    response = handler(api_event({"cpf": VALID_CPF}), Context())

    assert_json_response(response, 500)
    assert parse_body(response) == {
        "error": {
            "type": "internal_error",
            "message": "Erro interno.",
            "requestId": "aws-request-001",
        }
    }
    assert "Traceback" not in response["body"]
    assert parse_log(capsys)["outcome"] == "unexpected_error"


def test_body_payload_must_contain_only_cpf(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(api_event({"cpf": VALID_CPF, "unexpected": "field"}), Context())

    assert_json_response(response, 400)
    assert parse_body(response) == {
        "error": {
            "type": "invalid_request",
            "message": "Payload ou CPF invalido.",
            "requestId": "aws-request-001",
        }
    }
    parse_log(capsys)


def test_missing_body_returns_400(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(api_event(), Context())

    assert_json_response(response, 400)
    assert parse_body(response) == {
        "error": {
            "type": "invalid_request",
            "message": "Payload ou CPF invalido.",
            "requestId": "aws-request-001",
        }
    }
    parse_log(capsys)


def test_non_json_content_type_returns_400(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(
        api_event({"cpf": VALID_CPF}, headers={"Content-Type": "text/plain"}), Context()
    )

    assert_json_response(response, 400)
    assert parse_body(response) == {
        "error": {
            "type": "invalid_request",
            "message": "Payload ou CPF invalido.",
            "requestId": "aws-request-001",
        }
    }
    parse_log(capsys)


def test_non_post_method_returns_400(capsys: pytest.CaptureFixture[str]) -> None:
    response = auth_handler()(api_event({"cpf": VALID_CPF}, method="GET"), Context())

    assert_json_response(response, 400)
    assert parse_body(response) == {
        "error": {
            "type": "invalid_request",
            "message": "Payload ou CPF invalido.",
            "requestId": "aws-request-001",
        }
    }
    parse_log(capsys)


def test_default_lambda_handler_does_not_use_in_memory_in_production(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("OFICINA_AUTH_ENABLE_IN_MEMORY_DEMO", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    response = lambda_handler(api_event({"cpf": VALID_CPF}), Context())

    assert_json_response(response, 503)
    assert parse_body(response) == {
        "error": {
            "type": "dependency_unavailable",
            "message": "Dependencia temporariamente indisponivel.",
            "requestId": "aws-request-001",
        }
    }
    assert parse_log(capsys)["service.environment"] == "production"


def test_environment_factory_rejects_demo_without_explicit_dependencies() -> None:
    with pytest.raises(DependencyUnavailable, match="Demo local exige dependencias explicitas\\."):
        create_handler_from_environment(
            {"APP_ENV": "local", "OFICINA_AUTH_ENABLE_IN_MEMORY_DEMO": "true"}
        )


def test_local_demo_rejects_production_environment() -> None:
    with pytest.raises(DependencyUnavailable, match=r"Demo local exige ambiente local\."):
        create_local_demo_handler(
            {},
            StubTokenIssuer(),
            HandlerConfig(service_environment="production"),
        )


def test_logs_do_not_include_sensitive_values(capsys: pytest.CaptureFixture[str]) -> None:
    handler = auth_handler(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=True)}
    )
    event = api_event(
        {"cpf": FORMATTED_CPF},
        headers={
            "Content-Type": "application/json",
            AUTH_HEADER: AUTH_VALUE,
            "X-Correlation-Id": VALID_CORRELATION_ID,
        },
    )

    handler(event, Context())

    output = capsys.readouterr().out
    assert VALID_CPF not in output
    assert FORMATTED_CPF not in output
    assert ACCESS_TOKEN not in output
    assert AUTH_HEADER not in output
    assert AUTH_VALUE not in output

from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from oficina_auth import __version__
from oficina_auth.application import AuthenticateClient
from oficina_auth.application.ports import TokenIssuer
from oficina_auth.domain import (
    AuthenticationRecord,
    DependencyUnavailable,
    InvalidCredentials,
    InvalidInput,
)
from oficina_auth.infrastructure import InMemoryClientRepository

JSON_CONTENT_TYPE = "application/json"
INVALID_INPUT_MESSAGE = "Payload ou CPF invalido."
INVALID_CREDENTIALS_MESSAGE = "Credenciais invalidas ou cliente nao elegivel."
DEPENDENCY_UNAVAILABLE_MESSAGE = "Dependencia temporariamente indisponivel."
INTERNAL_ERROR_MESSAGE = "Erro interno."
TRACEPARENT_PATTERN = re.compile(
    r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HandlerConfig:
    service_name: str = "oficina-auth"
    service_environment: str = "local"
    service_version: str = __version__


ApiGatewayHandler = Callable[[dict[str, Any], Any], dict[str, Any]]


def create_auth_handler(
    authenticator: AuthenticateClient,
    config: HandlerConfig | None = None,
) -> ApiGatewayHandler:
    handler_config = config or HandlerConfig()

    def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
        return _handle_event(
            event=event,
            context=context,
            authenticator=authenticator,
            config=handler_config,
        )

    return handler


def create_local_demo_handler(
    records: Mapping[str, AuthenticationRecord],
    token_issuer: TokenIssuer,
    config: HandlerConfig | None = None,
) -> ApiGatewayHandler:
    handler_config = config or HandlerConfig(service_environment="local")
    if handler_config.service_environment not in {"local", "test", "demo", "local-demo"}:
        raise DependencyUnavailable("Demo local exige ambiente local.")
    authenticator = AuthenticateClient(InMemoryClientRepository(dict(records)), token_issuer)
    return create_auth_handler(authenticator, handler_config)


def create_handler_from_environment(environ: Mapping[str, str] | None = None) -> ApiGatewayHandler:
    environment = environ or os.environ
    service_environment = environment.get("APP_ENV", "production")

    if environment.get("OFICINA_AUTH_ENABLE_IN_MEMORY_DEMO") == "true":
        if service_environment not in {"local", "test", "demo"}:
            raise DependencyUnavailable("Dependencia de autenticacao nao configurada.")
        raise DependencyUnavailable("Demo local exige dependencias explicitas.")

    raise DependencyUnavailable("Dependencia de autenticacao nao configurada.")


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    try:
        handler = create_handler_from_environment()
    except DependencyUnavailable:
        return _handle_event(
            event=event,
            context=context,
            authenticator=None,
            config=HandlerConfig(service_environment=os.environ.get("APP_ENV", "production")),
        )

    return handler(event, context)


def _handle_event(
    event: dict[str, Any],
    context: Any,
    authenticator: AuthenticateClient | None,
    config: HandlerConfig,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    headers = _case_insensitive_headers(event.get("headers") or {})
    correlation_id = _correlation_id(headers.get("x-correlation-id"))
    request_id = _request_id(headers=headers, context=context)
    trace_headers = _trace_headers(headers)
    status_code = 500
    outcome = "error"
    response_body = {"message": INTERNAL_ERROR_MESSAGE}

    try:
        if event.get("httpMethod") != "POST":
            raise InvalidInput(INVALID_INPUT_MESSAGE)

        if not _is_json_content_type(headers.get("content-type")):
            raise InvalidInput(INVALID_INPUT_MESSAGE)

        payload = _parse_payload(event)
        if set(payload) != {"cpf"} or not isinstance(payload["cpf"], str):
            raise InvalidInput(INVALID_INPUT_MESSAGE)

        if authenticator is None:
            raise DependencyUnavailable(DEPENDENCY_UNAVAILABLE_MESSAGE)

        result = authenticator.execute(payload["cpf"])
        status_code = 200
        outcome = "success"
        response_body = {
            "access_token": result.access_token,
            "token_type": result.token_type,
            "expires_in": result.expires_in,
        }
    except InvalidInput:
        status_code = 400
        outcome = "invalid_input"
        response_body = {"message": INVALID_INPUT_MESSAGE}
    except InvalidCredentials:
        status_code = 401
        outcome = "invalid_credentials"
        response_body = {"message": INVALID_CREDENTIALS_MESSAGE}
    except DependencyUnavailable:
        status_code = 503
        outcome = "dependency_unavailable"
        response_body = {"message": DEPENDENCY_UNAVAILABLE_MESSAGE}
    except Exception:
        status_code = 500
        outcome = "unexpected_error"
        response_body = {"message": INTERNAL_ERROR_MESSAGE}
    finally:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        _log_event(
            config=config,
            correlation_id=correlation_id,
            request_id=request_id,
            duration_ms=duration_ms,
            status_code=status_code,
            outcome=outcome,
        )

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": JSON_CONTENT_TYPE,
            "X-Correlation-Id": correlation_id,
            "X-Request-Id": request_id,
            **trace_headers,
        },
        "body": json.dumps(response_body, separators=(",", ":")),
        "isBase64Encoded": False,
    }


def _case_insensitive_headers(raw_headers: Mapping[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in raw_headers.items():
        if isinstance(key, str) and isinstance(value, str):
            headers[key.lower()] = value
    return headers


def _is_json_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return False
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    return media_type == JSON_CONTENT_TYPE


def _parse_payload(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if not isinstance(body, str) or body == "":
        raise InvalidInput(INVALID_INPUT_MESSAGE)

    if event.get("isBase64Encoded") is True:
        try:
            body = base64.b64decode(body, validate=True).decode("utf-8")
        except Exception:
            raise InvalidInput(INVALID_INPUT_MESSAGE) from None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise InvalidInput(INVALID_INPUT_MESSAGE) from None

    if not isinstance(payload, dict):
        raise InvalidInput(INVALID_INPUT_MESSAGE)

    return payload


def _correlation_id(value: str | None) -> str:
    if value is not None and _is_uuid_v4(value):
        return value
    return str(uuid.uuid4())


def _is_uuid_v4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False

    return parsed.version == 4 and str(parsed).lower() == value.lower()


def _request_id(headers: Mapping[str, str], context: Any) -> str:
    header_value = headers.get("x-request-id")
    if header_value:
        return header_value

    aws_request_id = getattr(context, "aws_request_id", None)
    if isinstance(aws_request_id, str) and aws_request_id:
        return aws_request_id

    return str(uuid.uuid4())


def _trace_headers(headers: Mapping[str, str]) -> dict[str, str]:
    response_headers: dict[str, str] = {}
    traceparent = headers.get("traceparent")
    tracestate = headers.get("tracestate")

    if traceparent is not None and _is_valid_traceparent(traceparent):
        response_headers["traceparent"] = traceparent

    if tracestate is not None:
        response_headers["tracestate"] = tracestate

    return response_headers


def _is_valid_traceparent(value: str) -> bool:
    if not TRACEPARENT_PATTERN.fullmatch(value):
        return False

    _, trace_id, parent_id, _ = value.split("-")
    return trace_id != "0" * 32 and parent_id != "0" * 16


def _log_event(
    config: HandlerConfig,
    correlation_id: str,
    request_id: str,
    duration_ms: int,
    status_code: int,
    outcome: str,
) -> None:
    level = "INFO" if status_code < 500 else "ERROR"
    log_record = {
        "service.name": config.service_name,
        "service.environment": config.service_environment,
        "service.version": config.service_version,
        "event": "auth.request.completed",
        "level": level,
        "correlation.id": correlation_id,
        "request_id": request_id,
        "duration_ms": duration_ms,
        "status_code": status_code,
        "outcome": outcome,
    }
    print(json.dumps(log_record, separators=(",", ":"), sort_keys=True))

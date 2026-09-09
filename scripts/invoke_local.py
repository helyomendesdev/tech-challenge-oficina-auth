from __future__ import annotations

import contextlib
import io
import json
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from oficina_auth.application import AuthenticateClient  # noqa: E402
from oficina_auth.domain import AuthenticationRecord  # noqa: E402
from oficina_auth.domain.cpf import CPF  # noqa: E402
from oficina_auth.handlers import (  # noqa: E402
    HandlerConfig,
    create_auth_handler,
    create_local_demo_handler,
)
from oficina_auth.infrastructure.jwt_tokens import Rs256TokenIssuer  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "api_gateway"
SUCCESS_CPF = "52998224725"
MISSING_CLIENT_CPF = "39053344705"
REDACTED = "<redacted>"
SENSITIVE_MARKERS = {
    SUCCESS_CPF,
    "529.982.247-25",
    MISSING_CLIENT_CPF,
    "390.533.447-05",
    "Authorization",
    "Bearer ",
}


@dataclass(frozen=True)
class DemoScenario:
    name: str
    fixture: str
    expected_status: int
    handler_factory: Callable[[], Callable[[dict[str, Any], Any], dict[str, Any]]]
    expect_reused_correlation: bool = False
    expect_generated_correlation: bool = False


@dataclass(frozen=True)
class DemoContext:
    aws_request_id: str = "local-demo-request"


@dataclass(frozen=True)
class EphemeralPrivateKeyProvider:
    private_key: bytes

    def get_private_key(self) -> bytes:
        return self.private_key


class FailingClientRepository:
    def find_by_cpf(self, cpf: CPF) -> AuthenticationRecord | None:
        raise RuntimeError("synthetic dependency unavailable")


def main() -> int:
    started_at = time.perf_counter()
    token_issuer = Rs256TokenIssuer(EphemeralPrivateKeyProvider(_generate_private_key()))
    success_handler = create_local_demo_handler(
        {SUCCESS_CPF: AuthenticationRecord(cliente_id="cliente-demo", can_authenticate=True)},
        token_issuer,
        HandlerConfig(service_environment="local-demo"),
    )
    dependency_handler = create_auth_handler(
        AuthenticateClient(FailingClientRepository(), token_issuer),
        HandlerConfig(service_environment="local-demo"),
    )
    scenarios = [
        DemoScenario(
            name="200 with provided X-Correlation-Id",
            fixture="success_with_correlation.json",
            expected_status=200,
            handler_factory=lambda: success_handler,
            expect_reused_correlation=True,
        ),
        DemoScenario(
            name="200 with generated X-Correlation-Id",
            fixture="success_without_correlation.json",
            expected_status=200,
            handler_factory=lambda: success_handler,
            expect_generated_correlation=True,
        ),
        DemoScenario(
            name="401 invalid CPF",
            fixture="invalid_cpf.json",
            expected_status=401,
            handler_factory=lambda: success_handler,
        ),
        DemoScenario(
            name="401 generic client failure",
            fixture="client_not_found.json",
            expected_status=401,
            handler_factory=lambda: success_handler,
        ),
        DemoScenario(
            name="503 dependency unavailable",
            fixture="dependency_unavailable.json",
            expected_status=503,
            handler_factory=lambda: dependency_handler,
        ),
    ]

    output_lines = ["Local authentication demo"]
    failures: list[str] = []

    for scenario in scenarios:
        result = _run_scenario(scenario)
        output_lines.extend(result["lines"])
        failures.extend(result["failures"])

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    output_lines.append(f"duration_ms={elapsed_ms}")

    rendered_output = "\n".join(output_lines)
    leaked = sorted(marker for marker in SENSITIVE_MARKERS if marker in rendered_output)
    if leaked:
        failures.append(f"stdout contains sensitive marker(s): {', '.join(leaked)}")

    print(rendered_output)

    if failures:
        print("contract_failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("demo_result=ok")
    return 0


def _run_scenario(scenario: DemoScenario) -> dict[str, Any]:
    event = _load_fixture(scenario.fixture)
    handler = scenario.handler_factory()
    captured_stdout = io.StringIO()
    failures: list[str] = []

    with contextlib.redirect_stdout(captured_stdout):
        response = handler(event, DemoContext())

    sanitized_body = _sanitize_response_body(response)
    log_lines = _parse_logs(captured_stdout.getvalue())
    headers = response.get("headers", {})
    correlation_id = headers.get("X-Correlation-Id")

    if response.get("statusCode") != scenario.expected_status:
        actual_status = response.get("statusCode")
        failures.append(
            f"{scenario.name}: expected {scenario.expected_status}, got {actual_status}"
        )

    if headers.get("Content-Type") != "application/json":
        failures.append(f"{scenario.name}: missing JSON response header")

    if not _is_uuid_v4(correlation_id):
        failures.append(f"{scenario.name}: invalid X-Correlation-Id")

    provided_correlation = event["headers"].get("X-Correlation-Id")
    if scenario.expect_reused_correlation and correlation_id != provided_correlation:
        failures.append(f"{scenario.name}: did not preserve provided correlation id")

    if scenario.expect_generated_correlation and correlation_id == provided_correlation:
        failures.append(f"{scenario.name}: did not generate correlation id")

    if not log_lines:
        failures.append(f"{scenario.name}: no JSON log emitted")

    for log_record in log_lines:
        if log_record.get("correlation.id") != correlation_id:
            failures.append(f"{scenario.name}: log correlation mismatch")
        if log_record.get("http.status_code") != scenario.expected_status:
            failures.append(f"{scenario.name}: log status mismatch")

    if scenario.expected_status == 200:
        if sanitized_body.get("token_type") != "Bearer" or sanitized_body.get("expires_in") != 900:
            failures.append(f"{scenario.name}: invalid success contract")
    else:
        error = sanitized_body.get("error")
        if not isinstance(error, dict) or error.get("requestId") != headers.get("X-Request-Id"):
            failures.append(f"{scenario.name}: invalid error envelope")

    return {
        "lines": [
            f"- {scenario.name}: status={response.get('statusCode')} "
            f"correlation={correlation_id} body={json.dumps(sanitized_body, sort_keys=True)}",
            *[f"  log={json.dumps(log_record, sort_keys=True)}" for log_record in log_lines],
        ],
        "failures": failures,
    }


def _load_fixture(filename: str) -> dict[str, Any]:
    with (FIXTURE_DIR / filename).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _sanitize_response_body(response: dict[str, Any]) -> dict[str, Any]:
    body = json.loads(response.get("body") or "{}")
    if "access_token" in body:
        body["access_token"] = REDACTED
    return body


def _parse_logs(raw_output: str) -> list[dict[str, Any]]:
    records = []
    for line in raw_output.splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _is_uuid_v4(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed).lower() == value.lower()


def _generate_private_key() -> bytes:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


if __name__ == "__main__":
    raise SystemExit(main())

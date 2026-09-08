from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = ROOT / "openapi" / "openapi.yaml"


def load_contract() -> dict:
    with OPENAPI_PATH.open(encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)


def test_openapi_yaml_is_parseable() -> None:
    contract = load_contract()

    assert contract["openapi"] == "3.0.3"
    assert "/auth" in contract["paths"]


def test_post_auth_contract_shape() -> None:
    operation = load_contract()["paths"]["/auth"]["post"]
    responses = operation["responses"]

    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/AuthRequest"
    )
    assert set(responses) == {"200", "400", "401", "503"}

    for response in responses.values():
        assert "X-Correlation-Id" in response["headers"]


def test_success_response_contract_values() -> None:
    schemas = load_contract()["components"]["schemas"]
    success = schemas["AuthSuccessResponse"]["properties"]

    assert success["token_type"]["enum"] == ["Bearer"]
    assert success["expires_in"]["enum"] == [900]


def test_unauthorized_response_uses_generic_message() -> None:
    response = load_contract()["paths"]["/auth"]["post"]["responses"]["401"]
    example = response["content"]["application/json"]["examples"]["genericUnauthorized"]["value"]

    assert example == {"message": "Credenciais invalidas ou cliente nao elegivel."}

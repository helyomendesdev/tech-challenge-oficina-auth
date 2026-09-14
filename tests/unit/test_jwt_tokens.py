from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from oficina_auth.domain import DependencyUnavailable, InvalidCredentials
from oficina_auth.infrastructure.jwt_tokens import (
    AUDIENCE,
    ISSUER,
    TOKEN_EXPIRATION_SECONDS,
    Rs256TokenIssuer,
    TokenVerifier,
)

CLIENTE_ID = 42
FIXED_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    current: datetime = FIXED_NOW

    def now(self) -> datetime:
        return self.current


@dataclass(frozen=True)
class StaticPrivateKeyProvider:
    private_key: str | bytes

    def get_private_key(self) -> str | bytes:
        return self.private_key


@dataclass(frozen=True)
class StaticPublicKeyProvider:
    public_key: str | bytes

    def get_public_key(self) -> str | bytes:
        return self.public_key


class FailingPrivateKeyProvider:
    def get_private_key(self) -> str | bytes:
        raise RuntimeError("synthetic key provider failure")


@dataclass(frozen=True)
class KeyPair:
    private_pem: bytes
    public_pem: bytes


@pytest.fixture
def key_pair() -> KeyPair:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return KeyPair(private_pem=private_pem, public_pem=public_pem)


@pytest.fixture
def other_key_pair() -> KeyPair:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return KeyPair(private_pem=private_pem, public_pem=public_pem)


def valid_claims(**overrides: Any) -> dict[str, Any]:
    issued_at = int(FIXED_NOW.timestamp())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": f"cliente:{CLIENTE_ID}",
        "cliente_id": CLIENTE_ID,
        "principal_type": "cliente",
        "token_type": "access",
        "iat": issued_at,
        "exp": issued_at + TOKEN_EXPIRATION_SECONDS,
        "jti": "4f9b1e43-c189-49de-8eb3-3d6f8d8ea5f6",
    }
    claims.update(overrides)
    return claims


def sign_rs256(key_pair: KeyPair, claims: dict[str, Any]) -> str:
    return jwt.encode(claims, key_pair.private_pem, algorithm="RS256")


def verifier_for(key_pair: KeyPair, clock: FixedClock | None = None) -> TokenVerifier:
    return TokenVerifier(StaticPublicKeyProvider(key_pair.public_pem), clock or FixedClock())


def test_valid_token_is_issued_and_verified(key_pair: KeyPair) -> None:
    issuer = Rs256TokenIssuer(StaticPrivateKeyProvider(key_pair.private_pem), FixedClock())
    verifier = verifier_for(key_pair)

    token = issuer.issue(str(CLIENTE_ID))
    claims = verifier.verify(token)
    decoded = jwt.decode(
        token,
        key_pair.public_pem,
        algorithms=["RS256"],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"verify_exp": False},
    )

    assert claims.cliente_id == CLIENTE_ID
    assert claims.subject == f"cliente:{CLIENTE_ID}"
    assert decoded["cliente_id"] == CLIENTE_ID
    assert isinstance(decoded["cliente_id"], int)
    assert decoded["sub"] == f"cliente:{CLIENTE_ID}"
    assert decoded["principal_type"] == "cliente"
    assert decoded["token_type"] == "access"
    assert decoded["exp"] - decoded["iat"] == TOKEN_EXPIRATION_SECONDS
    assert jwt.get_unverified_header(token)["alg"] == "RS256"
    assert {"created_by_id", "cpf", "nome", "name", "email"}.isdisjoint(decoded)


def test_token_can_be_issued_and_verified_with_default_clock(key_pair: KeyPair) -> None:
    issuer = Rs256TokenIssuer(StaticPrivateKeyProvider(key_pair.private_pem))
    verifier = TokenVerifier(StaticPublicKeyProvider(key_pair.public_pem))

    claims = verifier.verify(issuer.issue(str(CLIENTE_ID)))

    assert claims.cliente_id == CLIENTE_ID


def test_tampered_signature_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims())
    header_and_payload, signature = token.rsplit(".", maxsplit=1)
    replacement = "A" if signature[0] != "A" else "B"
    tampered_token = f"{header_and_payload}.{replacement}{signature[1:]}"

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(tampered_token)


def test_wrong_key_is_rejected(key_pair: KeyPair, other_key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims())

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(other_key_pair).verify(token)


def test_non_rs256_algorithm_is_rejected(key_pair: KeyPair) -> None:
    token = jwt.encode(valid_claims(), "synthetic-secret-for-hs256-tests-only", algorithm="HS256")

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_wrong_issuer_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(iss="other-issuer"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_wrong_audience_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(aud="other-audience"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_expired_token_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(
        key_pair, valid_claims(exp=int((FIXED_NOW - timedelta(seconds=1)).timestamp()))
    )

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_future_iat_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(
        key_pair, valid_claims(iat=int((FIXED_NOW + timedelta(seconds=1)).timestamp()))
    )

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_missing_jti_is_rejected(key_pair: KeyPair) -> None:
    claims = valid_claims()
    del claims["jti"]
    token = sign_rs256(key_pair, claims)

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_wrong_principal_type_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(principal_type="operador"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_wrong_token_type_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(token_type="refresh"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_subject_must_match_cliente_id(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(sub="cliente:outro"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_missing_cliente_id_is_rejected(key_pair: KeyPair) -> None:
    claims = valid_claims()
    del claims["cliente_id"]
    token = sign_rs256(key_pair, claims)

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_forbidden_personal_claim_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(cpf="52998224725"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_non_uuid_v4_jti_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(jti="5dd9f830-a60e-311a-9210-0a99b67019ae"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_malformed_jti_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(jti="not-a-uuid"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


@pytest.mark.parametrize("cliente_id", ["", "42", True, 4.2])
def test_non_integer_cliente_id_is_rejected(key_pair: KeyPair, cliente_id: Any) -> None:
    token = sign_rs256(key_pair, valid_claims(cliente_id=cliente_id, sub=f"cliente:{cliente_id}"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


@pytest.mark.parametrize("cliente_id", ["cliente-001", "", "0", "-1"])
def test_non_numeric_cliente_id_cannot_be_issued(key_pair: KeyPair, cliente_id: str) -> None:
    issuer = Rs256TokenIssuer(StaticPrivateKeyProvider(key_pair.private_pem), FixedClock())

    with pytest.raises(DependencyUnavailable, match="Identidade do cliente invalida\\."):
        issuer.issue(cliente_id)


def test_non_integer_iat_is_rejected(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims(iat="synthetic-invalid-iat"))

    with pytest.raises(InvalidCredentials, match="Token invalido\\."):
        verifier_for(key_pair).verify(token)


def test_missing_private_key_fails_safely() -> None:
    issuer = Rs256TokenIssuer(StaticPrivateKeyProvider(""), FixedClock())

    with pytest.raises(DependencyUnavailable, match="Chave criptografica indisponivel\\."):
        issuer.issue(str(CLIENTE_ID))


def test_private_key_provider_failure_fails_safely() -> None:
    issuer = Rs256TokenIssuer(FailingPrivateKeyProvider(), FixedClock())

    with pytest.raises(DependencyUnavailable, match="Chave criptografica indisponivel\\."):
        issuer.issue(str(CLIENTE_ID))


def test_invalid_private_key_fails_safely() -> None:
    issuer = Rs256TokenIssuer(StaticPrivateKeyProvider("invalid-private-key"), FixedClock())

    with pytest.raises(DependencyUnavailable, match="Chave privada de assinatura indisponivel\\."):
        issuer.issue(str(CLIENTE_ID))


def test_invalid_public_key_fails_safely(key_pair: KeyPair) -> None:
    token = sign_rs256(key_pair, valid_claims())
    verifier = TokenVerifier(StaticPublicKeyProvider("invalid-public-key"), FixedClock())

    with pytest.raises(DependencyUnavailable, match="Chave publica de verificacao indisponivel\\."):
        verifier.verify(token)


def test_token_and_key_are_not_logged_or_exposed_in_error(
    caplog: pytest.LogCaptureFixture,
    key_pair: KeyPair,
) -> None:
    caplog.set_level(logging.INFO)
    issuer = Rs256TokenIssuer(StaticPrivateKeyProvider(key_pair.private_pem), FixedClock())
    token = issuer.issue(str(CLIENTE_ID))
    verifier = TokenVerifier(StaticPublicKeyProvider("invalid-public-key"), FixedClock())

    with pytest.raises(DependencyUnavailable) as exc_info:
        verifier.verify(token)

    assert token not in str(exc_info.value)
    assert key_pair.private_pem.decode("utf-8") not in str(exc_info.value)
    assert not caplog.records

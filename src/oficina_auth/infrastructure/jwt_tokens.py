from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from jwt import InvalidTokenError, PyJWTError

from oficina_auth.application.ports import TokenIssuer
from oficina_auth.domain.exceptions import DependencyUnavailable, InvalidCredentials

ISSUER = "oficina-auth"
AUDIENCE = "oficina-api"
ALGORITHM = "RS256"
TOKEN_EXPIRATION_SECONDS = 900
REQUIRED_CLAIMS = [
    "iss",
    "aud",
    "sub",
    "cliente_id",
    "principal_type",
    "token_type",
    "iat",
    "exp",
    "jti",
]
FORBIDDEN_CLAIMS = {"created_by_id", "cpf", "nome", "name", "email"}


class Clock(Protocol):
    def now(self) -> datetime:  # pragma: no cover
        raise NotImplementedError


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class PrivateKeyProvider(Protocol):
    def get_private_key(self) -> str | bytes:  # pragma: no cover
        raise NotImplementedError


class PublicKeyProvider(Protocol):
    def get_public_key(self) -> str | bytes:  # pragma: no cover
        raise NotImplementedError


@dataclass(frozen=True)
class TokenClaims:
    cliente_id: str
    subject: str
    issued_at: int
    expires_at: int
    jwt_id: str


class Rs256TokenIssuer(TokenIssuer):
    def __init__(
        self,
        private_key_provider: PrivateKeyProvider,
        clock: Clock | None = None,
    ) -> None:
        self._private_key_provider = private_key_provider
        self._clock = clock or SystemClock()

    def issue(self, cliente_id: str) -> str:
        private_key = _load_private_key(self._private_key_provider.get_private_key)
        now = self._clock.now().astimezone(UTC)
        issued_at = int(now.timestamp())
        expires_at = int((now + timedelta(seconds=TOKEN_EXPIRATION_SECONDS)).timestamp())

        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": f"cliente:{cliente_id}",
            "cliente_id": cliente_id,
            "principal_type": "cliente",
            "token_type": "access",
            "iat": issued_at,
            "exp": expires_at,
            "jti": str(uuid.uuid4()),
        }

        try:
            return jwt.encode(claims, private_key, algorithm=ALGORITHM)
        except PyJWTError:  # pragma: no cover
            raise DependencyUnavailable("Chave privada de assinatura indisponivel.") from None
        except Exception:  # pragma: no cover
            raise DependencyUnavailable("Chave privada de assinatura indisponivel.") from None


class TokenVerifier:
    def __init__(
        self,
        public_key_provider: PublicKeyProvider,
        clock: Clock | None = None,
    ) -> None:
        self._public_key_provider = public_key_provider
        self._clock = clock or SystemClock()

    def verify(self, token: str) -> TokenClaims:
        public_key = _load_public_key(self._public_key_provider.get_public_key)

        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={
                    "require": REQUIRED_CLAIMS,
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
        except InvalidTokenError:
            raise InvalidCredentials("Token invalido.") from None
        except PyJWTError:  # pragma: no cover
            raise InvalidCredentials("Token invalido.") from None
        except Exception:  # pragma: no cover
            raise DependencyUnavailable("Chave publica de verificacao indisponivel.") from None

        return self._validate_claims(claims)

    def _validate_claims(self, claims: dict[str, Any]) -> TokenClaims:
        cliente_id = _require_non_empty_string(claims, "cliente_id")
        subject = _require_non_empty_string(claims, "sub")
        principal_type = _require_non_empty_string(claims, "principal_type")
        token_type = _require_non_empty_string(claims, "token_type")
        jwt_id = _require_non_empty_string(claims, "jti")
        issued_at = _require_int(claims, "iat")
        expires_at = _require_int(claims, "exp")
        now = int(self._clock.now().astimezone(UTC).timestamp())

        if FORBIDDEN_CLAIMS.intersection(claims):
            raise InvalidCredentials("Token invalido.")

        if subject != f"cliente:{cliente_id}":
            raise InvalidCredentials("Token invalido.")

        if principal_type != "cliente" or token_type != "access":
            raise InvalidCredentials("Token invalido.")

        if issued_at > now or expires_at <= now:
            raise InvalidCredentials("Token invalido.")

        try:
            parsed_jti = uuid.UUID(jwt_id)
        except ValueError:
            raise InvalidCredentials("Token invalido.") from None

        if parsed_jti.version != 4:
            raise InvalidCredentials("Token invalido.")

        return TokenClaims(
            cliente_id=cliente_id,
            subject=subject,
            issued_at=issued_at,
            expires_at=expires_at,
            jwt_id=jwt_id,
        )


def _load_key(load_key: Any) -> str | bytes:
    try:
        key = load_key()
    except Exception:
        raise DependencyUnavailable("Chave criptografica indisponivel.") from None

    if not isinstance(key, str | bytes) or len(key) == 0:
        raise DependencyUnavailable("Chave criptografica indisponivel.")

    return key


def _load_private_key(load_key: Any) -> str | bytes:
    key = _load_key(load_key)
    try:
        load_pem_private_key(_as_bytes(key), password=None)
    except Exception:
        raise DependencyUnavailable("Chave privada de assinatura indisponivel.") from None
    return key


def _load_public_key(load_key: Any) -> str | bytes:
    key = _load_key(load_key)
    try:
        load_pem_public_key(_as_bytes(key))
    except Exception:
        raise DependencyUnavailable("Chave publica de verificacao indisponivel.") from None
    return key


def _as_bytes(key: str | bytes) -> bytes:
    if isinstance(key, bytes):
        return key
    return key.encode("utf-8")


def _require_non_empty_string(claims: dict[str, Any], claim_name: str) -> str:
    value = claims.get(claim_name)
    if not isinstance(value, str) or not value:
        raise InvalidCredentials("Token invalido.")
    return value


def _require_int(claims: dict[str, Any], claim_name: str) -> int:
    value = claims.get(claim_name)
    if not isinstance(value, int):
        raise InvalidCredentials("Token invalido.")
    return value

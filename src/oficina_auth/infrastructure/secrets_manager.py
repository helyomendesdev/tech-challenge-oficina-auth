from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from oficina_auth.domain.exceptions import DependencyUnavailable

SECRETS_MANAGER_ERROR = "Dependencia temporariamente indisponivel."
DEFAULT_CACHE_TTL_SECONDS = 300.0


class SecretsManagerClient(Protocol):
    def get_secret_value(self, *, SecretId: str) -> Mapping[str, Any]:
        raise NotImplementedError


class Boto3SecretsManagerClient:
    def __init__(self, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
            return

        try:
            import boto3

            self._client = boto3.client("secretsmanager")
        except Exception:
            raise DependencyUnavailable(SECRETS_MANAGER_ERROR) from None

    def get_secret_value(self, *, SecretId: str) -> Mapping[str, Any]:
        return self._client.get_secret_value(SecretId=SecretId)


@dataclass(frozen=True)
class DatabaseCredentials:
    username: str
    password: str = field(repr=False)


class _ProcessCache:
    def __init__(self, ttl_seconds: float, clock: Callable[[], float]) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._expires_at = 0.0
        self._value: Any = None
        self._lock = threading.Lock()

    def get(self) -> Any | None:
        with self._lock:
            if self._value is not None and self._clock() < self._expires_at:
                return self._value
            self._value = None
            return None

    def set(self, value: Any) -> Any:
        with self._lock:
            self._value = value
            self._expires_at = self._clock() + self._ttl_seconds
            return value

    def invalidate(self) -> None:
        with self._lock:
            self._value = None
            self._expires_at = 0.0


class SecretsManagerDatabaseCredentialsProvider:
    def __init__(
        self,
        client: SecretsManagerClient,
        secret_id: str,
        *,
        expected_username: str = "oficina_auth",
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._secret_id = secret_id
        self._expected_username = expected_username
        self._cache = _ProcessCache(cache_ttl_seconds, clock)

    def get_credentials(self) -> DatabaseCredentials:
        cached = self._cache.get()
        if cached is not None:
            return cached

        try:
            response = self._client.get_secret_value(SecretId=self._secret_id)
            payload = _parse_json_secret(response)
            username = payload.get("username")
            password = payload.get("password")
            if (
                not isinstance(username, str)
                or not username.strip()
                or not isinstance(password, str)
                or not password.strip()
                or username != self._expected_username
            ):
                raise ValueError
            return self._cache.set(DatabaseCredentials(username=username, password=password))
        except DependencyUnavailable:
            raise
        except Exception:
            self._cache.invalidate()
            raise DependencyUnavailable(SECRETS_MANAGER_ERROR) from None

    def invalidate(self) -> None:
        self._cache.invalidate()


class SecretsManagerPrivateKeyProvider:
    def __init__(
        self,
        client: SecretsManagerClient,
        secret_id: str,
        *,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._secret_id = secret_id
        self._cache = _ProcessCache(cache_ttl_seconds, clock)

    def get_private_key(self) -> str:
        cached = self._cache.get()
        if cached is not None:
            return cached

        try:
            response = self._client.get_secret_value(SecretId=self._secret_id)
            secret = _parse_string_secret(response)
            return self._cache.set(secret)
        except DependencyUnavailable:
            raise
        except Exception:
            self._cache.invalidate()
            raise DependencyUnavailable(SECRETS_MANAGER_ERROR) from None

    def invalidate(self) -> None:
        self._cache.invalidate()


def _parse_json_secret(response: Mapping[str, Any]) -> dict[str, Any]:
    secret = _parse_string_secret(response)
    payload = json.loads(secret)
    if not isinstance(payload, dict):
        raise ValueError
    return payload


def _parse_string_secret(response: Mapping[str, Any]) -> str:
    if not isinstance(response, Mapping):
        raise ValueError
    secret = response.get("SecretString")
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError
    return secret

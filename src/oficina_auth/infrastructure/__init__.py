"""Infrastructure adapter boundaries for authentication."""

from oficina_auth.infrastructure.in_memory_client_repository import InMemoryClientRepository
from oficina_auth.infrastructure.jwt_tokens import Rs256TokenIssuer, TokenClaims, TokenVerifier
from oficina_auth.infrastructure.postgres_client_repository import (
    PostgresClientRepository,
    PostgresRepositoryConfig,
)
from oficina_auth.infrastructure.secrets_manager import (
    Boto3SecretsManagerClient,
    DatabaseCredentials,
    SecretsManagerDatabaseCredentialsProvider,
    SecretsManagerPrivateKeyProvider,
)

__all__ = [
    "Boto3SecretsManagerClient",
    "DatabaseCredentials",
    "InMemoryClientRepository",
    "PostgresClientRepository",
    "PostgresRepositoryConfig",
    "Rs256TokenIssuer",
    "SecretsManagerDatabaseCredentialsProvider",
    "SecretsManagerPrivateKeyProvider",
    "TokenClaims",
    "TokenVerifier",
]

"""Domain model boundaries for authentication."""

from oficina_auth.domain.client import AuthenticationRecord, ClientAuthRecord
from oficina_auth.domain.cpf import CPF
from oficina_auth.domain.exceptions import DependencyUnavailable, InvalidCredentials, InvalidInput

__all__ = [
    "AuthenticationRecord",
    "ClientAuthRecord",
    "CPF",
    "DependencyUnavailable",
    "InvalidCredentials",
    "InvalidInput",
]

from __future__ import annotations

from typing import Protocol

from oficina_auth.domain.client import AuthenticationRecord
from oficina_auth.domain.cpf import CPF


class ClientRepository(Protocol):
    def find_by_cpf(self, cpf: CPF) -> AuthenticationRecord | None:
        raise NotImplementedError


class TokenIssuer(Protocol):
    def issue(self, cliente_id: str) -> str:
        raise NotImplementedError

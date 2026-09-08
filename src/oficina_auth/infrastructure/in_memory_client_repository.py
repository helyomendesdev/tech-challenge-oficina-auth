from oficina_auth.domain.client import AuthenticationRecord
from oficina_auth.domain.cpf import CPF


class InMemoryClientRepository:
    def __init__(self, records: dict[str, AuthenticationRecord] | None = None) -> None:
        self._records = records or {}

    def find_by_cpf(self, cpf: CPF) -> AuthenticationRecord | None:
        return self._records.get(cpf.digits)

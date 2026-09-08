import logging

import pytest

from oficina_auth.application import AuthenticateClient
from oficina_auth.application.authenticate_client import AuthenticationResult
from oficina_auth.domain import (
    AuthenticationRecord,
    DependencyUnavailable,
    InvalidCredentials,
    InvalidInput,
)
from oficina_auth.domain.cpf import CPF
from oficina_auth.infrastructure import InMemoryClientRepository

VALID_CPF = "52998224725"
TOKEN = "synthetic.jwt.value"


class StubTokenIssuer:
    def __init__(self) -> None:
        self.issued_for: list[str] = []

    def issue(self, cliente_id: str) -> str:
        self.issued_for.append(cliente_id)
        return TOKEN


class FailingClientRepository:
    def find_by_cpf(self, cpf: CPF) -> AuthenticationRecord | None:
        raise RuntimeError(f"database error for {cpf.digits}")


def test_client_does_not_exist_raises_generic_invalid_credentials() -> None:
    token_issuer = StubTokenIssuer()
    use_case = AuthenticateClient(InMemoryClientRepository(), token_issuer)

    with pytest.raises(
        InvalidCredentials, match="Credenciais invalidas ou cliente nao elegivel\\."
    ):
        use_case.execute(VALID_CPF)

    assert token_issuer.issued_for == []


def test_client_cannot_authenticate_raises_same_generic_error() -> None:
    token_issuer = StubTokenIssuer()
    repository = InMemoryClientRepository(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=False)}
    )
    use_case = AuthenticateClient(repository, token_issuer)

    with pytest.raises(
        InvalidCredentials, match="Credenciais invalidas ou cliente nao elegivel\\."
    ):
        use_case.execute(VALID_CPF)

    assert token_issuer.issued_for == []


def test_eligible_client_receives_token() -> None:
    token_issuer = StubTokenIssuer()
    repository = InMemoryClientRepository(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=True)}
    )
    use_case = AuthenticateClient(repository, token_issuer)

    result = use_case.execute(VALID_CPF)

    assert result == AuthenticationResult(access_token=TOKEN)
    assert result.token_type == "Bearer"
    assert result.expires_in == 900
    assert token_issuer.issued_for == ["cliente-001"]


def test_invalid_cpf_raises_invalid_input() -> None:
    use_case = AuthenticateClient(InMemoryClientRepository(), StubTokenIssuer())

    with pytest.raises(InvalidInput, match="CPF invalido\\."):
        use_case.execute("11111111111")


def test_missing_cpf_raises_invalid_input() -> None:
    use_case = AuthenticateClient(InMemoryClientRepository(), StubTokenIssuer())

    with pytest.raises(InvalidInput, match="CPF invalido\\."):
        use_case.execute(None)


def test_repository_failure_raises_dependency_unavailable_without_cause() -> None:
    use_case = AuthenticateClient(FailingClientRepository(), StubTokenIssuer())

    with pytest.raises(
        DependencyUnavailable, match="Dependencia temporariamente indisponivel\\."
    ) as exc_info:
        use_case.execute(VALID_CPF)

    assert exc_info.value.__cause__ is None
    assert VALID_CPF not in str(exc_info.value)


def test_does_not_log_or_repr_full_cpf_or_token(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    token_issuer = StubTokenIssuer()
    repository = InMemoryClientRepository(
        {VALID_CPF: AuthenticationRecord(cliente_id="cliente-001", can_authenticate=True)}
    )
    use_case = AuthenticateClient(repository, token_issuer)

    result = use_case.execute("529.982.247-25")

    assert VALID_CPF not in repr(result)
    assert TOKEN not in repr(result)
    assert not caplog.records

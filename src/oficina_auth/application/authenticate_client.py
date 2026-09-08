from dataclasses import dataclass, field

from oficina_auth.application.ports import ClientRepository, TokenIssuer
from oficina_auth.domain.cpf import CPF
from oficina_auth.domain.exceptions import DependencyUnavailable, InvalidCredentials, InvalidInput


@dataclass(frozen=True)
class AuthenticationResult:
    access_token: str = field(repr=False)
    token_type: str = "Bearer"
    expires_in: int = 900


class AuthenticateClient:
    def __init__(self, client_repository: ClientRepository, token_issuer: TokenIssuer) -> None:
        self._client_repository = client_repository
        self._token_issuer = token_issuer

    def execute(self, cpf_value: str | None) -> AuthenticationResult:
        if cpf_value is None:
            raise InvalidInput("CPF invalido.")

        cpf = CPF(cpf_value)

        try:
            client = self._client_repository.find_by_cpf(cpf)
        except DependencyUnavailable:
            raise
        except Exception:
            raise DependencyUnavailable("Dependencia temporariamente indisponivel.") from None

        if client is None or not client.can_authenticate:
            raise InvalidCredentials("Credenciais invalidas ou cliente nao elegivel.")

        access_token = self._token_issuer.issue(client.cliente_id)
        return AuthenticationResult(access_token=access_token)

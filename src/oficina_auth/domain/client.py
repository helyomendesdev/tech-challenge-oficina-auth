from dataclasses import dataclass


@dataclass(frozen=True)
class ClientAuthRecord:
    cliente_id: str
    can_authenticate: bool


# Backward-compatible name used by the initial domain implementation.
AuthenticationRecord = ClientAuthRecord

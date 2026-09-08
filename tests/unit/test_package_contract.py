import oficina_auth
from oficina_auth.domain import AuthenticationRecord, ClientAuthRecord


def test_package_exposes_version() -> None:
    assert oficina_auth.__version__ == "0.1.0"


def test_client_auth_record_exposes_minimal_client_identity() -> None:
    record = ClientAuthRecord(cliente_id="cliente-001", can_authenticate=True)

    assert record.cliente_id == "cliente-001"
    assert record.can_authenticate is True
    assert AuthenticationRecord is ClientAuthRecord

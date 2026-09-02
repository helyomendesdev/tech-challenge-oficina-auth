import pytest

from oficina_auth.domain import CPF, InvalidInput

VALID_CPF_DIGITS = "52998224725"
VALID_CPF_FORMATTED = "529.982.247-25"


def test_accepts_valid_cpf_with_digits_only() -> None:
    cpf = CPF(VALID_CPF_DIGITS)

    assert cpf.digits == VALID_CPF_DIGITS
    assert str(cpf) == VALID_CPF_DIGITS


def test_accepts_valid_formatted_cpf() -> None:
    cpf = CPF(VALID_CPF_FORMATTED)

    assert cpf.digits == VALID_CPF_DIGITS


def test_rejects_invalid_first_check_digit() -> None:
    with pytest.raises(InvalidInput, match="CPF invalido\\."):
        CPF("52998224735")


def test_rejects_invalid_second_check_digit() -> None:
    with pytest.raises(InvalidInput, match="CPF invalido\\."):
        CPF("52998224726")


def test_rejects_repeated_sequences() -> None:
    with pytest.raises(InvalidInput, match="CPF invalido\\."):
        CPF("11111111111")


def test_rejects_invalid_length() -> None:
    with pytest.raises(InvalidInput, match="CPF invalido\\."):
        CPF("5299822472")


def test_rejects_forbidden_character() -> None:
    with pytest.raises(InvalidInput, match="CPF invalido\\."):
        CPF("529.982.247-2A")


def test_does_not_expose_full_cpf_in_repr_or_errors() -> None:
    cpf = CPF(VALID_CPF_FORMATTED)

    assert VALID_CPF_DIGITS not in repr(cpf)
    assert VALID_CPF_FORMATTED not in repr(cpf)

    with pytest.raises(InvalidInput) as exc_info:
        CPF("529.982.247-2A")

    assert "529" not in str(exc_info.value)
    assert "247" not in str(exc_info.value)
    assert "2A" not in str(exc_info.value)

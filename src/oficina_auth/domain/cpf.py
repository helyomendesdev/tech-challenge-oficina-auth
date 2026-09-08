from __future__ import annotations

import re
from dataclasses import dataclass

from oficina_auth.domain.exceptions import InvalidInput

_CPF_FORMAT = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$")
_DIGITS_ONLY = re.compile(r"\D")


@dataclass(frozen=True)
class CPF:
    digits: str

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise InvalidInput("CPF invalido.")

        if not _CPF_FORMAT.fullmatch(value):
            raise InvalidInput("CPF invalido.")

        digits = _DIGITS_ONLY.sub("", value)
        if len(digits) != 11:
            raise InvalidInput("CPF invalido.")

        if len(set(digits)) == 1:
            raise InvalidInput("CPF invalido.")

        if not self._has_valid_check_digits(digits):
            raise InvalidInput("CPF invalido.")

        object.__setattr__(self, "digits", digits)

    def __str__(self) -> str:
        return self.digits

    def __repr__(self) -> str:
        return "CPF(masked='***')"

    @staticmethod
    def _has_valid_check_digits(digits: str) -> bool:
        first_digit = CPF._calculate_digit(digits[:9], start_weight=10)
        second_digit = CPF._calculate_digit(digits[:9] + str(first_digit), start_weight=11)

        return digits[-2:] == f"{first_digit}{second_digit}"

    @staticmethod
    def _calculate_digit(base_digits: str, start_weight: int) -> int:
        total = sum(
            int(digit) * weight
            for digit, weight in zip(base_digits, range(start_weight, 1, -1), strict=True)
        )
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

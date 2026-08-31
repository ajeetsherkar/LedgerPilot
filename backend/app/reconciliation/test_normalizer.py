from decimal import Decimal

import pytest

from backend.app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_reference,
)


def test_normalize_amount_with_currency_and_commas():
    assert normalize_amount("₹1,234.50") == Decimal("1234.50")


def test_normalize_amount_with_dollar():
    assert normalize_amount("$1,234.50") == Decimal("1234.50")


def test_normalize_amount_plain_value():
    assert normalize_amount("4512") == Decimal("4512.00")


def test_normalize_amount_negative_parentheses():
    assert normalize_amount("(1,234.50)") == Decimal("-1234.50")


def test_normalize_invalid_amount():
    with pytest.raises(ValueError):
        normalize_amount("not-an-amount")


def test_normalize_date_iso():
    assert normalize_date("2026-08-24") == "2026-08-24"


def test_normalize_date_slash():
    assert normalize_date("24/08/2026") == "2026-08-24"


def test_normalize_date_dash():
    assert normalize_date("24-08-2026") == "2026-08-24"


def test_normalize_date_us_format():
    assert normalize_date("08/24/2026") == "2026-08-24"


def test_normalize_invalid_date():
    with pytest.raises(ValueError):
        normalize_date("not-a-date")


def test_normalize_reference_dash():
    assert normalize_reference("SET-441") == "SET441"


def test_normalize_reference_underscore():
    assert normalize_reference("SET_441") == "SET441"


def test_normalize_reference_rzp_prefix():
    assert normalize_reference("RZP SET-441") == "SET441"


def test_normalize_reference_rzp_with_separator():
    assert normalize_reference("RZP/SET-441") == "SET441"


def test_normalize_reference_is_case_insensitive():
    assert normalize_reference("set-441") == "SET441"

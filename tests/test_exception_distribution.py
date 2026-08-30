from scripts.exceptions import DEFAULT_EXCEPTION_RATES


def test_exception_rates_total_30_percent():
    total = sum(DEFAULT_EXCEPTION_RATES.values())

    assert abs(total - 0.30) < 1e-9


def test_exception_rates_are_valid():
    for name, rate in DEFAULT_EXCEPTION_RATES.items():
        assert 0 <= rate <= 1
        assert name in {
            "date_drift",
            "amount_mismatch",
            "missing_bank",
            "duplicate",
            "fuzzy_reference",
            "partial_settlement",
            "combined_settlement",
        }

import random

from scripts.generate_data import generate_dataset
from scripts.exceptions import (
    apply_exceptions,
    DEFAULT_EXCEPTION_RATES,
)


def _rates_only(exception_name):
    rates = {name: 0 for name in DEFAULT_EXCEPTION_RATES}
    rates[exception_name] = DEFAULT_EXCEPTION_RATES[exception_name]
    return rates


def test_date_drift_rate_is_actually_applied():
    n = 1000

    orders, payments, settlements, banks = generate_dataset(n)

    _, _, corrupted_settlements, corrupted_banks = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        rates=_rates_only("date_drift"),
    )

    changed = sum(
        original["settlement_date"]
        != corrupted["settlement_date"]
        for original, corrupted in zip(
            settlements,
            corrupted_settlements,
        )
    )

    expected = int(n * DEFAULT_EXCEPTION_RATES["date_drift"])

    assert changed == expected


def test_amount_mismatch_rate_is_actually_applied():
    n = 1000

    orders, payments, settlements, banks = generate_dataset(n)

    _, _, _, corrupted_banks = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        rates=_rates_only("amount_mismatch"),
    )

    changed = sum(
        original["credit_amount"]
        != corrupted["credit_amount"]
        for original, corrupted in zip(
            banks,
            corrupted_banks,
        )
    )

    expected = int(n * DEFAULT_EXCEPTION_RATES["amount_mismatch"])

    assert changed == expected


def test_missing_bank_rate_is_actually_applied():
    n = 1000

    orders, payments, settlements, banks = generate_dataset(n)

    _, _, _, corrupted_banks = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        rates=_rates_only("missing_bank"),
    )

    expected = int(n * DEFAULT_EXCEPTION_RATES["missing_bank"])

    assert len(banks) - len(corrupted_banks) == expected


def test_duplicate_rate_is_actually_applied():
    n = 1000

    orders, payments, settlements, banks = generate_dataset(n)

    _, _, corrupted_settlements, corrupted_banks = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        rates=_rates_only("duplicate"),
    )

    expected = int(n * DEFAULT_EXCEPTION_RATES["duplicate"])

    assert len(corrupted_settlements) - len(settlements) == expected
    assert len(corrupted_banks) - len(banks) == expected


def test_fuzzy_reference_rate_is_actually_applied():
    n = 1000

    orders, payments, settlements, banks = generate_dataset(n)

    _, _, corrupted_settlements, _ = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        rates=_rates_only("fuzzy_reference"),
    )

    changed = sum(
        original["settlement_reference"]
        != corrupted["settlement_reference"]
        for original, corrupted in zip(
            settlements,
            corrupted_settlements,
        )
    )

    expected = int(n * DEFAULT_EXCEPTION_RATES["fuzzy_reference"])

    assert changed == expected


def test_partial_settlement_rate_is_actually_applied():
    n = 1000

    orders, payments, settlements, banks = generate_dataset(n)

    _, _, corrupted_settlements, _ = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        rates=_rates_only("partial_settlement"),
    )

    expected = int(n * DEFAULT_EXCEPTION_RATES["partial_settlement"])

    assert len(corrupted_settlements) - len(settlements) == expected


def test_combined_settlement_rate_is_actually_applied():
    n = 1000

    orders, payments, settlements, banks = generate_dataset(n)

    _, _, _, corrupted_banks = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        rates=_rates_only("combined_settlement"),
    )

    expected = int(
        n * DEFAULT_EXCEPTION_RATES["combined_settlement"]
    )

    expected_combinations = expected // 2

    assert len(banks) - len(corrupted_banks) == expected_combinations
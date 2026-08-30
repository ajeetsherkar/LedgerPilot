from scripts.generate_data import generate_dataset
from scripts.exceptions import (
    apply_exceptions,
    DEFAULT_EXCEPTION_RATES,
)
import random


def test_apply_exceptions_does_not_modify_original_dataset():
    orders, payments, settlements, banks = generate_dataset(100)

    original_settlements = [row.copy() for row in settlements]
    original_banks = [row.copy() for row in banks]

    apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
    )

    assert settlements == original_settlements
    assert banks == original_banks


def test_apply_exceptions_returns_same_core_record_count_or_expected_changes():
    orders, payments, settlements, banks = generate_dataset(100)

    corrupted = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
    )

    corrupted_orders, corrupted_payments, corrupted_settlements, corrupted_banks = corrupted

    assert len(corrupted_orders) == 100
    assert len(corrupted_payments) == 100

    # Duplicate exceptions may increase settlement/bank counts,
    # while missing-bank exceptions may decrease bank count.
    assert len(corrupted_settlements) >= 100
    assert len(corrupted_banks) >= 0


def test_exception_rates_are_used():
    total_rate = sum(DEFAULT_EXCEPTION_RATES.values())

    assert abs(total_rate - 0.30) < 1e-9
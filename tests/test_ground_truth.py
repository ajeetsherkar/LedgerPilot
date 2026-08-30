from copy import deepcopy
import random

from scripts.generate_data import generate_dataset
from scripts.exceptions import apply_exceptions


def test_clean_data_remains_untouched():
    """
    Ground truth rule:
    apply_exceptions() must never modify the original clean dataset.
    """

    orders, payments, settlements, banks = generate_dataset(100)

    original_orders = deepcopy(orders)
    original_payments = deepcopy(payments)
    original_settlements = deepcopy(settlements)
    original_banks = deepcopy(banks)

    apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
    )

    assert orders == original_orders
    assert payments == original_payments
    assert settlements == original_settlements
    assert banks == original_banks


def test_corrupted_data_is_separate_from_clean_data():
    """
    Ground truth rule:
    corruption must be applied to a copy of clean data.
    The returned corrupted data must be a separate object.
    """

    orders, payments, settlements, banks = generate_dataset(100)

    (
        corrupted_orders,
        corrupted_payments,
        corrupted_settlements,
        corrupted_banks,
    ) = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
    )

    assert corrupted_orders is not orders
    assert corrupted_payments is not payments
    assert corrupted_settlements is not settlements
    assert corrupted_banks is not banks


def test_original_relationships_remain_available_as_ground_truth():
    """
    The clean dataset remains the authoritative source of the
    original payment -> settlement -> bank relationships.

    Corruption must not destroy the clean reference dataset.
    """

    orders, payments, settlements, banks = generate_dataset(100)

    original_settlement_by_payment = {
        settlement["payment_id"]: settlement
        for settlement in settlements
    }

    original_bank_by_reference = {
        bank["reference"]: bank
        for bank in banks
    }

    (
        _,
        _,
        corrupted_settlements,
        corrupted_banks,
    ) = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
    )

    # Every original payment still has its clean settlement available.
    for payment_id, settlement in original_settlement_by_payment.items():
        assert settlement["payment_id"] == payment_id

    # Every original settlement still has its original bank relationship.
    for reference, bank in original_bank_by_reference.items():
        assert bank["reference"] == reference

    # The corrupted dataset is allowed to differ, but the clean
    # relationships remain available through the original data.
    assert len(corrupted_settlements) >= len(settlements)
    assert len(corrupted_banks) <= len(banks) + len(corrupted_settlements)


def test_corruption_can_be_compared_against_ground_truth():
    """
    Verify that clean and corrupted datasets can be compared to
    identify intentional changes.
    """

    orders, payments, settlements, banks = generate_dataset(100)

    (
        _,
        _,
        corrupted_settlements,
        corrupted_banks,
    ) = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
    )

    settlement_changes = [
        settlement
        for settlement in corrupted_settlements
        if settlement not in settlements
    ]

    bank_changes = [
        bank
        for bank in corrupted_banks
        if bank not in banks
    ]

    # With the default corruption configuration, at least some
    # corrupted records should be distinguishable from clean data.
    assert settlement_changes or bank_changes

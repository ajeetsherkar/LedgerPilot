from scripts.generate_data import generate_dataset

from scripts.exceptions import (
    apply_duplicate,
    apply_fuzzy_reference,
    apply_partial_settlement,
    apply_combined_settlement,
)


def test_duplicate_creates_extra_settlement_and_bank():
    _, _, settlements, banks = generate_dataset(10)

    original_settlements = len(settlements)
    original_banks = len(banks)

    result = apply_duplicate(
        settlements,
        banks,
        0,
    )

    assert result is True
    assert len(settlements) == original_settlements + 1
    assert len(banks) == original_banks + 1


def test_fuzzy_reference_changes_reference():
    _, _, settlements, banks = generate_dataset(10)

    original_reference = settlements[0]["settlement_reference"]

    result = apply_fuzzy_reference(
        settlements[0],
        banks[0],
    )

    assert result is True
    assert settlements[0]["settlement_reference"] != original_reference


def test_partial_settlement_creates_multiple_records_for_payment():
    _, payments, settlements, _ = generate_dataset(10)

    original_payment_id = settlements[0]["payment_id"]
    original_count = len(settlements)

    result = apply_partial_settlement(
        settlements,
        0,
    )

    assert result is True
    assert len(settlements) == original_count + 1

    matching = [
        row
        for row in settlements
        if row["payment_id"] == original_payment_id
    ]

    assert len(matching) == 2


def test_combined_settlement_creates_one_bank_record():
    _, _, settlements, banks = generate_dataset(10)

    original_bank_count = len(banks)

    result = apply_combined_settlement(
        settlements,
        banks,
        0,
        1,
    )

    assert result is True
    assert len(banks) == original_bank_count - 1

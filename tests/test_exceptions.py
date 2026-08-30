from datetime import timedelta

from backend.app.reconciliation.exceptions import classify_exception
from backend.app.reconciliation.models import ReconciliationResult


def make_result(
    payment_status="MATCHED",
    settlement_status="MATCHED",
    bank_status="MATCHED",
    reconciliation_status="MATCHED",
):
    return ReconciliationResult(
        order_id="TEST001",
        payment_status=payment_status,
        settlement_status=settlement_status,
        bank_status=bank_status,
        expected_amount=1000.0,
        paid_amount=1000.0,
        settled_amount=1000.0,
        bank_amount=1000.0,
        difference=0.0,
        reconciliation_status=reconciliation_status,
        exception_type="MATCHED",
    )


def test_matched_result():
    result = make_result()

    assert classify_exception(result) == "MATCHED"


def test_payment_mismatch():
    result = make_result(
        payment_status="MISMATCH",
        reconciliation_status="EXCEPTION",
    )

    assert classify_exception(result) == "PAYMENT_MISMATCH"


def test_settlement_mismatch():
    result = make_result(
        settlement_status="MISMATCH",
        reconciliation_status="EXCEPTION",
    )

    assert classify_exception(result) == "SETTLEMENT_MISMATCH"


def test_bank_mismatch():
    result = make_result(
        bank_status="MISMATCH",
        reconciliation_status="EXCEPTION",
    )

    assert classify_exception(result) == "BANK_MISMATCH"


def test_date_drift_changes_settlement_and_bank_dates_only():
    from scripts.generate_data import generate_dataset
    from scripts.exceptions import apply_date_drift

    orders, payments, settlements, banks = generate_dataset(50)

    original_settlement_date = settlements[0]["settlement_date"]
    original_bank_date = banks[0]["transaction_date"]

    original_net_amount = settlements[0]["net_amount"]
    original_platform_fee = settlements[0]["platform_fee"]
    original_gst_on_fee = settlements[0]["gst_on_fee"]
    original_reference = settlements[0]["settlement_reference"]
    original_bank_reference = banks[0]["reference"]

    apply_date_drift(
        settlements[0],
        banks[0],
        days=3,
    )

    assert settlements[0]["settlement_date"] == (
        original_settlement_date + timedelta(days=3)
    )

    assert banks[0]["transaction_date"] == (
        original_bank_date + timedelta(days=3)
    )

    # Amounts must remain unchanged.
    assert settlements[0]["net_amount"] == original_net_amount

    assert settlements[0]["platform_fee"] == original_platform_fee

    assert settlements[0]["gst_on_fee"] == original_gst_on_fee

    # References must remain unchanged.
    assert settlements[0]["settlement_reference"] == original_reference

    assert banks[0]["reference"] == original_bank_reference

    # Bank amount must still equal settlement net amount.
    assert banks[0]["credit_amount"] == settlements[0]["net_amount"]


def test_missing_bank_removes_only_corresponding_bank_record():
    from scripts.generate_data import generate_dataset
    from scripts.exceptions import apply_missing_bank

    orders, payments, settlements, banks = generate_dataset(50)

    original_bank_count = len(banks)
    target_settlement = settlements[0]
    target_reference = target_settlement["settlement_reference"]

    original_settlement = target_settlement.copy()

    removed = apply_missing_bank(
        target_settlement,
        banks,
    )

    assert removed is True

    # Exactly one bank record must be removed.
    assert len(banks) == original_bank_count - 1

    # Settlement must remain unchanged.
    assert target_settlement == original_settlement

    # The corresponding bank reference must no longer exist.
    assert all(
        bank["reference"] != target_reference
        for bank in banks
    )


def test_amount_mismatch_changes_bank_amount_only():
    from scripts.generate_data import generate_dataset
    from scripts.exceptions import apply_amount_mismatch

    orders, payments, settlements, banks = generate_dataset(50)

    original_bank_amount = banks[0]["credit_amount"]
    original_bank_reference = banks[0]["reference"]
    original_bank_date = banks[0]["transaction_date"]

    original_settlement_amount = settlements[0]["net_amount"]
    original_settlement_reference = settlements[0]["settlement_reference"]

    apply_amount_mismatch(
        banks[0],
        amount_difference=50,
    )

    # Bank amount must change.
    assert banks[0]["credit_amount"] == original_bank_amount - 50

    # Bank reference/date must remain unchanged.
    assert banks[0]["reference"] == original_bank_reference
    assert banks[0]["transaction_date"] == original_bank_date

    # Settlement must remain unchanged.
    assert settlements[0]["net_amount"] == original_settlement_amount
    assert settlements[0]["settlement_reference"] == original_settlement_reference
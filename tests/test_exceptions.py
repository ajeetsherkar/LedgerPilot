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
from .models import ReconciliationResult


def classify_exception(result: ReconciliationResult) -> str:
    """
    Classify a reconciliation result into a specific exception type.
    """

    if result.reconciliation_status == "MATCHED":
        return "MATCHED"

    if result.payment_status != "MATCHED":
        return "PAYMENT_MISMATCH"

    if result.settlement_status != "MATCHED":
        return "SETTLEMENT_MISMATCH"

    if result.bank_status != "MATCHED":
        return "BANK_MISMATCH"

    return "MISMATCH"
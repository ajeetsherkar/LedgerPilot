from datetime import date
from typing import Optional

from backend.app.reconciliation.relationship_builder import TransactionChain
from backend.app.reconciliation.exception_types import ExceptionType
from backend.app.reconciliation.normalizer import normalize_date


PAYMENT_TO_SETTLEMENT_MAX_DAYS = 3
SETTLEMENT_TO_BANK_MAX_DAYS = 2


def _parse_date(value) -> date:
    normalized = normalize_date(value)

    year, month, day = map(
        int,
        normalized.split("-"),
    )

    return date(year, month, day)


def _date_window_valid(
    start,
    end,
    max_days: int,
) -> bool:
    try:
        start_date = _parse_date(start)
        end_date = _parse_date(end)
    except (TypeError, ValueError):
        return False

    difference = (
        end_date - start_date
    ).days

    return 0 <= difference <= max_days


def _has_partial_settlement(
    chain: TransactionChain,
) -> bool:
    """
    PARTIAL_SETTLEMENT means:

        one payment -> multiple settlement records

    The synthetic generator creates two settlement records with
    the same payment_id.
    """

    settlements = chain.related_settlements or []

    if chain.payment is None:
        return False

    payment_id = str(
        chain.payment.get("payment_id")
    )

    payment_settlements = [
        settlement
        for settlement in settlements
        if str(settlement.get("payment_id"))
        == payment_id
    ]

    return len(payment_settlements) > 1


def _has_combined_settlement(
    chain: TransactionChain,
) -> bool:
    """
    COMBINED_SETTLEMENT means:

        multiple payments -> one bank credit

    The synthetic corruption marks the resulting bank reference
    as:

        COMBINED-<reference1>-<reference2>
    """

    if chain.bank is None:
        return False

    reference = str(
        chain.bank.get("reference", "")
    )

    if reference.startswith("COMBINED-"):
        return True

    narration = str(
        chain.bank.get("narration", "")
    ).lower()

    return narration.startswith(
        "combined settlement for"
    )


def _has_date_mismatch(
    chain: TransactionChain,
) -> bool:
    """
    DATE_MISMATCH means the transaction chain violates the
    configured settlement timing windows.

    Rules:

        Order <= Payment
        Payment -> Settlement <= 3 days
        Settlement -> Bank <= 2 days
    """

    if (
        chain.order is None
        or chain.payment is None
        or chain.settlement is None
        or chain.bank is None
    ):
        return False

    try:
        order_date = _parse_date(
            chain.order["order_date"]
        )

        payment_date = _parse_date(
            chain.payment["payment_date"]
        )

        settlement_date = _parse_date(
            chain.settlement["settlement_date"]
        )

        bank_date = _parse_date(
            chain.bank["transaction_date"]
        )
    except (KeyError, TypeError, ValueError):
        return False

    if payment_date < order_date:
        return True

    if not _date_window_valid(
        payment_date,
        settlement_date,
        PAYMENT_TO_SETTLEMENT_MAX_DAYS,
    ):
        return True

    if not _date_window_valid(
        settlement_date,
        bank_date,
        SETTLEMENT_TO_BANK_MAX_DAYS,
    ):
        return True

    return False


def classify_chain_exception(
    chain: TransactionChain,
) -> Optional[ExceptionType]:

    if not isinstance(chain, TransactionChain):
        raise TypeError(
            "chain must be a TransactionChain"
        )

    # ---------------------------------------------------------
    # 1. REQUIRED TRANSACTION DATA
    # ---------------------------------------------------------

    if chain.order is None:
        return ExceptionType.AMOUNT_MISMATCH

    if chain.payment is None:
        return ExceptionType.MISSING_PAYMENT

    if chain.settlement is None:
        return ExceptionType.MISSING_SETTLEMENT

    # ---------------------------------------------------------
    # 2. MULTI-SETTLEMENT EXCEPTIONS
    # ---------------------------------------------------------

    # Must happen before normal settlement/bank amount checks.
    if _has_partial_settlement(chain):
        return ExceptionType.PARTIAL_SETTLEMENT

    # ---------------------------------------------------------
    # 3. COMBINED SETTLEMENT
    # ---------------------------------------------------------

    # Must happen before bank amount mismatch because one bank
    # credit intentionally represents multiple payments.
    if _has_combined_settlement(chain):
        return ExceptionType.COMBINED_SETTLEMENT

    # ---------------------------------------------------------
    # 4. MISSING BANK
    # ---------------------------------------------------------

    if chain.bank is None:
        return ExceptionType.MISSING_BANK_RECORD

    # ---------------------------------------------------------
    # 5. DUPLICATE BANK TRANSACTION
    # ---------------------------------------------------------

    if chain.duplicate_bank_transactions:
        return ExceptionType.DUPLICATE_BANK_TRANSACTION

    # ---------------------------------------------------------
    # 6. ORDER -> PAYMENT AMOUNT
    # ---------------------------------------------------------

    try:
        order_amount = float(
            chain.order["order_amount"]
        )

        payment_amount = float(
            chain.payment["amount"]
        )

        if round(order_amount, 2) != round(
            payment_amount,
            2,
        ):
            return ExceptionType.AMOUNT_MISMATCH

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return ExceptionType.AMOUNT_MISMATCH

    # ---------------------------------------------------------
    # 7. SETTLEMENT INTERNAL VALIDATION
    # ---------------------------------------------------------

    try:
        settled_amount = float(
            chain.settlement["net_amount"]
        )

        gross_amount = float(
            chain.settlement["gross_amount"]
        )

        expected_fee = round(
            gross_amount * 0.01,
            2,
        )

        expected_gst = round(
            expected_fee * 0.18,
            2,
        )

        expected_settlement = round(
            gross_amount
            - expected_fee
            - expected_gst,
            2,
        )

        settlement_is_valid = (
            round(settled_amount, 2)
            == expected_settlement
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        settled_amount = None
        settlement_is_valid = False

    # ---------------------------------------------------------
    # 8. SETTLEMENT -> BANK AMOUNT
    # ---------------------------------------------------------

    if settlement_is_valid:

        bank_credit_amount = chain.bank.get(
            "credit_amount"
        )

        if bank_credit_amount is None:
            return ExceptionType.AMOUNT_MISMATCH

        try:
            bank_amount = float(
                bank_credit_amount
            )

            if round(bank_amount, 2) != round(
                settled_amount,
                2,
            ):
                return ExceptionType.AMOUNT_MISMATCH

        except (
            TypeError,
            ValueError,
        ):
            return ExceptionType.AMOUNT_MISMATCH

    # ---------------------------------------------------------
    # 9. REFERENCE
    # ---------------------------------------------------------

    settlement_reference = (
        chain.settlement.get(
            "settlement_reference"
        )
    )

    bank_reference = chain.bank.get(
        "reference"
    )

    if (
        settlement_reference is None
        or bank_reference is None
        or settlement_reference != bank_reference
    ):
        return ExceptionType.UNKNOWN_REFERENCE

    # ---------------------------------------------------------
    # 10. DATE MISMATCH
    # ---------------------------------------------------------

    if _has_date_mismatch(chain):
        return ExceptionType.DATE_MISMATCH

    # ---------------------------------------------------------
    # 11. NO EXCEPTION
    # ---------------------------------------------------------

    return None
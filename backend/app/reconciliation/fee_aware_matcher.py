from decimal import Decimal
from typing import Any

from backend.app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_reference,
)
from backend.app.reconciliation.relationship_builder import TransactionChain


# Session 5 tolerance.
FEE_AMOUNT_TOLERANCE = Decimal("1.00")


def expected_net_amount(settlement: dict[str, Any]) -> Decimal:
    """
    Calculate the expected settlement net amount:

        gross_amount - platform_fee - gst_on_fee

    Monetary values are normalized before calculation.
    """

    gross_amount = normalize_amount(
        settlement["gross_amount"]
    )

    platform_fee = normalize_amount(
        settlement["platform_fee"]
    )

    gst_on_fee = normalize_amount(
        settlement["gst_on_fee"]
    )

    return (
        gross_amount
        - platform_fee
        - gst_on_fee
    ).quantize(Decimal("0.01"))


def _same_reference(left: Any, right: Any) -> bool:
    """
    Compare transaction references after normalization.
    """

    try:
        return normalize_reference(left) == normalize_reference(right)
    except (TypeError, ValueError):
        return False


def _valid_date_sequence(
    order: dict[str, Any],
    payment: dict[str, Any],
    settlement: dict[str, Any],
    bank: dict[str, Any],
) -> bool:
    """
    Verify chronological transaction flow:

        Order -> Payment -> Settlement -> Bank

    Configurable date windows are introduced in Session 6.
    """

    try:
        order_date = normalize_date(order["order_date"])
        payment_date = normalize_date(payment["payment_date"])
        settlement_date = normalize_date(
            settlement["settlement_date"]
        )
        bank_date = normalize_date(
            bank["transaction_date"]
        )
    except (KeyError, TypeError, ValueError):
        return False

    return (
        order_date
        <= payment_date
        <= settlement_date
        <= bank_date
    )


def fee_aware_match(chain: TransactionChain) -> bool:
    """
    Apply the Session 5 fee-aware matching rule.

    A chain matches only when:

    1. All four records exist.
    2. Order ID links correctly to Payment.
    3. Payment ID links correctly to Settlement.
    4. Settlement reference matches Bank reference.
    5. Order amount matches Payment amount.
    6. Expected net amount calculated from:
           gross - platform fee - GST
       matches bank credit within the configured tolerance.
    7. Transaction dates are chronologically valid.

    This layer is deterministic and performs no AI,
    fuzzy matching, or similarity scoring.
    """

    if (
        chain.order is None
        or chain.payment is None
        or chain.settlement is None
        or chain.bank is None
    ):
        return False

    order = chain.order
    payment = chain.payment
    settlement = chain.settlement
    bank = chain.bank

    # ---------------------------------------------------------
    # 1. ORDER -> PAYMENT ID
    # ---------------------------------------------------------

    if str(payment.get("order_id")) != str(
        order.get("order_id")
    ):
        return False

    # ---------------------------------------------------------
    # 2. PAYMENT -> SETTLEMENT ID
    # ---------------------------------------------------------

    if str(settlement.get("payment_id")) != str(
        payment.get("payment_id")
    ):
        return False

    # ---------------------------------------------------------
    # 3. SETTLEMENT -> BANK REFERENCE
    # ---------------------------------------------------------

    if not _same_reference(
        settlement.get("settlement_reference"),
        bank.get("reference"),
    ):
        return False

    # ---------------------------------------------------------
    # 4. ORDER -> PAYMENT AMOUNT
    # ---------------------------------------------------------

    try:
        order_amount = normalize_amount(
            order["order_amount"]
        )
        payment_amount = normalize_amount(
            payment["amount"]
        )
    except (KeyError, TypeError, ValueError):
        return False

    if order_amount != payment_amount:
        return False

    # ---------------------------------------------------------
    # 5. FEE-AWARE NET AMOUNT -> BANK
    # ---------------------------------------------------------

    try:
        expected_net = expected_net_amount(settlement)
        bank_amount = normalize_amount(
            bank["credit_amount"]
        )
    except (KeyError, TypeError, ValueError):
        return False

    amount_difference = abs(
        bank_amount - expected_net
    )

    if amount_difference > FEE_AMOUNT_TOLERANCE:
        return False

    # ---------------------------------------------------------
    # 6. VALID DATE SEQUENCE
    # ---------------------------------------------------------

    if not _valid_date_sequence(
        order,
        payment,
        settlement,
        bank,
    ):
        return False

    return True


def fee_aware_match_status(
    chain: TransactionChain,
) -> str:
    """
    Return the explicit Session 5 decision:

        MATCH
        UNRESOLVED
    """

    return (
        "MATCH"
        if fee_aware_match(chain)
        else "UNRESOLVED"
    )
from decimal import Decimal
from typing import Any

from backend.app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_reference,
)
from backend.app.reconciliation.relationship_builder import TransactionChain


def _same_amount(left: Any, right: Any) -> bool:
    """
    Compare two monetary values after normalization.
    """
    try:
        return normalize_amount(left) == normalize_amount(right)
    except (TypeError, ValueError):
        return False


def _same_reference(left: Any, right: Any) -> bool:
    """
    Compare references after canonical normalization.
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

    Session 4 only verifies chronological validity.
    Configurable date tolerances are introduced later
    in Session 6.
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


def exact_match(chain: TransactionChain) -> bool:
    """
    Apply the Session 4 deterministic exact matching rule.

    A chain matches only when:

    1. All four records exist.
    2. Order ID links correctly to Payment.
    3. Payment ID links correctly to Settlement.
    4. Settlement reference matches Bank reference.
    5. Order amount exactly matches Payment amount.
    6. Settlement net amount exactly matches Bank credit amount.
    7. Transaction dates are chronologically valid.

    Otherwise the chain remains UNRESOLVED.

    No fuzzy matching, fee-aware matching, scoring, or AI
    logic is performed here.
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
    if str(payment.get("order_id")) != str(order.get("order_id")):
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
    if not _same_amount(
        order.get("order_amount"),
        payment.get("amount"),
    ):
        return False

    # ---------------------------------------------------------
    # 5. SETTLEMENT -> BANK AMOUNT
    # ---------------------------------------------------------
    if not _same_amount(
        settlement.get("net_amount"),
        bank.get("credit_amount"),
    ):
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


def exact_match_status(chain: TransactionChain) -> str:
    """
    Return the explicit Session 4 decision:

        MATCH
        UNRESOLVED
    """
    return "MATCH" if exact_match(chain) else "UNRESOLVED"

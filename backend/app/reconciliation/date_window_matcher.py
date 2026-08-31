from datetime import date
from typing import Any

from backend.app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_reference,
)
from backend.app.reconciliation.relationship_builder import TransactionChain


# Session 6 development-window defaults.
# These values are intentionally configurable and are NOT final
# production/tuned tolerances.
PAYMENT_TO_SETTLEMENT_MAX_DAYS = 3
SETTLEMENT_TO_BANK_MAX_DAYS = 2


def _parse_date(value: Any) -> date:
    """
    Normalize a supported date value and convert it to a date object.
    """
    normalized = normalize_date(value)

    year, month, day = map(int, normalized.split("-"))

    return date(year, month, day)


def _same_reference(left: Any, right: Any) -> bool:
    """
    Compare transaction references after canonical normalization.
    """
    try:
        return normalize_reference(left) == normalize_reference(right)
    except (TypeError, ValueError):
        return False


def _same_amount(left: Any, right: Any) -> bool:
    """
    Compare monetary values after normalization.
    """
    try:
        return normalize_amount(left) == normalize_amount(right)
    except (TypeError, ValueError):
        return False


def _within_date_window(
    start_date: Any,
    end_date: Any,
    max_days: int,
) -> bool:
    """
    Check whether end_date occurs between 0 and max_days
    after start_date, inclusive.

    Examples for max_days=3:

        same day -> valid
        +1 day    -> valid
        +2 days   -> valid
        +3 days   -> valid
        +4 days   -> invalid

    A negative difference is always invalid.
    """
    try:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
    except (TypeError, ValueError):
        return False

    difference = (end - start).days

    return 0 <= difference <= max_days


def valid_date_windows(
    order: dict[str, Any],
    payment: dict[str, Any],
    settlement: dict[str, Any],
    bank: dict[str, Any],
) -> bool:
    """
    Validate the Session 6 date-window rules.

    Order -> Payment:
        Chronological ordering is required.

    Payment -> Settlement:
        0 to PAYMENT_TO_SETTLEMENT_MAX_DAYS days.

    Settlement -> Bank:
        0 to SETTLEMENT_TO_BANK_MAX_DAYS days.
    """
    try:
        order_date = _parse_date(order["order_date"])
        payment_date = _parse_date(payment["payment_date"])
    except (KeyError, TypeError, ValueError):
        return False

    # Order must occur on or before payment.
    if payment_date < order_date:
        return False

    # Payment -> Settlement window.
    if not _within_date_window(
        payment["payment_date"],
        settlement["settlement_date"],
        PAYMENT_TO_SETTLEMENT_MAX_DAYS,
    ):
        return False

    # Settlement -> Bank window.
    if not _within_date_window(
        settlement["settlement_date"],
        bank["transaction_date"],
        SETTLEMENT_TO_BANK_MAX_DAYS,
    ):
        return False

    return True


def date_window_match(chain: TransactionChain) -> bool:
    """
    Apply the Session 6 deterministic date-window matching rule.

    A chain matches only when:

    1. All four records exist.
    2. Order ID links correctly to Payment.
    3. Payment ID links correctly to Settlement.
    4. Settlement reference matches Bank reference.
    5. Order amount matches Payment amount.
    6. Settlement net amount matches Bank credit amount.
    7. Payment -> Settlement occurs within the configured window.
    8. Settlement -> Bank occurs within the configured window.

    This layer performs no fuzzy matching, similarity scoring,
    candidate generation, or AI logic.
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
    # 6. CONFIGURABLE DATE WINDOWS
    # ---------------------------------------------------------

    try:
        if not valid_date_windows(
            order,
            payment,
            settlement,
            bank,
        ):
            return False
    except (KeyError, TypeError, ValueError):
        return False

    return True


def date_window_match_status(
    chain: TransactionChain,
) -> str:
    """
    Return the explicit Session 6 decision:

        MATCH
        UNRESOLVED
    """
    return (
        "MATCH"
        if date_window_match(chain)
        else "UNRESOLVED"
    )

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
)


# ---------------------------------------------------------
# SESSION 7 CONFIGURATION
# ---------------------------------------------------------
#
# Development defaults only.
# These values are intentionally configurable and can be
# tuned later during Day 3 on the development set.
#

CANDIDATE_AMOUNT_TOLERANCE_PERCENT = 0.10
CANDIDATE_DATE_WINDOW_MAX_DAYS = 3
MAX_CANDIDATES = 10


def _parse_date(value: Any) -> date:
    normalized = normalize_date(value)
    year, month, day = map(int, normalized.split("-"))
    return date(year, month, day)


def _amount_within_tolerance(
    target_amount: Any,
    candidate_amount: Any,
    tolerance_percent: Decimal,
) -> bool:
    try:
        target = normalize_amount(target_amount)
        candidate = normalize_amount(candidate_amount)
    except (TypeError, ValueError):
        return False

    if target < Decimal("0"):
        return False

    tolerance = target * tolerance_percent
    return abs(candidate - target) <= tolerance


def _date_within_window(
    target_date: Any,
    candidate_date: Any,
    window_days: int,
) -> bool:
    try:
        target = _parse_date(target_date)
        candidate = _parse_date(candidate_date)
    except (TypeError, ValueError):
        return False

    return abs((candidate - target).days) <= window_days


def _same_merchant(
    target_record: dict[str, Any],
    candidate_record: dict[str, Any],
) -> bool:
    target = target_record.get("merchant_id")
    candidate = candidate_record.get("merchant_id")

    if target is None or candidate is None:
        return True

    return str(target).strip() == str(candidate).strip()


def _same_currency(
    target_record: dict[str, Any],
    candidate_record: dict[str, Any],
) -> bool:
    target = target_record.get("currency")
    candidate = candidate_record.get("currency")

    if target is None or candidate is None:
        return True

    return (
        str(target).strip().upper()
        == str(candidate).strip().upper()
    )


def _record_id(record: dict[str, Any]) -> str | None:
    for field in (
        "order_id",
        "payment_id",
        "settlement_id",
        "transaction_id",
    ):
        if record.get(field) is not None:
            return str(record[field])

    return None


def generate_candidates(
    target_record: dict[str, Any],
    candidate_records: list[dict[str, Any]],
    *,
    amount_field: str,
    date_field: str,
    amount_tolerance_percent: float = CANDIDATE_AMOUNT_TOLERANCE_PERCENT,
    date_window_days: int = CANDIDATE_DATE_WINDOW_MAX_DAYS,
    max_candidates: int = MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """
    Generate a deterministic shortlist of plausible candidates.

    Filters:
    1. Rough amount range.
    2. Nearby date.
    3. Same merchant when available.
    4. Same currency when available.

    This function only generates candidates.

    It does not:
    - perform fuzzy matching
    - calculate similarity scores
    - select a winner
    - use AI
    - make a reconciliation decision
    """

    if not isinstance(target_record, dict):
        return []

    if not isinstance(candidate_records, list):
        return []

    if date_window_days < 0:
        return []

    if max_candidates < 0:
        return []

    try:
        tolerance_percent = Decimal(str(amount_tolerance_percent))
    except (InvalidOperation, ValueError, TypeError):
        return []

    if tolerance_percent < Decimal("0"):
        return []

    target_id = _record_id(target_record)
    results = []

    for candidate in candidate_records:
        if not isinstance(candidate, dict):
            continue

        # Do not return the target itself.
        candidate_id = _record_id(candidate)

        if (
            target_id is not None
            and candidate_id is not None
            and target_id == candidate_id
        ):
            continue

        if not _amount_within_tolerance(
            target_record.get(amount_field),
            candidate.get(amount_field),
            tolerance_percent,
        ):
            continue

        if not _date_within_window(
            target_record.get(date_field),
            candidate.get(date_field),
            date_window_days,
        ):
            continue

        if not _same_merchant(target_record, candidate):
            continue

        if not _same_currency(target_record, candidate):
            continue

        results.append(candidate)

        if len(results) >= max_candidates:
            break

    return results

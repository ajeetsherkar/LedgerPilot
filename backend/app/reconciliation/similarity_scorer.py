from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from rapidfuzz.fuzz import ratio

from backend.app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_reference,
)


# ---------------------------------------------------------
# SESSION 8 CONFIGURATION
# ---------------------------------------------------------
#
# Development defaults only.
# These values are intentionally configurable and can be
# tuned later on the development set.
#

AMOUNT_WEIGHT = 0.35
DATE_WEIGHT = 0.20
REFERENCE_WEIGHT = 0.25
MERCHANT_WEIGHT = 0.10
CURRENCY_WEIGHT = 0.10

DATE_SIMILARITY_MAX_DAYS = 3


def _parse_date(value: Any) -> date:
    """Normalize a supported date value into a date object."""
    normalized = normalize_date(value)
    year, month, day = map(int, normalized.split("-"))
    return date(year, month, day)


def amount_similarity(
    target_amount: Any,
    candidate_amount: Any,
) -> float:
    """
    Calculate a gradual amount similarity score.

    Exact amount -> 1.0

    The score decreases linearly according to the relative
    difference between the two normalized amounts.

    Invalid amounts -> 0.0
    """

    try:
        target = normalize_amount(target_amount)
        candidate = normalize_amount(candidate_amount)
    except (TypeError, ValueError):
        return 0.0

    if target < Decimal("0") or candidate < Decimal("0"):
        return 0.0

    if target == candidate:
        return 1.0

    if target == Decimal("0"):
        return 0.0

    difference = abs(candidate - target)
    relative_difference = difference / target

    score = Decimal("1") - relative_difference

    if score < Decimal("0"):
        return 0.0

    if score > Decimal("1"):
        return 1.0

    return float(score)


def date_similarity(
    target_date: Any,
    candidate_date: Any,
    max_days: int = DATE_SIMILARITY_MAX_DAYS,
) -> float:
    """
    Calculate date similarity.

    Same day -> 1.0
    1 day away -> lower score
    max_days away -> 0.0
    Outside max_days -> 0.0

    Invalid dates -> 0.0
    """

    if max_days < 0:
        return 0.0

    try:
        target = _parse_date(target_date)
        candidate = _parse_date(candidate_date)
    except (TypeError, ValueError):
        return 0.0

    difference = abs((candidate - target).days)

    if difference > max_days:
        return 0.0

    if max_days == 0:
        return 1.0 if difference == 0 else 0.0

    return float(
        Decimal("1")
        - (Decimal(str(difference)) / Decimal(str(max_days)))
    )


def reference_similarity(
    target_reference: Any,
    candidate_reference: Any,
) -> float:
    """
    Calculate normalized RapidFuzz reference similarity.

    Returns a value between 0.0 and 1.0.

    Invalid or missing references -> 0.0.
    """

    try:
        target = normalize_reference(target_reference)
        candidate = normalize_reference(candidate_reference)
    except (TypeError, ValueError):
        return 0.0

    return float(ratio(target, candidate)) / 100.0


def merchant_match(
    target_record: dict[str, Any],
    candidate_record: dict[str, Any],
) -> float:
    """
    Return 1.0 when merchant IDs match and 0.0 otherwise.

    Missing merchant information receives 0.0 because Session 8
    scoring should not assume that an unknown merchant is a match.
    """

    target = target_record.get("merchant_id")
    candidate = candidate_record.get("merchant_id")

    if target is None or candidate is None:
        return 0.0

    if str(target).strip() == str(candidate).strip():
        return 1.0

    return 0.0


def currency_match(
    target_record: dict[str, Any],
    candidate_record: dict[str, Any],
) -> float:
    """
    Return 1.0 when currencies match and 0.0 otherwise.
    """

    target = target_record.get("currency")
    candidate = candidate_record.get("currency")

    if target is None or candidate is None:
        return 0.0

    if (
        str(target).strip().upper()
        == str(candidate).strip().upper()
    ):
        return 1.0

    return 0.0


def _validate_weights(
    amount_weight: float,
    date_weight: float,
    reference_weight: float,
    merchant_weight: float,
    currency_weight: float,
) -> bool:
    """Validate that all weights are non-negative and sum to 1."""

    try:
        weights = [
            Decimal(str(amount_weight)),
            Decimal(str(date_weight)),
            Decimal(str(reference_weight)),
            Decimal(str(merchant_weight)),
            Decimal(str(currency_weight)),
        ]
    except (InvalidOperation, TypeError, ValueError):
        return False

    if any(weight < Decimal("0") for weight in weights):
        return False

    return sum(weights) == Decimal("1")


def score_candidate(
    target_record: dict[str, Any],
    candidate_record: dict[str, Any],
    *,
    amount_field: str,
    date_field: str,
    target_reference_field: str,
    candidate_reference_field: str,
    amount_weight: float = AMOUNT_WEIGHT,
    date_weight: float = DATE_WEIGHT,
    reference_weight: float = REFERENCE_WEIGHT,
    merchant_weight: float = MERCHANT_WEIGHT,
    currency_weight: float = CURRENCY_WEIGHT,
    date_window_days: int = DATE_SIMILARITY_MAX_DAYS,
) -> dict[str, Any]:
    """
    Calculate an explainable weighted similarity score.

    This function:

    - calculates component similarities
    - applies configurable weights
    - returns the final weighted score
    - returns component scores for explanation

    This function does NOT:

    - select a winner
    - declare a reconciliation match
    - use machine learning
    - use AI
    """

    if not isinstance(target_record, dict):
        raise TypeError("target_record must be a dictionary")

    if not isinstance(candidate_record, dict):
        raise TypeError("candidate_record must be a dictionary")

    if date_window_days < 0:
        raise ValueError("date_window_days cannot be negative")

    if not _validate_weights(
        amount_weight,
        date_weight,
        reference_weight,
        merchant_weight,
        currency_weight,
    ):
        raise ValueError(
            "Similarity weights must be non-negative "
            "and sum to exactly 1.0"
        )

    amount_score = amount_similarity(
        target_record.get(amount_field),
        candidate_record.get(amount_field),
    )

    date_score = date_similarity(
        target_record.get(date_field),
        candidate_record.get(date_field),
        date_window_days,
    )

    ref_score = reference_similarity(
        target_record.get(target_reference_field),
        candidate_record.get(candidate_reference_field),
    )

    merchant_score = merchant_match(
        target_record,
        candidate_record,
    )

    currency_score = currency_match(
        target_record,
        candidate_record,
    )

    total_score = (
        amount_weight * amount_score
        + date_weight * date_score
        + reference_weight * ref_score
        + merchant_weight * merchant_score
        + currency_weight * currency_score
    )

    return {
        "total_score": round(float(total_score), 6),
        "amount_similarity": round(amount_score, 6),
        "date_similarity": round(date_score, 6),
        "reference_similarity": round(ref_score, 6),
        "merchant_match": merchant_score,
        "currency_match": currency_score,
        "weights": {
            "amount": amount_weight,
            "date": date_weight,
            "reference": reference_weight,
            "merchant": merchant_weight,
            "currency": currency_weight,
        },
        "explanation": {
            "amount": (
                f"amount similarity = {amount_score:.4f}, "
                f"weight = {amount_weight:.2f}"
            ),
            "date": (
                f"date similarity = {date_score:.4f}, "
                f"weight = {date_weight:.2f}"
            ),
            "reference": (
                f"RapidFuzz reference similarity = "
                f"{ref_score:.4f}, weight = {reference_weight:.2f}"
            ),
            "merchant": (
                f"merchant match = {merchant_score:.1f}, "
                f"weight = {merchant_weight:.2f}"
            ),
            "currency": (
                f"currency match = {currency_score:.1f}, "
                f"weight = {currency_weight:.2f}"
            ),
        },
    }


def score_candidates(
    target_record: dict[str, Any],
    candidate_records: list[dict[str, Any]],
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Score every candidate independently.

    Results preserve the original candidate order.

    No candidate is selected as the winner.
    """

    if not isinstance(candidate_records, list):
        return []

    return [
        {
            "candidate": candidate,
            "score": score_candidate(
                target_record,
                candidate,
                **kwargs,
            ),
        }
        for candidate in candidate_records
        if isinstance(candidate, dict)
    ]

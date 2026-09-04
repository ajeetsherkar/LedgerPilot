from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from backend.app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_reference,
)
from backend.app.reconciliation.fee_aware_matcher import (
    expected_net_amount,
    FEE_AMOUNT_TOLERANCE,
)


@dataclass
class VerificationResult:
    """
    Deterministic verification result for a proposed
    settlement -> bank match.

    AUTO_RESOLVED is allowed only when every required
    verification check passes.
    """

    passed: bool

    amount_passed: bool
    fee_passed: bool
    date_passed: bool
    currency_passed: bool
    reference_passed: bool
    uniqueness_passed: bool

    reasons: list[str] = field(default_factory=list)


def _same_amount(
    expected: Any,
    actual: Any,
) -> bool:
    try:
        return (
            normalize_amount(expected)
            == normalize_amount(actual)
        )
    except (TypeError, ValueError):
        return False


def _same_currency(
    expected: Any,
    actual: Any,
) -> bool:
    if expected is None or actual is None:
        return False

    return (
        str(expected).strip().upper()
        == str(actual).strip().upper()
    )


def _same_reference(
    expected: Any,
    actual: Any,
) -> bool:
    try:
        return (
            normalize_reference(expected)
            == normalize_reference(actual)
        )
    except (TypeError, ValueError):
        return False


def _date_difference_days(
    expected: Any,
    actual: Any,
) -> Optional[int]:
    try:
        expected_date = date.fromisoformat(
            normalize_date(expected)
        )
        actual_date = date.fromisoformat(
            normalize_date(actual)
        )
        return (actual_date - expected_date).days
    except (TypeError, ValueError):
        return None


def _verify_amount(
    settlement: dict[str, Any],
    bank: dict[str, Any],
) -> bool:
    """
    Verify settlement net amount exactly matches
    the proposed bank credit amount.
    """

    return _same_amount(
        settlement.get("net_amount"),
        bank.get("credit_amount"),
    )


def _verify_fee(
    settlement: dict[str, Any],
    bank: dict[str, Any],
) -> bool:
    """
    Verify the bank amount against the settlement fee calculation.

    If the settlement does not contain gross_amount, there is
    no independent fee calculation to perform. In that case,
    the exact net-amount verification is sufficient.
    """

    # Fee verification is only applicable when gross amount
    # is explicitly available.
    if settlement.get("gross_amount") is None:
        return True

    try:
        expected_net = expected_net_amount(settlement)
        bank_amount = normalize_amount(
            bank["credit_amount"]
        )
    except (KeyError, TypeError, ValueError):
        return False

    return (
        abs(bank_amount - expected_net)
        <= FEE_AMOUNT_TOLERANCE
    )


def _verify_date(
    settlement: dict[str, Any],
    bank: dict[str, Any],
) -> bool:
    """
    Verify settlement -> bank date ordering.

    The verification layer deliberately requires the
    bank transaction to occur on or after settlement.
    """

    difference = _date_difference_days(
        settlement.get("settlement_date"),
        bank.get("transaction_date"),
    )

    return (
        difference is not None
        and difference >= 0
    )


def _verify_currency(
    settlement: dict[str, Any],
    bank: dict[str, Any],
) -> bool:
    return _same_currency(
        settlement.get("currency"),
        bank.get("currency"),
    )


def _verify_reference(
    settlement: dict[str, Any],
    bank: dict[str, Any],
) -> bool:
    return _same_reference(
        settlement.get("settlement_reference"),
        bank.get("reference"),
    )


def _verify_uniqueness(
    candidate: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> bool:
    """
    A candidate is unique only when exactly one candidate
    represents the proposed bank transaction.

    Candidate identity is based on transaction_id.
    """

    if not isinstance(candidate, dict):
        return False

    candidate_id = candidate.get("transaction_id")

    if candidate_id is None:
        return False

    matches = 0

    for item in candidates:
        if not isinstance(item, dict):
            continue

        if str(item.get("transaction_id")) == str(
            candidate_id
        ):
            matches += 1

    return matches == 1


def verify_match(
    settlement: dict[str, Any],
    candidate: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    method: str = "EXACT",
) -> VerificationResult:
    """
    Deterministically verify a proposed settlement -> bank match.

    AUTO_RESOLVED may only occur when ALL checks pass:

        1. amount
        2. fee
        3. date
        4. currency
        5. reference
        6. candidate uniqueness

    No AI reasoning is used here.

    This implements:

        AI proposes
              ↓
        Rules verify
              ↓
        System decides
    """

    reasons: list[str] = []

    if method == "FEE_AWARE":
        amount_passed = _verify_fee(
            settlement,
            candidate,
        )
        fee_passed = amount_passed

        if not amount_passed:
            reasons.append(
                "Bank amount does not satisfy the "
                "deterministic fee calculation."
            )
    else:
        amount_passed = _verify_amount(
            settlement,
            candidate,
        )

        if not amount_passed:
            reasons.append(
                "Settlement net amount does not match "
                "bank credit amount."
            )

        fee_passed = _verify_fee(
            settlement,
            candidate,
        )

        if not fee_passed:
            reasons.append(
                "Bank amount does not satisfy the "
                "deterministic fee calculation."
            )

    date_passed = _verify_date(
        settlement,
        candidate,
    )

    if not date_passed:
        reasons.append(
            "Bank transaction date occurs before "
            "the settlement date or is invalid."
        )

    currency_passed = _verify_currency(
        settlement,
        candidate,
    )

    if not currency_passed:
        reasons.append(
            "Settlement and bank currencies do not match."
        )

    reference_passed = _verify_reference(
        settlement,
        candidate,
    )

    if not reference_passed:
        reasons.append(
            "Settlement reference does not match "
            "bank reference."
        )

    uniqueness_passed = _verify_uniqueness(
        candidate,
        candidates,
    )

    if not uniqueness_passed:
        reasons.append(
            "The proposed bank candidate is not unique."
        )

    passed = all(
        (
            amount_passed,
            fee_passed,
            date_passed,
            currency_passed,
            reference_passed,
            uniqueness_passed,
        )
    )

    if passed:
        reasons.append(
            "All deterministic verification checks passed."
        )

    return VerificationResult(
        passed=passed,
        amount_passed=amount_passed,
        fee_passed=fee_passed,
        date_passed=date_passed,
        currency_passed=currency_passed,
        reference_passed=reference_passed,
        uniqueness_passed=uniqueness_passed,
        reasons=reasons,
    )
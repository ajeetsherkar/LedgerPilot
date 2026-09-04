from dataclasses import dataclass
from typing import Any, Optional

from backend.app.reconciliation.relationship_builder import TransactionChain
from backend.app.reconciliation.exact_matcher import exact_match
from backend.app.reconciliation.fee_aware_matcher import fee_aware_match
from backend.app.reconciliation.date_window_matcher import date_window_match
from backend.app.reconciliation.candidate_generator import (
    generate_candidates,
)
from backend.app.reconciliation.similarity_scorer import (
    score_candidates,
)
from backend.app.reconciliation.confidence import (
    ConfidenceBucket,
    ConfidenceThresholds,
    classify_confidence,
)
from backend.app.reconciliation.ai_service import (
    reason_about_reconciliation,
    safely_process_ai_response,
)
from backend.app.reconciliation.verification import (
    verify_match,
)
from backend.app.reconciliation.exception_classifier import (
    classify_chain_exception,
)
from backend.app.reconciliation.exception_types import ExceptionType
from backend.app.reconciliation.decision_status import DecisionStatus


# ---------------------------------------------------------
# SESSION 9 CONFIGURATION
# ---------------------------------------------------------
#
# Development defaults only.
# These thresholds should be tuned later using
# development / ground-truth data.
#

SIMILARITY_MATCH_THRESHOLD = 0.80
SIMILARITY_REVIEW_THRESHOLD = 0.64
MIN_SCORE_MARGIN = 0.05

DEFAULT_CONFIDENCE_THRESHOLDS = ConfidenceThresholds(
    high=0.90,
    medium=0.70,
)


@dataclass
class MatchDecision:
    """
    Final reconciliation decision for a transaction chain.
    """

    status: str
    method: str
    confidence: float
    confidence_bucket: ConfidenceBucket = ConfidenceBucket.LOW
    reason: str = ""
    candidate: Optional[dict[str, Any]] = None
    ai_reasoning: Optional[dict[str, Any]] = None
    exception_type: Optional[str] = None
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    settlement_id: Optional[str] = None
    bank_transaction_id: Optional[str] = None


def _add_confidence_bucket(
    decision: MatchDecision,
) -> MatchDecision:
    decision.confidence_bucket = classify_confidence(
        decision.confidence,
        DEFAULT_CONFIDENCE_THRESHOLDS,
    )
    return decision


def _auto_resolve_if_eligible(
    decision: MatchDecision,
    *,
    verification_passed: bool,
    has_competing_candidate: bool,
) -> MatchDecision:
    """
    Convert an eligible MATCH into AUTO_RESOLVED.

    Auto-resolution requires all three conditions:
        1. HIGH confidence
        2. Verification passed
        3. No competing candidate

    Verification is intentionally supplied as an explicit hook for
    Session 8. Until verification is implemented, callers must not
    pass True.
    """

    if (
        decision.status == "MATCH"
        and decision.confidence_bucket == ConfidenceBucket.HIGH
        and verification_passed
        and not has_competing_candidate
    ):
        decision.status = "AUTO_RESOLVED"
        decision.reason = (
            "High-confidence match passed verification and had "
            "no competing candidate, so it was automatically resolved."
        )

    return decision


def _finalize_decision(
    decision: MatchDecision,
) -> MatchDecision:
    """
    Convert an internal reconciliation decision into one of the
    canonical Session 10 terminal business outcomes.

    Rules:
        AUTO_RESOLVED
            -> preserve

        validated AI reasoning
            -> AI_SUGGESTED

        everything else
            -> HUMAN_REVIEW
    """

    # ---------------------------------------------------------
    # 1. ALREADY AUTO-RESOLVED
    # ---------------------------------------------------------

    if decision.status == DecisionStatus.AUTO_RESOLVED.value:
        return decision

    # ---------------------------------------------------------
    # 2. VALIDATED AI SUGGESTION
    # ---------------------------------------------------------

    if (
        decision.ai_reasoning is not None
        and decision.ai_reasoning.get("status") == "AI_VALIDATED"
        and decision.ai_reasoning.get("recommended_action")
    ):
        decision.status = DecisionStatus.AI_SUGGESTED.value

        ai_reason = (
            "AI produced a validated reconciliation suggestion "
            "for human review."
        )

        if decision.reason:
            decision.reason = f"{decision.reason} {ai_reason}"
        else:
            decision.reason = ai_reason

        return decision

    # ---------------------------------------------------------
    # 3. ALL REMAINING NON-FINAL CASES
    # ---------------------------------------------------------

    decision.status = DecisionStatus.HUMAN_REVIEW.value

    if not decision.reason:
        decision.reason = (
            "Decision requires human review because it did not "
            "meet the criteria for automatic resolution or a "
            "validated AI suggestion."
        )

    return decision


def _finalize_with_confidence(
    decision: MatchDecision,
) -> MatchDecision:
    """
    Apply centralized confidence classification and then
    convert the internal decision into a Session 10 terminal
    business outcome.
    """
    decision = _add_confidence_bucket(decision)
    return _finalize_decision(decision)


def _with_chain_ids(
    decision: MatchDecision,
    chain: TransactionChain,
) -> MatchDecision:
    decision.order_id = chain.order_id
    decision.payment_id = chain.payment_id
    decision.settlement_id = chain.settlement_id
    decision.bank_transaction_id = chain.bank_transaction_id
    return decision


def _verify_decision(
    chain: TransactionChain,
    decision: MatchDecision,
    bank_candidates: Optional[list[dict[str, Any]]],
) -> bool:
    """
    Deterministically verify a proposed settlement -> bank match.

    Verification is required before AUTO_RESOLVED can be produced.
    AI is never trusted as proof of reconciliation.
    """

    if decision.candidate is None:
        return False

    if chain.settlement is None:
        return False

    if bank_candidates is None:
        candidates = [decision.candidate]
    else:
        candidates = bank_candidates

    # Settlement records do not contain currency in the
    # production CSV schema. Use the payment currency as
    # the expected transaction currency for verification.
    payment = getattr(chain, "payment", None)
    order = getattr(chain, "order", None)

    if isinstance(payment, dict):
        expected_currency = payment.get("currency")
    elif isinstance(order, dict):
        expected_currency = order.get("currency")
    else:
        expected_currency = chain.settlement.get("currency")

    verification_settlement = {
        **chain.settlement,
        "currency": expected_currency,
    }

    verification = verify_match(
        verification_settlement,
        decision.candidate,
        candidates,
        method=decision.method,
    )

    if not verification.passed:
        # Preserve verification evidence for downstream
        # routing and human review.
        if decision.reason:
            decision.reason = (
                f"{decision.reason} "
                f"Deterministic verification failed: "
                f"{' '.join(verification.reasons)}"
            )
        else:
            decision.reason = (
                "Deterministic verification failed: "
                f"{' '.join(verification.reasons)}"
            )

    return verification.passed


def _calculate_numeric_delta(
    expected: Any,
    actual: Any,
) -> Optional[float]:
    try:
        if expected is None or actual is None:
            return None

        return round(
            float(actual) - float(expected),
            2,
        )
    except (TypeError, ValueError):
        return None


def _calculate_date_delta(
    expected: Any,
    actual: Any,
) -> Optional[int]:
    if expected is None or actual is None:
        return None

    try:
        from backend.app.reconciliation.normalizer import (
            normalize_date,
        )
        from datetime import date

        expected_normalized = normalize_date(expected)
        actual_normalized = normalize_date(actual)

        expected_date = date.fromisoformat(
            expected_normalized
        )
        actual_date = date.fromisoformat(
            actual_normalized
        )

        return (actual_date - expected_date).days

    except (TypeError, ValueError):
        return None


def _build_ai_evidence_payload(
    chain: TransactionChain,
    decision: MatchDecision,
    bank_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Build a compact evidence payload for AI reasoning.

    The payload contains:
        - transaction context
        - top candidate records
        - amount/date/reference mismatch details
    """

    transaction = {
        "order": chain.order,
        "payment": chain.payment,
        "settlement": chain.settlement,
        "bank": chain.bank,
    }

    top_candidates = []

    for candidate in bank_candidates[:3]:
        if not isinstance(candidate, dict):
            continue

        candidate_amount = candidate.get("credit_amount")
        candidate_date = candidate.get("transaction_date")
        candidate_reference = candidate.get("reference")

        settlement_amount = (
            chain.settlement.get("net_amount")
            if chain.settlement
            else None
        )

        settlement_date = (
            chain.settlement.get("settlement_date")
            if chain.settlement
            else None
        )

        settlement_reference = (
            chain.settlement.get("settlement_reference")
            if chain.settlement
            else None
        )

        top_candidates.append(
            {
                "candidate": candidate,
                "mismatches": {
                    "amount": {
                        "expected": settlement_amount,
                        "actual": candidate_amount,
                        "delta": _calculate_numeric_delta(
                            settlement_amount,
                            candidate_amount,
                        ),
                    },
                    "date": {
                        "expected": settlement_date,
                        "actual": candidate_date,
                        "delta_days": _calculate_date_delta(
                            settlement_date,
                            candidate_date,
                        ),
                    },
                    "reference": {
                        "expected": settlement_reference,
                        "actual": candidate_reference,
                        "match": (
                            settlement_reference
                            == candidate_reference
                        ),
                    },
                },
            }
        )

    return {
        "transaction": transaction,
        "decision": {
            "status": decision.status,
            "method": decision.method,
            "confidence": decision.confidence,
            "confidence_bucket": (
                decision.confidence_bucket.value
            ),
            "reason": decision.reason,
        },
        "top_candidates": top_candidates,
    }


def _deterministic_decision(
    chain: TransactionChain,
) -> Optional[MatchDecision]:
    """
    Apply deterministic reconciliation strategies
    in priority order.

    Priority:

        EXACT
          ↓
        FEE_AWARE
          ↓
        DATE_WINDOW

    Returns:
        MatchDecision when a deterministic strategy matches.
        None when no deterministic strategy matches.
    """

    if exact_match(chain):
        return MatchDecision(
            status="MATCH",
            method="EXACT",
            confidence=1.0,
            reason=(
                "Transaction chain satisfies the exact "
                "matching rules."
            ),
            candidate=chain.bank,
        )

    if fee_aware_match(chain):
        return MatchDecision(
            status="MATCH",
            method="FEE_AWARE",
            confidence=0.99,
            reason=(
                "Transaction chain reconciles after applying "
                "the configured fee and GST calculation."
            ),
            candidate=chain.bank,
        )

    if date_window_match(chain):
        return MatchDecision(
            status="MATCH",
            method="DATE_WINDOW",
            confidence=0.98,
            reason=(
                "Transaction chain satisfies the configured "
                "date-window reconciliation rules."
            ),
            candidate=chain.bank,
        )

    return None


def _similarity_decision(
    chain: TransactionChain,
    bank_candidates: list[dict[str, Any]],
) -> Optional[MatchDecision]:
    """
    Apply candidate generation and similarity scoring
    as the fallback reconciliation strategy.

    Current mapping:
        Settlement -> Bank

    Bank records are adapted internally to the settlement
    field names required by the generic candidate generator
    and similarity scorer. Original bank records are returned
    in the final MatchDecision.
    """

    if chain.settlement is None:
        return None

    if not isinstance(bank_candidates, list):
        return None

    # ---------------------------------------------------------
    # 1. CREATE INTERNAL SCORING RECORDS
    # ---------------------------------------------------------
    # The generic candidate generator and scorer expect
    # settlement-style field names.
    #
    # Do NOT modify the original bank candidates.

    scoring_candidates = [
        {
            **candidate,
            "net_amount": candidate.get("credit_amount"),
            "settlement_date": candidate.get("transaction_date"),
            "settlement_reference": candidate.get("reference"),
        }
        for candidate in bank_candidates
        if isinstance(candidate, dict)
    ]

    if not scoring_candidates:
        return None

    # ---------------------------------------------------------
    # 2. GENERATE CANDIDATES
    # ---------------------------------------------------------

    candidates = generate_candidates(
        chain.settlement,
        scoring_candidates,
        amount_field="net_amount",
        date_field="settlement_date",
    )

    if not candidates:
        return None

    # ---------------------------------------------------------
    # 3. SCORE CANDIDATES
    # ---------------------------------------------------------

    scored_candidates = score_candidates(
        chain.settlement,
        candidates,
        amount_field="net_amount",
        date_field="settlement_date",
        target_reference_field="settlement_reference",
        candidate_reference_field="settlement_reference",
    )

    if not scored_candidates:
        return None

    # ---------------------------------------------------------
    # 4. SELECT BEST CANDIDATE
    # ---------------------------------------------------------

    decision = select_best_candidate(scored_candidates)

    if decision is None:
        return None

    status = decision["status"]

    # ---------------------------------------------------------
    # 5. MAP BACK TO ORIGINAL BANK RECORD
    # ---------------------------------------------------------

    scored_candidate = decision.get("candidate")
    original_candidate = None

    if isinstance(scored_candidate, dict):
        candidate_id = scored_candidate.get("transaction_id")

        for candidate in bank_candidates:
            if (
                isinstance(candidate, dict)
                and candidate.get("transaction_id") == candidate_id
            ):
                original_candidate = candidate
                break

    # ---------------------------------------------------------
    # 6. MATCH
    # ---------------------------------------------------------

    if status == "MATCH":
        return MatchDecision(
            status="MATCH",
            method="SIMILARITY",
            confidence=float(decision["score"]),
            reason=(
                "Best bank candidate exceeded the similarity "
                "match threshold with sufficient score margin."
            ),
            candidate=original_candidate,
        )

    # ---------------------------------------------------------
    # 7. REVIEW
    # ---------------------------------------------------------

    if status == "REVIEW":
        if decision.get("ambiguous", False):
            return MatchDecision(
                status="REVIEW",
                method="SIMILARITY",
                confidence=0.0,
                reason=(
                    "Top two bank candidates have a score difference "
                    "below the configured ambiguity margin. The system "
                    "refuses to guess and requires human review."
                ),
                candidate=original_candidate,
                exception_type=ExceptionType.AMBIGUOUS_MATCH.value,
            )

        return MatchDecision(
            status="REVIEW",
            method="SIMILARITY",
            confidence=float(decision["score"]),
            reason=(
                "Best bank candidate is plausible but requires "
                "manual review because the similarity score does "
                "not provide sufficient confidence for automatic matching."
            ),
            candidate=original_candidate,
        )

    # ---------------------------------------------------------
    # 8. UNRESOLVED
    # ---------------------------------------------------------

    return MatchDecision(
        status="UNRESOLVED",
        method="SIMILARITY",
        confidence=float(decision["score"]),
        reason=(
            "Candidate records were generated and scored, but "
            "no candidate reached the review threshold."
        ),
        candidate=None,
        exception_type=ExceptionType.UNKNOWN_REFERENCE.value,
    )


def select_best_candidate(
    scored_candidates: list[dict[str, Any]],
    *,
    match_threshold: float = SIMILARITY_MATCH_THRESHOLD,
    review_threshold: float = SIMILARITY_REVIEW_THRESHOLD,
    min_score_margin: float = MIN_SCORE_MARGIN,
) -> Optional[dict[str, Any]]:
    """
    Select the best candidate from already-scored candidates.

    This function does not calculate similarity scores.

    Decision rules:

        score >= match_threshold
            AND sufficient margin
            -> MATCH

        score >= review_threshold
            -> REVIEW

        otherwise
            -> UNRESOLVED

    Ambiguous high-scoring candidates are sent to REVIEW.
    """

    if not isinstance(scored_candidates, list):
        return None

    if not scored_candidates:
        return None

    if match_threshold < review_threshold:
        raise ValueError(
            "match_threshold cannot be lower than "
            "review_threshold"
        )

    if min_score_margin < 0:
        raise ValueError(
            "min_score_margin cannot be negative"
        )

    ranked = sorted(
        scored_candidates,
        key=lambda item: item.get("score", {}).get(
            "total_score",
            0.0,
        ),
        reverse=True,
    )

    best = ranked[0]

    best_score = float(
        best.get("score", {}).get(
            "total_score",
            0.0,
        )
    )

    second_score = (
        float(
            ranked[1].get("score", {}).get(
                "total_score",
                0.0,
            )
        )
        if len(ranked) > 1
        else 0.0
    )

    score_margin = round(best_score - second_score, 2)

    ambiguous = (
        len(ranked) > 1
        and score_margin < min_score_margin
    )

    if ambiguous:
        status = "REVIEW"
    elif best_score >= match_threshold:
        status = "MATCH"
    elif best_score >= review_threshold:
        status = "REVIEW"
    else:
        status = "UNRESOLVED"

    return {
        "status": status,
        "candidate": best.get("candidate"),
        "score": best_score,
        "score_margin": score_margin,
        "ambiguous": ambiguous,
        "ranked_candidates": ranked,
    }


def decide_chain(
    chain: TransactionChain,
    *,
    bank_candidates: Optional[list[dict[str, Any]]] = None,
    verification_passed: bool = False,
    allow_missing_bank_exception: bool = True,
) -> MatchDecision:
    """
    Apply the deterministic reconciliation decision pipeline,
    falling back to similarity-based matching when bank
    candidates are supplied.

    Current Session 9 pipeline:

        TransactionChain
              ↓
        Incomplete Chain Check
              ↓
        Missing Bank Record Check
              ↓
        classify_chain_exception()
              ↓
        Canonical Session 7 Exceptions
        (PARTIAL_SETTLEMENT / COMBINED_SETTLEMENT / DATE_MISMATCH)
              ↓
        Order/Payment Amount Mismatch Check
              ↓
        Exact Matcher
              ↓
        Fee-Aware Matcher
              ↓
        Date-Window Matcher
              ↓
        Similarity Fallback (if bank_candidates provided)
              ↓
        Other Canonical Accounting Exceptions
              ↓
        UNRESOLVED

    Every returned MatchDecision passes through
    _add_confidence_bucket() so confidence_bucket is always
    derived centrally from confidence, rather than being set
    ad hoc at each call site.
    """

    if not isinstance(chain, TransactionChain):
        raise TypeError(
            "chain must be a TransactionChain"
        )

    # ---------------------------------------------------------
    # INCOMPLETE CHAIN → UNRESOLVED
    # ---------------------------------------------------------

    if (
        chain.payment is None
        or chain.settlement is None
    ):
        return _finalize_with_confidence(
            _with_chain_ids(
                MatchDecision(
                    status="UNRESOLVED",
                    method="NONE",
                    confidence=0.0,
                    reason=(
                        "Transaction chain is incomplete and does "
                        "not contain enough records to perform "
                        "reconciliation."
                    ),
                    candidate=None,
                    exception_type=(
                        ExceptionType.UNKNOWN_REFERENCE.value
                    ),
                ),
                chain,
            )
        )

    # ---------------------------------------------------------
    # MISSING BANK RECORD → EXCEPTION
    # ---------------------------------------------------------

    if (
        chain.bank is None
        and not bank_candidates
        and allow_missing_bank_exception
    ):
        return _finalize_with_confidence(
            _with_chain_ids(
                MatchDecision(
                    status="EXCEPTION",
                    method="NONE",
                    confidence=1.0,
                    reason=(
                        "Transaction chain is missing the required "
                        "bank record."
                    ),
                    candidate=None,
                    exception_type=(
                        ExceptionType.MISSING_BANK_RECORD.value
                    ),
                ),
                chain,
            )
        )

    # ---------------------------------------------------------
    # HARD ACCOUNTING EXCEPTION: ORDER/PAYMENT AMOUNT MISMATCH
    # ---------------------------------------------------------
    #
    # This must be checked BEFORE deterministic matching.
    # An order/payment amount mismatch is a hard accounting
    # exception and must never be allowed to become MATCH.
    #

    chain_exception = classify_chain_exception(chain)

    # ---------------------------------------------------------
    # CANONICAL SESSION 7 EXCEPTIONS
    # ---------------------------------------------------------

    if chain_exception in {
        ExceptionType.PARTIAL_SETTLEMENT,
        ExceptionType.COMBINED_SETTLEMENT,
    }:
        reasons = {
            ExceptionType.PARTIAL_SETTLEMENT: (
                "One payment is associated with multiple "
                "settlement records."
            ),
            ExceptionType.COMBINED_SETTLEMENT: (
                "Multiple payments are represented by a "
                "single combined bank credit."
            ),
        }

        return _finalize_with_confidence(
            _with_chain_ids(
                MatchDecision(
                    status="EXCEPTION",
                    method="NONE",
                    confidence=1.0,
                    reason=reasons[chain_exception],
                    candidate=None,
                    exception_type=chain_exception.value,
                ),
                chain,
            )
        )

    if (
        chain_exception == ExceptionType.AMOUNT_MISMATCH
        and chain.order is not None
        and chain.payment is not None
    ):
        order_amount = chain.order.get("order_amount")
        payment_amount = chain.payment.get("amount")

        try:
            payment_mismatch = (
                order_amount is not None
                and payment_amount is not None
                and round(float(order_amount), 2)
                != round(float(payment_amount), 2)
            )
        except (TypeError, ValueError):
            payment_mismatch = False

        if payment_mismatch:
            return _finalize_with_confidence(
                _with_chain_ids(
                    MatchDecision(
                        status="EXCEPTION",
                        method="NONE",
                        confidence=1.0,
                        reason=(
                            "Order amount does not match payment amount."
                        ),
                        candidate=None,
                        exception_type=chain_exception.value,
                    ),
                    chain,
                )
            )

    # ---------------------------------------------------------
    # DETERMINISTIC MATCHING
    # ---------------------------------------------------------

    deterministic_result = _deterministic_decision(chain)

    if deterministic_result is not None:
        decision = _add_confidence_bucket(
            _with_chain_ids(
                deterministic_result,
                chain,
            )
        )

        verification_passed = _verify_decision(
            chain,
            decision,
            bank_candidates,
        )

        if not verification_passed:
            decision.status = "REVIEW"
            decision.reason = (
                f"{decision.reason} "
                "The proposed match failed deterministic verification "
                "and therefore requires human review."
            )

        if decision.method == "EXACT":
            decision = _auto_resolve_if_eligible(
                decision,
                verification_passed=verification_passed,
                has_competing_candidate=False,
            )
        return _finalize_decision(decision)

    # ---------------------------------------------------------
    # SIMILARITY FALLBACK
    # ---------------------------------------------------------

    if bank_candidates is not None:
        similarity_result = _similarity_decision(
            chain,
            bank_candidates,
        )

        if similarity_result is not None:
            decision = _add_confidence_bucket(
                _with_chain_ids(
                    similarity_result,
                    chain,
                )
            )

            verification_passed = _verify_decision(
                chain,
                decision,
                bank_candidates,
            )

            if not verification_passed:
                decision.status = "REVIEW"
                decision.reason = (
                    f"{decision.reason} "
                    "The proposed match failed deterministic verification "
                    "and therefore requires human review."
                )

            if decision.method == "EXACT":
                decision = _auto_resolve_if_eligible(
                    decision,
                    verification_passed=verification_passed,
                    has_competing_candidate=False,
                )


            if decision.confidence_bucket == ConfidenceBucket.MEDIUM:

                if decision.exception_type is None:
                    decision.exception_type = (
                        ExceptionType.UNKNOWN_REFERENCE.value
                    )

                evidence = _build_ai_evidence_payload(
                    chain,
                    decision,
                    bank_candidates,
                )

                ai_response = reason_about_reconciliation(
                    evidence
                )

                decision.ai_reasoning = safely_process_ai_response(
                    evidence,
                    ai_response,
                )

                if isinstance(decision.candidate, dict):
                    decision.candidate["ai_reasoning"] = decision.ai_reasoning

                decision.reason = (
                    f"{decision.reason} "
                    "Medium-confidence case routed to AI reasoning service "
                    "through the safe AI validation boundary."
                )

            return _finalize_decision(decision)

    # ---------------------------------------------------------
    # CANONICAL ACCOUNTING EXCEPTION
    # ---------------------------------------------------------
    #
    # Only surface exceptions that are independently established
    # by the transaction chain. A failed reconciliation alone is
    # not sufficient to declare an accounting exception.
    #
    # Missing bank is a structural exception and must be surfaced.
    # Payment/order amount mismatch is also a hard exception and
    # was already checked earlier, before deterministic matching.
    #
    # Settlement/bank amount mismatches are canonical accounting
    # exceptions once all reconciliation strategies have failed.
    #
    # Reference problems without a deterministic match remain
    # UNRESOLVED.

    if (
        chain_exception == ExceptionType.MISSING_BANK_RECORD
        and bank_candidates is None
    ):
        return _finalize_with_confidence(
            _with_chain_ids(
                MatchDecision(
                    status="EXCEPTION",
                    method="NONE",
                    confidence=1.0,
                    reason=(
                        "Transaction chain is missing the required "
                        "bank record."
                    ),
                    candidate=None,
                    exception_type=chain_exception.value,
                ),
                chain,
            )
        )

    # ---------------------------------------------------------
    # SETTLEMENT / BANK AMOUNT MISMATCH
    # ---------------------------------------------------------
    #
    # At this point all deterministic and similarity matching
    # strategies have already failed. Therefore an independently
    # classified settlement/bank amount mismatch can safely be
    # surfaced as a canonical accounting exception.
    #
    if chain_exception == ExceptionType.AMOUNT_MISMATCH:
        settlement_net_amount = chain.settlement.get("net_amount")
        bank_credit_amount = chain.bank.get("credit_amount")

        try:
            bank_amount_mismatch = (
                settlement_net_amount is not None
                and bank_credit_amount is not None
                and round(float(settlement_net_amount), 2)
                != round(float(bank_credit_amount), 2)
            )
        except (TypeError, ValueError):
            bank_amount_mismatch = False

        if bank_amount_mismatch:
            return _finalize_with_confidence(
                _with_chain_ids(
                    MatchDecision(
                        status="EXCEPTION",
                        method="NONE",
                        confidence=1.0,
                        reason=(
                            "Settlement net amount does not match "
                            "the bank credit amount."
                        ),
                        candidate=None,
                        exception_type=chain_exception.value,
                    ),
                    chain,
                )
            )

    # ---------------------------------------------------------
    # FINAL UNRESOLVED
    # ---------------------------------------------------------

    return _finalize_with_confidence(
        _with_chain_ids(
            MatchDecision(
                status="UNRESOLVED",
                method="NONE",
                confidence=0.0,
                reason=(
                    "No deterministic reconciliation strategy matched "
                    "the transaction chain and no similarity candidate "
                    "produced a reviewable result."
                ),
                candidate=None,
                exception_type=ExceptionType.UNKNOWN_REFERENCE.value,
            ),
            chain,
        )
    )
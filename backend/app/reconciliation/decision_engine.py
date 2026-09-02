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


def _with_chain_ids(
    decision: MatchDecision,
    chain: TransactionChain,
) -> MatchDecision:
    decision.order_id = chain.order_id
    decision.payment_id = chain.payment_id
    decision.settlement_id = chain.settlement_id
    decision.bank_transaction_id = chain.bank_transaction_id

    return decision


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
) -> MatchDecision:
    """
    Apply the deterministic reconciliation decision pipeline,
    falling back to similarity-based matching when bank
    candidates are supplied.

    Current Session 9 pipeline:

        TransactionChain
              ↓
        Exact Matcher
              ↓
        Fee-Aware Matcher
              ↓
        Date-Window Matcher
              ↓
        Similarity Fallback (if bank_candidates provided)
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

    deterministic_result = _deterministic_decision(chain)

    if deterministic_result is not None:
        return _add_confidence_bucket(
            _with_chain_ids(
                deterministic_result,
                chain,
            )
        )

    # ---------------------------------------------------------
    # BLOCK SIMILARITY FALLBACK FOR KNOWN PAYMENT MISMATCH
    # ---------------------------------------------------------

    if (
        chain.payment is not None
        and chain.order is not None
    ):
        try:
            order_amount = float(chain.order["order_amount"])
            payment_amount = float(chain.payment["amount"])

            if order_amount != payment_amount:
                return _add_confidence_bucket(
                    _with_chain_ids(
                        MatchDecision(
                            status="EXCEPTION",
                            method="NONE",
                            confidence=1.0,
                            reason=(
                                "Order amount does not match payment amount."
                            ),
                            candidate=None,
                        ),
                        chain,
                    )
                )
        except (KeyError, TypeError, ValueError):
            return _add_confidence_bucket(
                _with_chain_ids(
                    MatchDecision(
                        status="EXCEPTION",
                        method="NONE",
                        confidence=1.0,
                        reason=(
                            "Order or payment amount could not be "
                            "validated."
                        ),
                        candidate=None,
                    ),
                    chain,
                )
            )

    # ---------------------------------------------------------
    # SIMILARITY FALLBACK
    # ---------------------------------------------------------

    if bank_candidates is not None:
        similarity_result = _similarity_decision(
            chain,
            bank_candidates,
        )

        if similarity_result is not None:
            return _add_confidence_bucket(
                _with_chain_ids(
                    similarity_result,
                    chain,
                )
            )

    return _add_confidence_bucket(
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
            ),
            chain,
        )
    )
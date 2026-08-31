from dataclasses import dataclass
from typing import Any, Optional

from backend.app.reconciliation.relationship_builder import TransactionChain
from backend.app.reconciliation.exact_matcher import exact_match
from backend.app.reconciliation.fee_aware_matcher import fee_aware_match
from backend.app.reconciliation.date_window_matcher import date_window_match


# ---------------------------------------------------------
# SESSION 9 CONFIGURATION
# ---------------------------------------------------------
#
# Development defaults only.
# These thresholds should be tuned later using
# development / ground-truth data.
#

SIMILARITY_MATCH_THRESHOLD = 0.85
SIMILARITY_REVIEW_THRESHOLD = 0.65
MIN_SCORE_MARGIN = 0.05


@dataclass
class MatchDecision:
    """
    Final reconciliation decision for a transaction chain.

    status:
        MATCH
        REVIEW
        UNRESOLVED
        EXCEPTION

    method:
        EXACT
        FEE_AWARE
        DATE_WINDOW
        SIMILARITY
        NONE
    """

    status: str
    method: str
    confidence: float
    reason: str
    candidate: Optional[dict[str, Any]] = None


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

    score_margin = best_score - second_score

    if (
        best_score >= match_threshold
        and score_margin >= min_score_margin
    ):
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
        "ranked_candidates": ranked,
    }


def decide_chain(
    chain: TransactionChain,
) -> MatchDecision:
    """
    Apply the deterministic reconciliation decision pipeline.

    Current Session 9 pipeline:

        TransactionChain
              ↓
        Exact Matcher
              ↓
        Fee-Aware Matcher
              ↓
        Date-Window Matcher
              ↓
        UNRESOLVED

    Candidate generation and similarity scoring will be
    integrated into this function after their record-level
    mapping is defined.
    """

    if not isinstance(chain, TransactionChain):
        raise TypeError(
            "chain must be a TransactionChain"
        )

    deterministic_result = _deterministic_decision(chain)

    if deterministic_result is not None:
        return deterministic_result

    return MatchDecision(
        status="UNRESOLVED",
        method="NONE",
        confidence=0.0,
        reason=(
            "No deterministic reconciliation strategy "
            "matched the transaction chain."
        ),
    )
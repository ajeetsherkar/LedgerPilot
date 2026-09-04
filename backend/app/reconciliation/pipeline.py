from typing import Any, Optional

from backend.app.reconciliation.relationship_builder import (
    TransactionChain,
    build_transaction_chains,
)

from backend.app.reconciliation.decision_engine import (
    MatchDecision,
    decide_chain,
    _finalize_decision,
)


def reconcile_all(
    orders: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    banks: list[dict[str, Any]],
    *,
    bank_candidates: Optional[list[dict[str, Any]]] = None,
) -> list[MatchDecision]:
    """
    Run the complete reconciliation decision pipeline.

    Pipeline:

        Orders
          ↓
        Relationship Builder
          ↓
        TransactionChain[]
          ↓
        Decision Engine
          ↓
        MatchDecision[]

    The function does not modify the input datasets.
    """

    chains = build_transaction_chains(
        orders,
        payments,
        settlements,
        banks,
    )

    decisions = []

    for chain in chains:
        decision = decide_chain(
            chain,
            bank_candidates=bank_candidates,
        )

        if (
            decision.exception_type == "MISSING_BANK_RECORD"
            and not bank_candidates
        ):
            decision.status = "UNRESOLVED"
            decision.confidence = 0.0
            decision.reason = (
                "Transaction chain is missing the required bank record "
                "and no bank candidates were supplied."
            )

        # Session 10 canonical terminal-status gate.
        decision = _finalize_decision(decision)
        decisions.append(decision)

    return decisions
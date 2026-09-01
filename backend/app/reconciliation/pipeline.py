from typing import Any, Optional

from backend.app.reconciliation.relationship_builder import (
    TransactionChain,
    build_transaction_chains,
)

from backend.app.reconciliation.decision_engine import (
    MatchDecision,
    decide_chain,
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

        decisions.append(decision)

    return decisions
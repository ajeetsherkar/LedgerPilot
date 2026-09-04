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
from backend.app.reconciliation.input_validator import (
    validate_reconciliation_inputs,
)



def _unresolved_validation_decisions(
    orders: list[dict[str, Any]],
    reason: str,
) -> list[MatchDecision]:
    """Create inspectable UNRESOLVED decisions for malformed input."""
    decisions: list[MatchDecision] = []

    for order in orders:
        order_id = order.get("order_id")

        decisions.append(
            MatchDecision(
                status="UNRESOLVED",
                method="VALIDATION",
                confidence=0.0,
                reason=(
                    "Reconciliation input validation failed. "
                    "The case was safely marked UNRESOLVED. "
                    f"Failure: {reason}"
                ),
                order_id=order_id,
            )
        )

    return decisions


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

    validation_error = validate_reconciliation_inputs(
        orders,
        payments,
        settlements,
        banks,
    )

    if validation_error is not None:
        return _unresolved_validation_decisions(
            orders,
            validation_error,
        )

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
from typing import Any


def reason_about_reconciliation(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """
    AI reasoning service boundary.

    Receives a compact evidence payload for a MEDIUM-confidence
    reconciliation case.

    The actual LLM/provider integration can be added behind this
    boundary without changing the decision engine.
    """

    if not isinstance(evidence, dict):
        raise TypeError("evidence must be a dictionary")

    return {
        "status": "PENDING_AI_REVIEW",
        "reasoning": None,
        "recommendation": None,
        "evidence": evidence,
    }

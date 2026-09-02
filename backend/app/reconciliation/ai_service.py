from typing import Any

from backend.app.reconciliation.ai_schema import AIReasoningResponse


def validate_ai_response(
    response: dict[str, Any],
) -> AIReasoningResponse:
    """
    Validate and parse an AI reconciliation response.

    Pydantic is the trust boundary for AI-generated output.
    Invalid or unexpected fields are rejected before the
    response can be used by downstream reconciliation logic.
    """

    if not isinstance(response, dict):
        raise TypeError("AI response must be a dictionary")

    return AIReasoningResponse.model_validate(response)


def reason_about_reconciliation(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """
    AI reasoning service boundary.

    Receives a compact evidence payload for a MEDIUM-confidence
    reconciliation case.

    The actual LLM/provider integration can be added behind this
    boundary without changing the decision engine.

    For Session 5, the service establishes and enforces the
    structured AI response contract.
    """

    if not isinstance(evidence, dict):
        raise TypeError("evidence must be a dictionary")

    return {
        "status": "PENDING_AI_REVIEW",
        "reasoning": None,
        "recommendation": None,
        "evidence": evidence,
    }

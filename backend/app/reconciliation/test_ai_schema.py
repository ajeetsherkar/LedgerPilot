import pytest
from pydantic import ValidationError

from backend.app.reconciliation.ai_schema import (
    AIReasoningResponse,
)


def test_valid_ai_response_is_accepted():
    response = AIReasoningResponse(
        classification="AMOUNT_MISMATCH",
        recommended_action="HUMAN_REVIEW",
        reason="The payment amount differs from the settlement amount.",
        confidence=0.82,
    )

    assert response.classification == "AMOUNT_MISMATCH"
    assert response.recommended_action == "HUMAN_REVIEW"
    assert response.reason == (
        "The payment amount differs from the settlement amount."
    )
    assert response.confidence == 0.82


def test_missing_required_field_is_rejected():
    with pytest.raises(ValidationError):
        AIReasoningResponse(
            classification="AMOUNT_MISMATCH",
            recommended_action="HUMAN_REVIEW",
            reason="Amount mismatch detected.",
        )


@pytest.mark.parametrize(
    "confidence",
    [-0.1, 1.1, -1.0, 2.0],
)
def test_out_of_range_confidence_is_rejected(confidence):
    with pytest.raises(ValidationError):
        AIReasoningResponse(
            classification="AMOUNT_MISMATCH",
            recommended_action="HUMAN_REVIEW",
            reason="Amount mismatch detected.",
            confidence=confidence,
        )


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        AIReasoningResponse(
            classification="AMOUNT_MISMATCH",
            recommended_action="HUMAN_REVIEW",
            reason="Amount mismatch detected.",
            confidence=0.82,
            unexpected_field="must be rejected",
        )


@pytest.mark.parametrize(
    "field",
    [
        "classification",
        "recommended_action",
        "reason",
    ],
)
def test_empty_required_string_is_rejected(field):
    payload = {
        "classification": "AMOUNT_MISMATCH",
        "recommended_action": "HUMAN_REVIEW",
        "reason": "Amount mismatch detected.",
        "confidence": 0.82,
    }

    payload[field] = ""

    with pytest.raises(ValidationError):
        AIReasoningResponse(**payload)


def test_boundary_confidence_values_are_accepted():
    low = AIReasoningResponse(
        classification="AMOUNT_MISMATCH",
        recommended_action="HUMAN_REVIEW",
        reason="Low boundary test.",
        confidence=0.0,
    )

    high = AIReasoningResponse(
        classification="AMOUNT_MISMATCH",
        recommended_action="HUMAN_REVIEW",
        reason="High boundary test.",
        confidence=1.0,
    )

    assert low.confidence == 0.0
    assert high.confidence == 1.0

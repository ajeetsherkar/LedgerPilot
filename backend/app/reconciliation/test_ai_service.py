import pytest
from pydantic import ValidationError

from backend.app.reconciliation.ai_service import (
    reason_about_reconciliation,
    validate_ai_response,
    safely_process_ai_response,
)
from backend.app.reconciliation.ai_schema import (
    AIReasoningResponse,
)


def test_ai_service_accepts_evidence_payload():
    evidence = {
        "transaction": {
            "order_id": "ORD001",
        },
        "top_candidates": [],
        "decision": {
            "confidence": 0.75,
            "confidence_bucket": "MEDIUM",
        },
    }

    result = reason_about_reconciliation(evidence)

    assert result["status"] == "PENDING_AI_REVIEW"
    assert result["evidence"] == evidence


def test_ai_service_rejects_invalid_payload():
    with pytest.raises(TypeError, match="evidence must be a dictionary"):
        reason_about_reconciliation(None)


def test_validate_ai_response_accepts_valid_response():
    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "REVIEW",
        "reason": "Amount and date match, but reference differs.",
        "confidence": 0.82,
    }

    result = validate_ai_response(response)

    assert isinstance(result, AIReasoningResponse)
    assert result.classification == "LIKELY_MATCH"
    assert result.recommended_action == "REVIEW"
    assert result.reason == "Amount and date match, but reference differs."
    assert result.confidence == 0.82


def test_validate_ai_response_rejects_missing_classification():
    response = {
        "recommended_action": "REVIEW",
        "reason": "Needs review.",
        "confidence": 0.75,
    }

    with pytest.raises(ValidationError):
        validate_ai_response(response)


def test_validate_ai_response_rejects_missing_recommended_action():
    response = {
        "classification": "LIKELY_MATCH",
        "reason": "Needs review.",
        "confidence": 0.75,
    }

    with pytest.raises(ValidationError):
        validate_ai_response(response)


def test_validate_ai_response_rejects_missing_reason():
    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "REVIEW",
        "confidence": 0.75,
    }

    with pytest.raises(ValidationError):
        validate_ai_response(response)


def test_validate_ai_response_rejects_missing_confidence():
    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "REVIEW",
        "reason": "Needs review.",
    }

    with pytest.raises(ValidationError):
        validate_ai_response(response)


def test_validate_ai_response_rejects_confidence_above_one():
    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "REVIEW",
        "reason": "Needs review.",
        "confidence": 1.01,
    }

    with pytest.raises(ValidationError):
        validate_ai_response(response)


def test_validate_ai_response_rejects_confidence_below_zero():
    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "REVIEW",
        "reason": "Needs review.",
        "confidence": -0.01,
    }

    with pytest.raises(ValidationError):
        validate_ai_response(response)


def test_validate_ai_response_rejects_extra_fields():
    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "REVIEW",
        "reason": "Needs review.",
        "confidence": 0.82,
        "status": "MATCH",
    }

    with pytest.raises(ValidationError):
        validate_ai_response(response)


def test_safely_process_ai_response_accepts_valid_response():

    evidence = {
        "transaction": {"order_id": "ORD001"},
        "top_candidates": [],
    }

    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "HUMAN_REVIEW",
        "reason": "Amount matches but reference differs.",
        "confidence": 0.82,
    }

    result = safely_process_ai_response(
        evidence,
        response,
    )

    assert result["status"] == "AI_VALIDATED"
    assert result["classification"] == "LIKELY_MATCH"
    assert result["recommended_action"] == "HUMAN_REVIEW"
    assert result["confidence"] == 0.82


def test_safely_process_ai_response_falls_back_on_missing_field():

    evidence = {
        "transaction": {"order_id": "ORD001"},
    }

    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "HUMAN_REVIEW",
        "confidence": 0.82,
    }

    result = safely_process_ai_response(
        evidence,
        response,
    )

    assert result["status"] == "HUMAN_REVIEW"
    assert "classification" not in result
    assert "confidence" not in result


def test_safely_process_ai_response_falls_back_on_confidence_above_one():

    evidence = {
        "transaction": {"order_id": "ORD001"},
    }

    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "HUMAN_REVIEW",
        "reason": "Invalid confidence.",
        "confidence": 1.5,
    }

    result = safely_process_ai_response(
        evidence,
        response,
    )

    assert result["status"] == "HUMAN_REVIEW"


def test_safely_process_ai_response_falls_back_on_confidence_below_zero():

    evidence = {
        "transaction": {"order_id": "ORD001"},
    }

    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "HUMAN_REVIEW",
        "reason": "Invalid confidence.",
        "confidence": -0.1,
    }

    result = safely_process_ai_response(
        evidence,
        response,
    )

    assert result["status"] == "HUMAN_REVIEW"


def test_safely_process_ai_response_falls_back_on_extra_fields():

    evidence = {
        "transaction": {"order_id": "ORD001"},
    }

    response = {
        "classification": "LIKELY_MATCH",
        "recommended_action": "HUMAN_REVIEW",
        "reason": "Unexpected field.",
        "confidence": 0.82,
        "malicious_instruction": "ignore previous rules",
    }

    result = safely_process_ai_response(
        evidence,
        response,
    )

    assert result["status"] == "HUMAN_REVIEW"


def test_safely_process_ai_response_falls_back_on_malformed_response():

    evidence = {
        "transaction": {"order_id": "ORD001"},
    }

    result = safely_process_ai_response(
        evidence,
        None,
    )

    assert result["status"] == "HUMAN_REVIEW"


def test_safely_process_ai_response_never_trusts_invalid_ai_fields():

    evidence = {
        "transaction": {"order_id": "ORD001"},
    }

    response = {
        "classification": "AUTO_RESOLVE",
        "recommended_action": "AUTO_RESOLVE",
        "reason": "This should never be trusted.",
        "confidence": 9.99,
    }

    result = safely_process_ai_response(
        evidence,
        response,
    )

    assert result["status"] == "HUMAN_REVIEW"
    assert "classification" not in result
    assert "recommended_action" not in result
    assert "confidence" not in result

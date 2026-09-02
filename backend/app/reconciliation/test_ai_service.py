from backend.app.reconciliation.ai_service import (
    reason_about_reconciliation,
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
    try:
        reason_about_reconciliation(None)
    except TypeError as exc:
        assert str(exc) == "evidence must be a dictionary"
    else:
        raise AssertionError(
            "Expected TypeError for invalid evidence"
        )

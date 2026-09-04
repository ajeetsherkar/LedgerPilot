from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_connection
from backend.app.reconciliation.human_review import (
    create_or_get_review,
)


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "LedgerPilot"


def test_upload_and_reconciliation():
    with (
        open("data/test_orders.csv", "rb") as orders,
        open("data/test_payments.csv", "rb") as payments,
        open("data/test_settlements.csv", "rb") as settlements,
        open("data/test_bank.csv", "rb") as bank,
    ):
        response = client.post(
            "/upload",
            files={
                "orders": (
                    "test_orders.csv",
                    orders,
                    "text/csv",
                ),
                "payments": (
                    "test_payments.csv",
                    payments,
                    "text/csv",
                ),
                "settlements": (
                    "test_settlements.csv",
                    settlements,
                    "text/csv",
                ),
                "bank": (
                    "test_bank.csv",
                    bank,
                    "text/csv",
                ),
            },
        )

    assert response.status_code == 200

    upload_data = response.json()

    assert upload_data["status"] == "success"
    assert upload_data["records_uploaded"] == 40

    batch_id = upload_data["batch_id"]

    reconciliation_response = client.get(
        f"/reconciliation/{batch_id}"
    )

    assert reconciliation_response.status_code == 200

    data = reconciliation_response.json()

    assert data["batch_id"] == batch_id
    assert data["total"] == 10
    assert data["matched"] == 9
    assert data["review"] == 1
    assert data["unresolved"] == 0
    assert data["exceptions"] == 0

    results = data["results"]

    assert len(results) == 10

    # ---------------------------------------------------------
    # HUMAN REVIEW RESULT
    # ---------------------------------------------------------

    exception = next(
        result
        for result in results
        if result["status"] == "HUMAN_REVIEW"
    )

    assert exception["order_id"] == "ORD0001"
    assert exception["payment_id"] == "PAY0001"
    assert exception["settlement_id"] == "SET0001"
    assert exception["bank_transaction_id"] == "BTX0001"

    assert exception["method"] == "NONE"
    assert exception["confidence"] == 1.0
    assert (
        exception["reason"]
        == "Order amount does not match payment amount."
    )

    # ---------------------------------------------------------
    # MATCHED RESULTS
    # ---------------------------------------------------------

    matched_results = [
        result
        for result in results
        if result["status"] == "AUTO_RESOLVED"
    ]

    assert len(matched_results) == 9

    for result in matched_results:
        assert result["method"] == "EXACT"
        assert result["confidence"] == 1.0


def test_reconciliation_run_endpoint():
    with (
        open("data/test_orders.csv", "rb") as orders,
        open("data/test_payments.csv", "rb") as payments,
        open("data/test_settlements.csv", "rb") as settlements,
        open("data/test_bank.csv", "rb") as bank,
    ):
        upload_response = client.post(
            "/upload",
            files={
                "orders": (
                    "test_orders.csv",
                    orders,
                    "text/csv",
                ),
                "payments": (
                    "test_payments.csv",
                    payments,
                    "text/csv",
                ),
                "settlements": (
                    "test_settlements.csv",
                    settlements,
                    "text/csv",
                ),
                "bank": (
                    "test_bank.csv",
                    bank,
                    "text/csv",
                ),
            },
        )

    assert upload_response.status_code == 200

    batch_id = upload_response.json()["batch_id"]

    response = client.post(
        "/reconciliation/run",
        json={"batch_id": batch_id},
    )

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "batch_id": batch_id,
        "total": 10,
        "auto_resolved": 9,
        "ai_suggested": 0,
        "human_review": 1,
    }

    response = client.post(
        "/reconciliation/run",
        json={"batch_id": batch_id},
    )

    assert response.status_code == 200
    assert response.json() == data

    connection = get_connection()
    try:
        result_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM reconciliation_results
            WHERE batch_id = %s
            """,
            (batch_id,),
        ).fetchone()[0]

        exception_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM exceptions
            WHERE batch_id = %s
            """,
            (batch_id,),
        ).fetchone()[0]

        audit_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_logs
            WHERE batch_id = %s
            """,
            (batch_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert result_count == 10
    assert exception_count == 1
    assert audit_count == 10


def _create_test_batch(batch_id: str):
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO upload_batches (batch_id, uploaded_at)
            VALUES (%s, %s)
            ON CONFLICT (batch_id) DO NOTHING
            """,
            (batch_id, "2026-01-01T00:00:00+00:00"),
        )
        connection.commit()
    finally:
        connection.close()


def test_human_review_list_and_get():
    _create_test_batch("TEST-API-REVIEW")

    review = create_or_get_review(
        batch_id="TEST-API-REVIEW",
        order_id="ORD-API",
        payment_id="PAY-API",
        settlement_id="SET-API",
        bank_transaction_id="BTX-API",
        original_decision="REVIEW",
        reason="Requires human verification.",
    )

    review_id = review["review_id"]

    response = client.get(
        "/reconciliation/TEST-API-REVIEW/reviews"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["batch_id"] == "TEST-API-REVIEW"
    assert data["total"] == 1
    assert data["reviews"][0]["review_id"] == review_id

    response = client.get(
        f"/reconciliation/TEST-API-REVIEW/reviews/{review_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["review_id"] == review_id
    assert data["original_decision"] == "REVIEW"
    assert data["final_decision"] is None

    _cleanup_human_review("TEST-API-REVIEW")


def test_human_review_approve():
    _create_test_batch("TEST-API-APPROVE")

    review = create_or_get_review(
        batch_id="TEST-API-APPROVE",
        order_id="ORD-APPROVE",
        payment_id="PAY-APPROVE",
        settlement_id="SET-APPROVE",
        bank_transaction_id="BTX-APPROVE",
        original_decision="REVIEW",
        reason="Requires approval.",
    )

    review_id = review["review_id"]

    response = client.post(
        f"/reconciliation/TEST-API-APPROVE/reviews/{review_id}/approve",
        json={
            "reviewer": "self",
            "reason": "Verified supporting records.",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["review_id"] == review_id
    assert data["original_decision"] == "REVIEW"
    assert data["final_decision"] == "APPROVE"
    assert data["reviewer"] == "self"
    assert data["reviewed_at"] is not None
    assert data["reason"] == "Verified supporting records."

    _cleanup_human_review("TEST-API-APPROVE")


def test_human_review_reject():
    _create_test_batch("TEST-API-REJECT")

    review = create_or_get_review(
        batch_id="TEST-API-REJECT",
        order_id="ORD-REJECT",
        payment_id="PAY-REJECT",
        settlement_id="SET-REJECT",
        bank_transaction_id="BTX-REJECT",
        original_decision="REVIEW",
        reason="Requires rejection decision.",
    )

    review_id = review["review_id"]

    response = client.post(
        f"/reconciliation/TEST-API-REJECT/reviews/{review_id}/reject",
        json={
            "reviewer": "self",
            "reason": "Transaction evidence does not support the match.",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["review_id"] == review_id
    assert data["original_decision"] == "REVIEW"
    assert data["final_decision"] == "REJECT"
    assert data["reviewer"] == "self"
    assert data["reviewed_at"] is not None
    assert (
        data["reason"]
        == "Transaction evidence does not support the match."
    )

    _cleanup_human_review("TEST-API-REJECT")


def test_human_review_invalid_review_id():

    response = client.post(
        "/reconciliation/TEST-NOT-FOUND/reviews/REV-NOT-FOUND/approve",
        json={
            "reviewer": "self",
            "reason": "Test.",
        },
    )

    assert response.status_code == 404


def test_human_review_wrong_batch():
    _create_test_batch("TEST-CORRECT-BATCH")

    review = create_or_get_review(
        batch_id="TEST-CORRECT-BATCH",
        order_id="ORD-WRONG-BATCH",
        payment_id="PAY-WRONG-BATCH",
        settlement_id="SET-WRONG-BATCH",
        bank_transaction_id="BTX-WRONG-BATCH",
        original_decision="REVIEW",
        reason="Testing batch validation.",
    )

    response = client.post(
        f"/reconciliation/TEST-WRONG-BATCH/reviews/{review['review_id']}/approve",
        json={
            "reviewer": "self",
            "reason": "Test.",
        },
    )

    assert response.status_code == 404

    _cleanup_human_review("TEST-CORRECT-BATCH")


def test_human_review_cannot_be_resolved_twice():
    _create_test_batch("TEST-DOUBLE-RESOLVE")

    review = create_or_get_review(
        batch_id="TEST-DOUBLE-RESOLVE",
        order_id="ORD-DOUBLE",
        payment_id="PAY-DOUBLE",
        settlement_id="SET-DOUBLE",
        bank_transaction_id="BTX-DOUBLE",
        original_decision="REVIEW",
        reason="Testing duplicate resolution.",
    )

    review_id = review["review_id"]

    response = client.post(
        f"/reconciliation/TEST-DOUBLE-RESOLVE/reviews/{review_id}/approve",
        json={
            "reviewer": "self",
            "reason": "First resolution.",
        },
    )

    assert response.status_code == 200

    response = client.post(
        f"/reconciliation/TEST-DOUBLE-RESOLVE/reviews/{review_id}/reject",
        json={
            "reviewer": "self",
            "reason": "Second resolution should fail.",
        },
    )

    assert response.status_code == 400
    assert "already been resolved" in response.json()["detail"]

    _cleanup_human_review("TEST-DOUBLE-RESOLVE")


def test_human_review_requires_reviewer_and_reason():
    _create_test_batch("TEST-VALIDATION")

    review = create_or_get_review(
        batch_id="TEST-VALIDATION",
        order_id="ORD-VALIDATION",
        payment_id="PAY-VALIDATION",
        settlement_id="SET-VALIDATION",
        bank_transaction_id="BTX-VALIDATION",
        original_decision="REVIEW",
        reason="Testing validation.",
    )

    review_id = review["review_id"]

    response = client.post(
        f"/reconciliation/TEST-VALIDATION/reviews/{review_id}/approve",
        json={
            "reviewer": "",
            "reason": "",
        },
    )

    assert response.status_code == 400

    _cleanup_human_review("TEST-VALIDATION")


def test_reconciliation_review_creates_human_review_record():
    _create_test_batch("TEST-AUTO-REVIEW")

    from backend.app.reconciliation.decision_engine import (
        MatchDecision,
    )
    from backend.app.reconciliation.human_review import (
        get_review,
    )

    batch_id = "TEST-AUTO-REVIEW"

    review_decision = MatchDecision(
        status="REVIEW",
        method="SIMILARITY",
        confidence=0.70,
        reason="Requires human verification.",
        order_id="ORD-AUTO",
        payment_id="PAY-AUTO",
        settlement_id="SET-AUTO",
        bank_transaction_id="BTX-AUTO",
    )

    review = create_or_get_review(
        batch_id=batch_id,
        order_id=review_decision.order_id,
        payment_id=review_decision.payment_id,
        settlement_id=review_decision.settlement_id,
        bank_transaction_id=review_decision.bank_transaction_id,
        original_decision=review_decision.status,
        reason=review_decision.reason,
    )

    review_id = review["review_id"]

    assert review_id.startswith("REV-")

    persisted = get_review(review_id)

    assert persisted is not None
    assert persisted["review_id"] == review_id
    assert persisted["batch_id"] == batch_id
    assert persisted["order_id"] == "ORD-AUTO"
    assert persisted["payment_id"] == "PAY-AUTO"
    assert persisted["settlement_id"] == "SET-AUTO"
    assert persisted["bank_transaction_id"] == "BTX-AUTO"
    assert persisted["original_decision"] == "REVIEW"
    assert persisted["final_decision"] is None
    assert persisted["reviewer"] is None
    assert persisted["reviewed_at"] is None
    assert persisted["reason"] == "Requires human verification."

    connection = get_connection()

    try:
        connection.execute(
            "DELETE FROM human_reviews WHERE batch_id = %s",
            (batch_id,),
        )
        connection.commit()
    finally:
        connection.close()


def _cleanup_human_review(batch_id: str):

    connection = get_connection()

    try:
        connection.execute(
            "DELETE FROM human_reviews WHERE batch_id = %s",
            (batch_id,),
        )
        connection.commit()
    finally:
        connection.close()
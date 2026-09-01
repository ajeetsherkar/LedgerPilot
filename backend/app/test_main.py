from fastapi.testclient import TestClient

from backend.app.main import app


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
    assert data["review"] == 0
    assert data["unresolved"] == 0
    assert data["exceptions"] == 1

    results = data["results"]

    assert len(results) == 10

    # ---------------------------------------------------------
    # EXCEPTION RESULT
    # ---------------------------------------------------------

    exception = next(
        result
        for result in results
        if result["status"] == "EXCEPTION"
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
        if result["status"] == "MATCH"
    ]

    assert len(matched_results) == 9

    for result in matched_results:
        assert result["method"] == "EXACT"
        assert result["confidence"] == 1.0
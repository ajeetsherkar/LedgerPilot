from backend.app.database import get_connection, initialize_database
from backend.app.reconciliation.batch_loader import load_batch


def test_load_batch_returns_records():
    initialize_database()

    connection = get_connection()

    connection.execute(
        "DELETE FROM raw_records WHERE batch_id = ?",
        ("TEST-BATCH",),
    )

    connection.execute(
        "DELETE FROM upload_batches WHERE batch_id = ?",
        ("TEST-BATCH",),
    )

    connection.execute(
        """
        INSERT INTO upload_batches (
            batch_id,
            uploaded_at
        )
        VALUES (?, ?)
        """,
        ("TEST-BATCH", "2026-09-01T00:00:00+00:00"),
    )

    connection.execute(
        """
        INSERT INTO raw_records (
            batch_id,
            source,
            row_number,
            payload
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "TEST-BATCH",
            "orders",
            1,
            '{"order_id": "ORD-1", "order_amount": "100"}',
        ),
    )

    connection.commit()
    connection.close()

    orders, payments, settlements, banks = load_batch("TEST-BATCH")

    assert len(orders) == 1
    assert orders[0]["order_id"] == "ORD-1"
    assert payments == []
    assert settlements == []
    assert banks == []

import json

from backend.app.database import get_connection


EXPECTED_SOURCES = {
    "orders",
    "payments",
    "settlements",
    "bank",
}


def load_batch(batch_id: str):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT source, payload
            FROM raw_records
            WHERE batch_id = ?
            ORDER BY source, row_number
            """,
            (batch_id,),
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        raise ValueError(f"Batch not found: {batch_id}")

    datasets = {
        "orders": [],
        "payments": [],
        "settlements": [],
        "bank": [],
    }

    for row in rows:
        source = row["source"]

        if source in datasets:
            datasets[source].append(
                json.loads(row["payload"])
            )

    return (
        datasets["orders"],
        datasets["payments"],
        datasets["settlements"],
        datasets["bank"],
    )
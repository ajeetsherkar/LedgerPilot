import json

from psycopg.rows import dict_row

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
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT source, payload
                FROM raw_records
                WHERE batch_id = %s
                ORDER BY source, row_number
                """,
                (batch_id,),
            )
            rows = cursor.fetchall()
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

import json
import sqlite3
import uuid
from datetime import datetime, timezone

import pandas as pd

from backend.app.database import get_connection


EXPECTED_FILES = {
    "orders": "orders",
    "payments": "payments",
    "settlements": "settlements",
    "bank": "bank",
}


def create_batch_id():
    return f"BATCH-{uuid.uuid4().hex[:12].upper()}"


def ingest_csv_files(
    orders_file,
    payments_file,
    settlements_file,
    bank_file,
):
    files = {
        "orders": orders_file,
        "payments": payments_file,
        "settlements": settlements_file,
        "bank": bank_file,
    }

    dataframes = {}

    for source, upload_file in files.items():
        dataframe = pd.read_csv(upload_file.file)

        if dataframe.empty:
            raise ValueError(f"{source}.csv is empty")

        dataframes[source] = dataframe

    batch_id = create_batch_id()

    uploaded_at = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO upload_batches (
                batch_id,
                uploaded_at
            )
            VALUES (?, ?)
            """,
            (batch_id, uploaded_at),
        )

        total_records = 0

        for source, dataframe in dataframes.items():
            for row_number, record in enumerate(
                dataframe.to_dict(orient="records"),
                start=1,
            ):
                payload = json.dumps(
                    record,
                    default=str,
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
                        batch_id,
                        source,
                        row_number,
                        payload,
                    ),
                )

                total_records += 1

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return {
        "batch_id": batch_id,
        "records_uploaded": total_records,
        "files": {
            source: len(dataframe)
            for source, dataframe in dataframes.items()
        },
    }

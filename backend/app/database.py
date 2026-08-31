import sqlite3
from pathlib import Path


DB_PATH = Path("data/ledgerpilot.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS upload_batches (
            batch_id TEXT PRIMARY KEY,
            uploaded_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            source TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            payload TEXT NOT NULL,
            FOREIGN KEY (batch_id) REFERENCES upload_batches(batch_id)
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_raw_records_batch_id
        ON raw_records(batch_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_raw_records_source
        ON raw_records(source)
        """
    )

    connection.commit()
    connection.close()

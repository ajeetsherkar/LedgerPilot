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

    initialize_human_review_table(connection)

    connection.commit()
    connection.close()


# ---------------------------------------------------------
# HUMAN REVIEW
# ---------------------------------------------------------

def initialize_human_review_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS human_reviews (
            review_id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL,

            order_id TEXT,
            payment_id TEXT,
            settlement_id TEXT,
            bank_transaction_id TEXT,

            original_decision TEXT NOT NULL,
            final_decision TEXT,

            reviewer TEXT,
            reviewed_at TEXT,
            reason TEXT,

            created_at TEXT NOT NULL,

            FOREIGN KEY (batch_id)
                REFERENCES upload_batches(batch_id)
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_human_reviews_batch_id
        ON human_reviews(batch_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_human_reviews_status
        ON human_reviews(final_decision)
        """
    )



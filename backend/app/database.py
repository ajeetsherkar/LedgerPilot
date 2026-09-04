import os

import psycopg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ledgerpilot:ledgerpilot_dev@localhost:5432/ledgerpilot",
)


def get_connection():
    return psycopg.connect(DATABASE_URL)


def initialize_database():
    connection = get_connection()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_batches (
                batch_id TEXT PRIMARY KEY,
                uploaded_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_records (
                id BIGSERIAL PRIMARY KEY,
                batch_id TEXT NOT NULL,
                source TEXT NOT NULL,
                row_number INTEGER NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY (batch_id)
                    REFERENCES upload_batches(batch_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_raw_records_batch_id
            ON raw_records(batch_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_raw_records_source
            ON raw_records(source)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                chain_id TEXT,
                merchant_id TEXT,
                customer_id TEXT,
                customer_name TEXT,
                order_amount NUMERIC(12, 2),
                currency TEXT,
                order_date DATE,
                status TEXT,
                FOREIGN KEY (batch_id)
                    REFERENCES upload_batches(batch_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                chain_id TEXT,
                order_id TEXT,
                payment_method TEXT,
                upi_ref TEXT,
                amount NUMERIC(12, 2),
                currency TEXT,
                payment_date DATE,
                status TEXT,
                FOREIGN KEY (batch_id)
                    REFERENCES upload_batches(batch_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settlements (
                settlement_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                chain_id TEXT,
                payment_id TEXT,
                gross_amount NUMERIC(12, 2),
                platform_fee NUMERIC(12, 2),
                gst_on_fee NUMERIC(12, 2),
                net_amount NUMERIC(12, 2),
                settlement_date DATE,
                settlement_reference TEXT,
                FOREIGN KEY (batch_id)
                    REFERENCES upload_batches(batch_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_transactions (
                transaction_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                chain_id TEXT,
                transaction_date DATE,
                credit_amount NUMERIC(12, 2),
                currency TEXT,
                narration TEXT,
                reference TEXT,
                FOREIGN KEY (batch_id)
                    REFERENCES upload_batches(batch_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reconciliation_results (
                result_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                order_id TEXT,
                payment_id TEXT,
                settlement_id TEXT,
                bank_transaction_id TEXT,
                status TEXT NOT NULL,
                method TEXT NOT NULL,
                confidence NUMERIC(6, 5) NOT NULL,
                confidence_bucket TEXT NOT NULL,
                reason TEXT NOT NULL,
                candidate JSONB,
                ai_reasoning JSONB,
                exception_type TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (batch_id)
                    REFERENCES upload_batches(batch_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reconciliation_results_batch_id
            ON reconciliation_results(batch_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reconciliation_results_status
            ON reconciliation_results(status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reconciliation_results_exception
            ON reconciliation_results(exception_type)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS exceptions (
                exception_id TEXT PRIMARY KEY,
                result_id TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                exception_type TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (result_id)
                    REFERENCES reconciliation_results(result_id),
                FOREIGN KEY (batch_id)
                    REFERENCES upload_batches(batch_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_exceptions_batch_id
            ON exceptions(batch_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_exceptions_type
            ON exceptions(exception_type)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                audit_id TEXT PRIMARY KEY,
                batch_id TEXT,
                result_id TEXT,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                details JSONB,
                created_at TEXT NOT NULL,
                FOREIGN KEY (batch_id)
                    REFERENCES upload_batches(batch_id),
                FOREIGN KEY (result_id)
                    REFERENCES reconciliation_results(result_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_batch_id
            ON audit_logs(batch_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_result_id
            ON audit_logs(result_id)
            """
        )

        initialize_human_review_table(connection)

    connection.commit()
    connection.close()


# ---------------------------------------------------------
# HUMAN REVIEW
# ---------------------------------------------------------

def initialize_human_review_table(connection):
    with connection.cursor() as cursor:
        cursor.execute(
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

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_human_reviews_batch_id
            ON human_reviews(batch_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_human_reviews_status
            ON human_reviews(final_decision)
            """
        )

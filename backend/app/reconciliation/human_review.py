import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.app.database import get_connection


ALLOWED_FINAL_DECISIONS = {
    "APPROVE",
    "REJECT",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_review_id() -> str:
    return f"REV-{uuid.uuid4().hex[:12].upper()}"


def _same_value_clause(column: str) -> str:
    return (
        f"({column} = ? "
        f"OR ({column} IS NULL AND ? IS NULL))"
    )


def create_or_get_review(
    *,
    batch_id: str,
    order_id: Optional[str],
    payment_id: Optional[str],
    settlement_id: Optional[str],
    bank_transaction_id: Optional[str],
    original_decision: str,
    reason: str,
) -> dict[str, Any]:
    """
    Create a pending human-review record for a REVIEW decision.

    If the same transaction already has a review record, return
    the existing record instead of creating a duplicate.
    """

    if original_decision != "REVIEW":
        raise ValueError(
            "Human review can only be created for REVIEW decisions."
        )

    connection = get_connection()

    try:
        query = f"""
            SELECT *
            FROM human_reviews
            WHERE batch_id = ?
              AND {_same_value_clause("order_id")}
              AND {_same_value_clause("payment_id")}
              AND {_same_value_clause("settlement_id")}
              AND {_same_value_clause("bank_transaction_id")}
            ORDER BY created_at DESC
            LIMIT 1
        """

        row = connection.execute(
            query,
            (
                batch_id,
                order_id,
                order_id,
                payment_id,
                payment_id,
                settlement_id,
                settlement_id,
                bank_transaction_id,
                bank_transaction_id,
            ),
        ).fetchone()

        if row is not None:
            return dict(row)

        review_id = _create_review_id()
        created_at = _now()

        connection.execute(
            """
            INSERT INTO human_reviews (
                review_id,
                batch_id,
                order_id,
                payment_id,
                settlement_id,
                bank_transaction_id,
                original_decision,
                final_decision,
                reviewer,
                reviewed_at,
                reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
            """,
            (
                review_id,
                batch_id,
                order_id,
                payment_id,
                settlement_id,
                bank_transaction_id,
                original_decision,
                reason,
                created_at,
            ),
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT *
            FROM human_reviews
            WHERE review_id = ?
            """,
            (review_id,),
        ).fetchone()

        return dict(row)

    finally:
        connection.close()


def get_review(review_id: str) -> Optional[dict[str, Any]]:
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM human_reviews
            WHERE review_id = ?
            """,
            (review_id,),
        ).fetchone()

        return dict(row) if row is not None else None

    finally:
        connection.close()


def resolve_review(
    *,
    review_id: str,
    final_decision: str,
    reviewer: str,
    reason: str,
) -> dict[str, Any]:
    """
    Approve or reject a pending human-review record.
    """

    if final_decision not in ALLOWED_FINAL_DECISIONS:
        raise ValueError(
            "final_decision must be APPROVE or REJECT."
        )

    if not reviewer or not reviewer.strip():
        raise ValueError(
            "reviewer is required."
        )

    if not reason or not reason.strip():
        raise ValueError(
            "reason is required."
        )

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM human_reviews
            WHERE review_id = ?
            """,
            (review_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Human review not found: {review_id}"
            )

        if row["original_decision"] != "REVIEW":
            raise ValueError(
                "Human review has an invalid original decision."
            )

        if row["final_decision"] is not None:
            raise ValueError(
                "Human review has already been resolved."
            )

        reviewed_at = _now()

        connection.execute(
            """
            UPDATE human_reviews
            SET
                final_decision = ?,
                reviewer = ?,
                reviewed_at = ?,
                reason = ?
            WHERE review_id = ?
            """,
            (
                final_decision,
                reviewer.strip(),
                reviewed_at,
                reason.strip(),
                review_id,
            ),
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT *
            FROM human_reviews
            WHERE review_id = ?
            """,
            (review_id,),
        ).fetchone()

        return dict(row)

    finally:
        connection.close()


def list_reviews(
    batch_id: str,
) -> list[dict[str, Any]]:
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM human_reviews
            WHERE batch_id = ?
            ORDER BY created_at
            """,
            (batch_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()

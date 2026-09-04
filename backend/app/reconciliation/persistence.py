from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from backend.app.database import get_connection
from backend.app.reconciliation.decision_engine import MatchDecision


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, float) and value != value:
        return None

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (dict, list, str, int, float, bool)):
        return value

    return str(value)


def _sanitize_json(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, float) and value != value:
        return None

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, dict):
        return {
            key: _sanitize_json(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _sanitize_json(item)
            for item in value
        ]

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None

    return json.dumps(_sanitize_json(value))


def persist_source_records(
    batch_id: str,
    orders: Iterable[dict[str, Any]],
    payments: Iterable[dict[str, Any]],
    settlements: Iterable[dict[str, Any]],
    banks: Iterable[dict[str, Any]],
) -> None:
    """
    Persist the normalized source datasets for a reconciliation batch.

    The raw_records table remains the ingestion source of truth. These
    tables provide queryable, typed representations for application APIs,
    metrics, and auditability.
    """
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            for row in orders:
                cursor.execute(
                    """
                    INSERT INTO orders (
                        order_id,
                        batch_id,
                        chain_id,
                        merchant_id,
                        customer_id,
                        customer_name,
                        order_amount,
                        currency,
                        order_date,
                        status
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (order_id)
                    DO UPDATE SET
                        batch_id = EXCLUDED.batch_id,
                        chain_id = EXCLUDED.chain_id,
                        merchant_id = EXCLUDED.merchant_id,
                        customer_id = EXCLUDED.customer_id,
                        customer_name = EXCLUDED.customer_name,
                        order_amount = EXCLUDED.order_amount,
                        currency = EXCLUDED.currency,
                        order_date = EXCLUDED.order_date,
                        status = EXCLUDED.status
                    """,
                    (
                        row.get("order_id"),
                        batch_id,
                        row.get("chain_id"),
                        row.get("merchant_id"),
                        row.get("customer_id"),
                        row.get("customer_name"),
                        row.get("order_amount"),
                        row.get("currency"),
                        row.get("order_date"),
                        row.get("status"),
                    ),
                )

            for row in payments:
                cursor.execute(
                    """
                    INSERT INTO payments (
                        payment_id,
                        batch_id,
                        chain_id,
                        order_id,
                        payment_method,
                        upi_ref,
                        amount,
                        currency,
                        payment_date,
                        status
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (payment_id)
                    DO UPDATE SET
                        batch_id = EXCLUDED.batch_id,
                        chain_id = EXCLUDED.chain_id,
                        order_id = EXCLUDED.order_id,
                        payment_method = EXCLUDED.payment_method,
                        upi_ref = EXCLUDED.upi_ref,
                        amount = EXCLUDED.amount,
                        currency = EXCLUDED.currency,
                        payment_date = EXCLUDED.payment_date,
                        status = EXCLUDED.status
                    """,
                    (
                        row.get("payment_id"),
                        batch_id,
                        row.get("chain_id"),
                        row.get("order_id"),
                        row.get("payment_method"),
                        row.get("upi_ref"),
                        row.get("amount"),
                        row.get("currency"),
                        row.get("payment_date"),
                        row.get("status"),
                    ),
                )

            for row in settlements:
                cursor.execute(
                    """
                    INSERT INTO settlements (
                        settlement_id,
                        batch_id,
                        chain_id,
                        payment_id,
                        gross_amount,
                        platform_fee,
                        gst_on_fee,
                        net_amount,
                        settlement_date,
                        settlement_reference
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (settlement_id)
                    DO UPDATE SET
                        batch_id = EXCLUDED.batch_id,
                        chain_id = EXCLUDED.chain_id,
                        payment_id = EXCLUDED.payment_id,
                        gross_amount = EXCLUDED.gross_amount,
                        platform_fee = EXCLUDED.platform_fee,
                        gst_on_fee = EXCLUDED.gst_on_fee,
                        net_amount = EXCLUDED.net_amount,
                        settlement_date = EXCLUDED.settlement_date,
                        settlement_reference = EXCLUDED.settlement_reference
                    """,
                    (
                        row.get("settlement_id"),
                        batch_id,
                        row.get("chain_id"),
                        row.get("payment_id"),
                        row.get("gross_amount"),
                        row.get("platform_fee"),
                        row.get("gst_on_fee"),
                        row.get("net_amount"),
                        row.get("settlement_date"),
                        row.get("settlement_reference"),
                    ),
                )

            for row in banks:
                cursor.execute(
                    """
                    INSERT INTO bank_transactions (
                        transaction_id,
                        batch_id,
                        chain_id,
                        transaction_date,
                        credit_amount,
                        currency,
                        narration,
                        reference
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (transaction_id)
                    DO UPDATE SET
                        batch_id = EXCLUDED.batch_id,
                        chain_id = EXCLUDED.chain_id,
                        transaction_date = EXCLUDED.transaction_date,
                        credit_amount = EXCLUDED.credit_amount,
                        currency = EXCLUDED.currency,
                        narration = EXCLUDED.narration,
                        reference = EXCLUDED.reference
                    """,
                    (
                        row.get("transaction_id"),
                        batch_id,
                        row.get("chain_id"),
                        row.get("transaction_date"),
                        row.get("credit_amount"),
                        row.get("currency"),
                        row.get("narration"),
                        row.get("reference"),
                    ),
                )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def persist_decisions(
    batch_id: str,
    decisions: Iterable[MatchDecision],
) -> list[str]:
    """
    Persist reconciliation decisions and their associated exceptions/audit logs.

    Returns the generated reconciliation result IDs in decision order.
    """
    connection = get_connection()
    result_ids: list[str] = []

    try:
        with connection.cursor() as cursor:
            for decision in decisions:
                result_id = f"RES-{uuid.uuid4().hex[:12].upper()}"
                created_at = _utc_now()

                cursor.execute(
                    """
                    INSERT INTO reconciliation_results (
                        result_id,
                        batch_id,
                        order_id,
                        payment_id,
                        settlement_id,
                        bank_transaction_id,
                        status,
                        method,
                        confidence,
                        confidence_bucket,
                        reason,
                        candidate,
                        ai_reasoning,
                        exception_type,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        result_id,
                        batch_id,
                        decision.order_id,
                        decision.payment_id,
                        decision.settlement_id,
                        decision.bank_transaction_id,
                        decision.status,
                        decision.method,
                        decision.confidence,
                        decision.confidence_bucket.value,
                        decision.reason,
                        _json_dump(decision.candidate),
                        _json_dump(decision.ai_reasoning),
                        decision.exception_type,
                        created_at,
                    ),
                )

                if decision.exception_type:
                    exception_id = f"EXC-{uuid.uuid4().hex[:12].upper()}"

                    cursor.execute(
                        """
                        INSERT INTO exceptions (
                            exception_id,
                            result_id,
                            batch_id,
                            exception_type,
                            status,
                            reason,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            exception_id,
                            result_id,
                            batch_id,
                            decision.exception_type,
                            decision.status,
                            decision.reason,
                            created_at,
                        ),
                    )

                audit_id = f"AUD-{uuid.uuid4().hex[:12].upper()}"

                cursor.execute(
                    """
                    INSERT INTO audit_logs (
                        audit_id,
                        batch_id,
                        result_id,
                        event_type,
                        actor,
                        action,
                        details,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        audit_id,
                        batch_id,
                        result_id,
                        "RECONCILIATION_DECISION",
                        "SYSTEM",
                        decision.status,
                        _json_dump(
                            {
                                "method": decision.method,
                                "confidence": decision.confidence,
                                "confidence_bucket": decision.confidence_bucket.value,
                                "reason": decision.reason,
                                "exception_type": decision.exception_type,
                            }
                        ),
                        created_at,
                    ),
                )

                result_ids.append(result_id)

        connection.commit()
        return result_ids

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

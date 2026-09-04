from __future__ import annotations

from decimal import Decimal
from typing import Any


from backend.app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
)


SOURCE_SCHEMAS: dict[str, dict[str, Any]] = {
    "orders": {
        "id_field": "order_id",
        "required": [
            "order_id",
            "order_amount",
            "order_date",
        ],
        "amount_fields": [
            "order_amount",
        ],
        "date_fields": [
            "order_date",
        ],
    },
    "payments": {
        "id_field": "payment_id",
        "required": [
            "payment_id",
            "order_id",
            "amount",
            "payment_date",
        ],
        "amount_fields": [
            "amount",
        ],
        "date_fields": [
            "payment_date",
        ],
    },
    "settlements": {
        "id_field": "settlement_id",
        "required": [
            "settlement_id",
            "payment_id",
            "gross_amount",
            "platform_fee",
            "gst_on_fee",
            "net_amount",
            "settlement_date",
            "settlement_reference",
        ],
        "amount_fields": [
            "gross_amount",
            "platform_fee",
            "gst_on_fee",
            "net_amount",
        ],
        "date_fields": [
            "settlement_date",
        ],
    },
    "bank": {
        "id_field": "transaction_id",
        "required": [
            "transaction_id",
            "transaction_date",
            "credit_amount",
            "reference",
        ],
        "amount_fields": [
            "credit_amount",
        ],
        "date_fields": [
            "transaction_date",
        ],
    },
}


def validate_source_records(
    source: str,
    records: list[dict[str, Any]],
) -> str | None:
    """
    Validate one source dataset.

    Returns:
        None when valid.
        A human-readable validation reason when invalid.
    """
    schema = SOURCE_SCHEMAS.get(source)

    if schema is None:
        return f"Unknown source dataset: {source}"

    if not isinstance(records, list):
        return f"{source} dataset must be a list of records."


    required = schema["required"]
    id_field = schema["id_field"]
    amount_fields = schema["amount_fields"]
    date_fields = schema["date_fields"]

    # ---------------------------------------------------------
    # REQUIRED FIELDS / VALUES
    # ---------------------------------------------------------
    for row_number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            return (
                f"{source}.csv row {row_number} is not a valid record."
            )

        missing = [
            field
            for field in required
            if field not in record
        ]

        if missing:
            return (
                f"{source}.csv row {row_number} is missing "
                f"required field(s): {', '.join(missing)}."
            )

        for field in required:
            value = record.get(field)

            if value is None or str(value).strip() == "":
                return (
                    f"{source}.csv row {row_number} has an empty "
                    f"required field: {field}."
                )

        # -----------------------------------------------------
        # AMOUNT VALIDATION
        # -----------------------------------------------------
        for field in amount_fields:
            try:
                amount = normalize_amount(record[field])
                if not amount.is_finite():
                    raise ValueError("Amount must be finite.")
            except (TypeError, ValueError, ArithmeticError) as exc:
                return (
                    f"{source}.csv row {row_number} has invalid "
                    f"amount in '{field}': {exc}"
                )

        # -----------------------------------------------------
        # DATE VALIDATION
        # -----------------------------------------------------
        for field in date_fields:
            try:
                normalize_date(record[field])
            except (TypeError, ValueError) as exc:
                return (
                    f"{source}.csv row {row_number} has invalid "
                    f"date in '{field}': {exc}"
                )

    # ---------------------------------------------------------
    # DUPLICATE ID VALIDATION
    # ---------------------------------------------------------
    seen_ids: set[str] = set()

    for row_number, record in enumerate(records, start=1):
        record_id = str(record[id_field]).strip()

        if record_id in seen_ids:
            return (
                f"{source}.csv row {row_number} contains duplicate "
                f"{id_field}: {record_id}."
            )

        seen_ids.add(record_id)

    return None


def validate_reconciliation_inputs(
    orders: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    banks: list[dict[str, Any]],
) -> str | None:
    """
    Validate all four reconciliation source datasets.

    Returns:
        None when all inputs are valid.
        A human-readable validation reason otherwise.
    """
    datasets = {
        "orders": orders,
        "payments": payments,
        "settlements": settlements,
        "bank": banks,
    }

    for source, records in datasets.items():
        error = validate_source_records(source, records)

        if error is not None:
            return error

    return None

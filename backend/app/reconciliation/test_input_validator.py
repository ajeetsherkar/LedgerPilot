from backend.app.reconciliation.input_validator import (
    validate_source_records,
)


def valid_order(order_id="ORD001"):
    return {
        "order_id": order_id,
        "order_amount": "1000.00",
        "order_date": "2026-08-26",
    }


def test_missing_required_column_is_rejected():
    record = valid_order()
    del record["order_amount"]

    result = validate_source_records(
        "orders",
        [record],
    )

    assert result is not None
    assert "missing required field" in result
    assert "order_amount" in result


def test_invalid_amount_is_rejected():
    record = valid_order()
    record["order_amount"] = "NOT-A-NUMBER"

    result = validate_source_records(
        "orders",
        [record],
    )

    assert result is not None
    assert "invalid amount" in result
    assert "order_amount" in result


def test_invalid_date_is_rejected():
    record = valid_order()
    record["order_date"] = "NOT-A-DATE"

    result = validate_source_records(
        "orders",
        [record],
    )

    assert result is not None
    assert "invalid date" in result
    assert "order_date" in result


def test_duplicate_id_is_rejected():
    result = validate_source_records(
        "orders",
        [
            valid_order("ORD001"),
            valid_order("ORD001"),
        ],
    )

    assert result is not None
    assert "duplicate" in result
    assert "ORD001" in result


def test_valid_records_are_accepted():
    result = validate_source_records(
        "orders",
        [
            valid_order("ORD001"),
            valid_order("ORD002"),
        ],
    )

    assert result is None

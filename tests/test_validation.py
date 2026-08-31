from datetime import date, datetime
import random

from scripts.generate_data import generate_dataset
from scripts.exceptions import apply_exceptions


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def generate_clean_and_corrupted(seed=42, size=100):
    orders, payments, settlements, banks = generate_dataset(size)

    (
        corrupted_orders,
        corrupted_payments,
        corrupted_settlements,
        corrupted_banks,
    ) = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(seed),
    )

    return (
        orders,
        payments,
        settlements,
        banks,
        corrupted_orders,
        corrupted_payments,
        corrupted_settlements,
        corrupted_banks,
    )


def assert_unique_ids(records, id_field):
    ids = [record[id_field] for record in records]

    assert all(value is not None and str(value).strip() for value in ids), (
        f"Missing/empty {id_field}"
    )

    assert len(ids) == len(set(ids)), (
        f"Duplicate {id_field} values found"
    )


def assert_numeric_non_negative(records, amount_field):
    for record in records:
        value = record[amount_field]

        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise AssertionError(
                f"{amount_field} is not numeric: {value!r}"
            ) from exc

        assert numeric_value >= 0, (
            f"Negative {amount_field}: {numeric_value}"
        )


def assert_parseable_dates(records, date_field):
    for record in records:
        value = record[date_field]

        if isinstance(value, (date, datetime)):
            continue

        if isinstance(value, str):
            try:
                datetime.fromisoformat(value)
            except ValueError as exc:
                raise AssertionError(
                    f"Unparseable {date_field}: {value!r}"
                ) from exc
            continue

        raise AssertionError(
            f"Invalid {date_field} type: {type(value).__name__}"
        )


# ---------------------------------------------------------
# 1. ID VALIDATION
# ---------------------------------------------------------

def test_clean_dataset_has_no_duplicate_ids():
    (
        orders,
        payments,
        settlements,
        banks,
        *_,
    ) = generate_clean_and_corrupted()

    assert_unique_ids(orders, "order_id")
    assert_unique_ids(payments, "payment_id")
    assert_unique_ids(settlements, "settlement_id")
    assert_unique_ids(banks, "transaction_id")


# ---------------------------------------------------------
# 2. AMOUNT VALIDATION
# ---------------------------------------------------------

def test_clean_amounts_are_numeric_and_non_negative():
    (
        orders,
        payments,
        settlements,
        banks,
        *_,
    ) = generate_clean_and_corrupted()

    assert_numeric_non_negative(orders, "order_amount")
    assert_numeric_non_negative(payments, "amount")

    assert_numeric_non_negative(settlements, "gross_amount")
    assert_numeric_non_negative(settlements, "platform_fee")
    assert_numeric_non_negative(settlements, "gst_on_fee")
    assert_numeric_non_negative(settlements, "net_amount")

    assert_numeric_non_negative(banks, "credit_amount")


# ---------------------------------------------------------
# 3. DATE VALIDATION
# ---------------------------------------------------------

def test_clean_dates_are_parseable():
    (
        orders,
        payments,
        settlements,
        banks,
        *_,
    ) = generate_clean_and_corrupted()

    assert_parseable_dates(orders, "order_date")
    assert_parseable_dates(payments, "payment_date")
    assert_parseable_dates(settlements, "settlement_date")
    assert_parseable_dates(banks, "transaction_date")


# ---------------------------------------------------------
# 4. ORDER → PAYMENT
# ---------------------------------------------------------

def test_order_to_payment_relationship_is_valid():
    (
        orders,
        payments,
        settlements,
        banks,
        *_,
    ) = generate_clean_and_corrupted()

    order_ids = {
        order["order_id"]
        for order in orders
    }

    for payment in payments:
        assert payment["order_id"] in order_ids


# ---------------------------------------------------------
# 5. PAYMENT → SETTLEMENT
# ---------------------------------------------------------

def test_payment_to_settlement_relationship_is_valid():
    (
        orders,
        payments,
        settlements,
        banks,
        *_,
    ) = generate_clean_and_corrupted()

    payment_ids = {
        payment["payment_id"]
        for payment in payments
    }

    for settlement in settlements:
        assert settlement["payment_id"] in payment_ids


# ---------------------------------------------------------
# 6. SETTLEMENT → BANK
# ---------------------------------------------------------

def test_settlement_to_bank_relationship_is_valid():
    (
        orders,
        payments,
        settlements,
        banks,
        *_,
    ) = generate_clean_and_corrupted()

    bank_references = {
        bank["reference"]
        for bank in banks
    }

    for settlement in settlements:
        assert settlement["settlement_reference"] in bank_references


# ---------------------------------------------------------
# 7. CLEAN FINANCIAL INVARIANT
# ---------------------------------------------------------

def test_clean_settlement_amounts_are_consistent():
    (
        orders,
        payments,
        settlements,
        banks,
        *_,
    ) = generate_clean_and_corrupted()

    for settlement in settlements:
        gross = float(settlement["gross_amount"])
        fee = float(settlement["platform_fee"])
        gst = float(settlement["gst_on_fee"])
        net = float(settlement["net_amount"])

        expected_net = gross - fee - gst

        assert abs(expected_net - net) < 1e-9, (
            f"Settlement {settlement['settlement_id']} violates "
            f"gross - fee - GST = net"
        )


# ---------------------------------------------------------
# 8. GROUND-TRUTH TRACEABILITY
# ---------------------------------------------------------

def test_corrupted_chains_remain_traceable_to_ground_truth():
    (
        orders,
        payments,
        settlements,
        banks,
        corrupted_orders,
        corrupted_payments,
        corrupted_settlements,
        corrupted_banks,
    ) = generate_clean_and_corrupted()

    # Clean IDs are the authoritative ground truth.
    clean_chain_ids = {
        order["chain_id"]
        for order in orders
    }

    clean_order_ids = {
        order["order_id"]
        for order in orders
    }

    clean_payment_ids = {
        payment["payment_id"]
        for payment in payments
    }

    clean_settlement_ids = {
        settlement["settlement_id"]
        for settlement in settlements
    }

    clean_bank_ids = {
        bank["transaction_id"]
        for bank in banks
    }

    # Corruption must not destroy the original chain identity.
    corrupted_chain_ids = {
        order["chain_id"]
        for order in corrupted_orders
    }

    assert clean_chain_ids <= corrupted_chain_ids

    # Original order/payment/settlement records remain traceable.
    corrupted_order_ids = {
        order["order_id"]
        for order in corrupted_orders
    }

    corrupted_payment_ids = {
        payment["payment_id"]
        for payment in corrupted_payments
    }

    corrupted_settlement_ids = {
        settlement["settlement_id"]
        for settlement in corrupted_settlements
    }

    corrupted_bank_ids = {
        bank["transaction_id"]
        for bank in corrupted_banks
    }

    assert clean_order_ids <= corrupted_order_ids
    assert clean_payment_ids <= corrupted_payment_ids
    assert clean_settlement_ids <= corrupted_settlement_ids

    # Bank records may intentionally be removed by MISSING_BANK,
    # so we do not require every original bank transaction to remain.


# ---------------------------------------------------------
# 9. CORRUPTION MUST BE INTENTIONAL
# ---------------------------------------------------------

def test_corruption_is_detectable_against_clean_ground_truth():
    (
        orders,
        payments,
        settlements,
        banks,
        corrupted_orders,
        corrupted_payments,
        corrupted_settlements,
        corrupted_banks,
    ) = generate_clean_and_corrupted()

    assert (
        corrupted_orders != orders
        or corrupted_payments != payments
        or corrupted_settlements != settlements
        or corrupted_banks != banks
    )


# ---------------------------------------------------------
# 10. EXCEPTION PRESENCE # Seven unique exception types are implemented.
# ---------------------------------------------------------

def test_all_exception_scenarios_are_present():
    orders, payments, settlements, banks = generate_dataset(100)

    events = []

    (
        _,
        _,
        _,
        _,
    ) = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        events=events,
    )

    # Seven unique exception types are implemented.
    expected_exception_types = {
        "DATE_DRIFT",
        "AMOUNT_MISMATCH",
        "MISSING_BANK",
        "DUPLICATE",
        "FUZZY_REFERENCE",
        "PARTIAL_SETTLEMENT",
        "COMBINED_SETTLEMENT",
    }

    exception_types = {
        event["exception_type"]
        for event in events
    }

    missing = expected_exception_types - exception_types

    assert not missing, (
        f"Missing exception scenarios: {sorted(missing)}"
    )

    # Eight scenario events are expected because
    # COMBINED_SETTLEMENT produces two event records.
    assert len(events) >= 8, (
        f"Expected at least 8 exception events, got {len(events)}"
    )


# ---------------------------------------------------------
# 11. EXCEPTION EVENTS MUST BE TRACEABLE
# ---------------------------------------------------------

def test_exception_events_reference_ground_truth_chains():
    orders, payments, settlements, banks = generate_dataset(100)

    events = []

    apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        events=events,
    )

    clean_chains = {
        order["chain_id"]
        for order in orders
    }

    clean_payments = {
        payment["payment_id"]
        for payment in payments
    }

    clean_settlements = {
        settlement["settlement_id"]
        for settlement in settlements
    }

    clean_banks = {
        bank["transaction_id"]
        for bank in banks
    }

    for event in events:
        assert event["chain_id"] in clean_chains

        if event.get("payment_id") is not None:
            assert event["payment_id"] in clean_payments

        if event.get("settlement_id") is not None:
            assert event["settlement_id"] in clean_settlements

        if event.get("bank_transaction_id") is not None:
            assert event["bank_transaction_id"] in clean_banks


# ---------------------------------------------------------
# 12. CLEAN CHAINS SATISFY FINANCIAL INVARIANT
# ---------------------------------------------------------

def test_every_clean_chain_satisfies_financial_invariant():
    (
        orders,
        payments,
        settlements,
        banks,
        *_,
    ) = generate_clean_and_corrupted()

    for settlement in settlements:
        gross = float(settlement["gross_amount"])
        fee = float(settlement["platform_fee"])
        gst = float(settlement["gst_on_fee"])
        net = float(settlement["net_amount"])

        assert abs((gross - fee - gst) - net) < 1e-9


# ---------------------------------------------------------
# 13. EVENTS ARE NOT EMPTY
# ---------------------------------------------------------

def test_exception_generation_produces_events():
    orders, payments, settlements, banks = generate_dataset(100)

    events = []

    apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(42),
        events=events,
    )

    assert events, "No exception events were generated"

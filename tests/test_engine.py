from backend.app.reconciliation.engine import (
    load_datasets,
    reconcile_all,
    reconcile_order,
)


def test_load_datasets():
    orders, payments, settlements, bank_transactions = load_datasets()

    assert len(orders) == 10
    assert len(payments) == 10
    assert len(settlements) == 10
    assert len(bank_transactions) == 10


def test_reconcile_all():
    results = reconcile_all()

    assert len(results) == 10

    for result in results:
        assert result.reconciliation_status == "MATCHED"
        assert result.exception_type == "MATCHED"


def test_payment_mismatch():
    orders, payments, settlements, banks = load_datasets()

    payment = payments[0].copy()
    payment["paid_amount"] = str(
        float(payment["paid_amount"]) + 100
    )

    bank_by_reference = {
        bank["transaction_ref"]: bank
        for bank in banks
    }

    bank = bank_by_reference.get(payment["transaction_ref"])

    result = reconcile_order(
        orders[0],
        payment,
        settlements[0],
        bank,
    )

    assert result.payment_status == "MISMATCH"
    assert result.reconciliation_status == "EXCEPTION"
    assert result.exception_type == "PAYMENT_MISMATCH"
    assert result.difference == 100.0


def test_settlement_mismatch():
    orders, payments, settlements, banks = load_datasets()

    settlement = settlements[1].copy()
    settlement["settled_amount"] = str(
        float(settlement["settled_amount"]) + 50
    )

    bank_by_reference = {
        bank["transaction_ref"]: bank
        for bank in banks
    }

    bank = bank_by_reference.get(
        payments[1]["transaction_ref"]
    )

    result = reconcile_order(
        orders[1],
        payments[1],
        settlement,
        bank,
    )

    assert result.settlement_status == "MISMATCH"
    assert result.reconciliation_status == "EXCEPTION"
    assert result.exception_type == "SETTLEMENT_MISMATCH"
    assert result.difference == 50.0


def test_bank_mismatch():
    orders, payments, settlements, banks = load_datasets()

    bank_by_reference = {
        bank["transaction_ref"]: bank.copy()
        for bank in banks
    }

    transaction_ref = payments[2]["transaction_ref"]

    bank = bank_by_reference[transaction_ref]

    bank["amount"] = str(
        float(bank["amount"]) + 75
    )

    result = reconcile_order(
        orders[2],
        payments[2],
        settlements[2],
        bank,
    )

    assert result.bank_status == "MISMATCH"
    assert result.reconciliation_status == "EXCEPTION"
    assert result.exception_type == "BANK_MISMATCH"
    assert result.difference == 75.0
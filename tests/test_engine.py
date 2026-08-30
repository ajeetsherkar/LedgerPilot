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
        assert result.exception_type is None


def _bank_for_payment(payment, settlements, banks):
    """Resolve the bank record for a payment via the settlement chain:
    payment -> settlement (by payment_id) -> bank (by settlement_reference)."""
    payment_id = payment["payment_id"]

    settlement = next(
        settlement
        for settlement in settlements
        if settlement["payment_id"] == payment_id
    )

    settlement_reference = settlement["settlement_reference"]

    bank_by_reference = {
        bank["reference"]: bank
        for bank in banks
    }

    return bank_by_reference.get(settlement_reference)


def test_payment_mismatch():
    orders, payments, settlements, banks = load_datasets()

    payment = payments[0].copy()
    payment["amount"] = str(
        float(payment["amount"]) + 100
    )

    bank = _bank_for_payment(payment, settlements, banks)

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
    settlement["net_amount"] = str(
        float(settlement["net_amount"]) + 50
    )

    bank = _bank_for_payment(payments[1], settlements, banks)

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
        bank["reference"]: bank.copy()
        for bank in banks
    }

    payment_id = payments[2]["payment_id"]

    settlement = next(
        settlement
        for settlement in settlements
        if settlement["payment_id"] == payment_id
    )

    settlement_reference = settlement["settlement_reference"]

    bank = bank_by_reference[settlement_reference]

    bank["credit_amount"] = str(
        float(bank["credit_amount"]) + 75
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
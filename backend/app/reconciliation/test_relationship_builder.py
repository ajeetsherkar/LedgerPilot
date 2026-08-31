from backend.app.reconciliation.relationship_builder import (
    build_transaction_chains,
)


def test_build_complete_transaction_chain():
    orders = [
        {
            "order_id": "ORD001",
            "order_amount": "1000.00",
        }
    ]

    payments = [
        {
            "payment_id": "PAY001",
            "order_id": "ORD001",
            "amount": "1000.00",
        }
    ]

    settlements = [
        {
            "settlement_id": "SET001",
            "payment_id": "PAY001",
            "settlement_reference": "SET-441",
        }
    ]

    banks = [
        {
            "transaction_id": "BTX001",
            "reference": "SET-441",
            "credit_amount": "988.20",
        }
    ]

    chains = build_transaction_chains(
        orders,
        payments,
        settlements,
        banks,
    )

    assert len(chains) == 1

    chain = chains[0]

    assert chain.order_id == "ORD001"
    assert chain.payment_id == "PAY001"
    assert chain.settlement_id == "SET001"
    assert chain.bank_transaction_id == "BTX001"


def test_chain_can_be_missing_payment():
    orders = [
        {
            "order_id": "ORD001",
        }
    ]

    chains = build_transaction_chains(
        orders,
        [],
        [],
        [],
    )

    assert len(chains) == 1

    chain = chains[0]

    assert chain.order_id == "ORD001"
    assert chain.payment is None
    assert chain.settlement is None
    assert chain.bank is None


def test_chain_can_be_missing_settlement():
    orders = [
        {
            "order_id": "ORD001",
        }
    ]

    payments = [
        {
            "payment_id": "PAY001",
            "order_id": "ORD001",
        }
    ]

    chains = build_transaction_chains(
        orders,
        payments,
        [],
        [],
    )

    chain = chains[0]

    assert chain.order_id == "ORD001"
    assert chain.payment_id == "PAY001"
    assert chain.settlement is None
    assert chain.bank is None


def test_chain_can_be_missing_bank():
    orders = [
        {
            "order_id": "ORD001",
        }
    ]

    payments = [
        {
            "payment_id": "PAY001",
            "order_id": "ORD001",
        }
    ]

    settlements = [
        {
            "settlement_id": "SET001",
            "payment_id": "PAY001",
            "settlement_reference": "SET-441",
        }
    ]

    chains = build_transaction_chains(
        orders,
        payments,
        settlements,
        [],
    )

    chain = chains[0]

    assert chain.order_id == "ORD001"
    assert chain.payment_id == "PAY001"
    assert chain.settlement_id == "SET001"
    assert chain.bank is None


def test_reference_normalization_allows_bank_link():
    orders = [
        {
            "order_id": "ORD001",
        }
    ]

    payments = [
        {
            "payment_id": "PAY001",
            "order_id": "ORD001",
        }
    ]

    settlements = [
        {
            "settlement_id": "SET001",
            "payment_id": "PAY001",
            "settlement_reference": "RZP SET-441",
        }
    ]

    banks = [
        {
            "transaction_id": "BTX001",
            "reference": "SET_441",
        }
    ]

    chains = build_transaction_chains(
        orders,
        payments,
        settlements,
        banks,
    )

    assert chains[0].bank_transaction_id == "BTX001"

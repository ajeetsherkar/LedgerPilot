from backend.app.reconciliation.relationship_builder import TransactionChain
from backend.app.reconciliation.exception_classifier import (
    classify_chain_exception,
)

from backend.app.reconciliation.exception_types import (
    ExceptionType,
)

def test_missing_payment_is_classified():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
        },
        payment=None,
        settlement=None,
        bank=None,
    )

    assert (
        classify_chain_exception(chain)
        == ExceptionType.MISSING_PAYMENT
    )


def test_missing_settlement_is_classified():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
        },
        payment={
            "payment_id": "PAY001",
            "amount": 1000,
        },
        settlement=None,
        bank=None,
    )

    assert (
        classify_chain_exception(chain)
        == ExceptionType.MISSING_SETTLEMENT
    )


def test_missing_bank_is_classified():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
        },
        payment={
            "payment_id": "PAY001",
            "amount": 1000,
        },
        settlement={
            "settlement_id": "SET001",
            "gross_amount": 1000,
            "net_amount": 988.20,
        },
        bank=None,
    )

    assert (
        classify_chain_exception(chain)
        == ExceptionType.MISSING_BANK_RECORD
    )


def test_bank_mismatch_is_classified():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
        },
        payment={
            "payment_id": "PAY001",
            "amount": 1000,
        },
        settlement={
            "settlement_id": "SET001",
            "gross_amount": 1000,
            "net_amount": 988.20,
            "settlement_reference": "SET001",
        },
        bank={
            "transaction_id": "BANK001",
            "credit_amount": 900,
            "reference": "SET001",
        },
    )

    assert (
        classify_chain_exception(chain)
        == ExceptionType.AMOUNT_MISMATCH
    )
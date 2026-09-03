from backend.app.reconciliation.exception_classifier import (
    classify_chain_exception,
)

from backend.app.reconciliation.exception_types import (
    ExceptionType,
)

from backend.app.reconciliation.relationship_builder import (
    TransactionChain,
)


def test_partial_settlement_is_classified():

    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
            "order_date": "2026-08-24",
        },
        payment={
            "payment_id": "PAY001",
            "amount": 1000,
            "payment_date": "2026-08-24",
        },
        settlement={
            "settlement_id": "SET001",
            "payment_id": "PAY001",
            "gross_amount": 1000,
            "net_amount": 494.10,
            "settlement_date": "2026-08-26",
            "settlement_reference": "SET001",
        },
        bank={
            "transaction_id": "BANK001",
            "credit_amount": 494.10,
            "transaction_date": "2026-08-26",
            "reference": "SET001",
        },
        related_settlements=[
            {
                "settlement_id": "SET001",
                "payment_id": "PAY001",
                "gross_amount": 1000,
                "net_amount": 494.10,
                "settlement_date": "2026-08-26",
                "settlement_reference": "SET001",
            },
            {
                "settlement_id": "SET001_PART2",
                "payment_id": "PAY001",
                "gross_amount": 1000,
                "net_amount": 494.10,
                "settlement_date": "2026-08-26",
                "settlement_reference": "SET001",
            },
        ],
    )

    assert (
        classify_chain_exception(chain)
        == ExceptionType.PARTIAL_SETTLEMENT
    )


def test_combined_settlement_is_classified():

    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
            "order_date": "2026-08-24",
        },
        payment={
            "payment_id": "PAY001",
            "amount": 1000,
            "payment_date": "2026-08-24",
        },
        settlement={
            "settlement_id": "SET001",
            "payment_id": "PAY001",
            "gross_amount": 1000,
            "net_amount": 988.20,
            "settlement_date": "2026-08-26",
            "settlement_reference": "SET001",
        },
        bank={
            "transaction_id": "BANK001_COMBINED",
            "credit_amount": 1976.40,
            "transaction_date": "2026-08-26",
            "reference": "COMBINED-SET001-SET002",
            "narration": (
                "Combined settlement for "
                "PAY001 and PAY002"
            ),
        },
    )

    assert (
        classify_chain_exception(chain)
        == ExceptionType.COMBINED_SETTLEMENT
    )


def test_date_mismatch_is_classified():

    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
            "order_date": "2026-08-24",
        },
        payment={
            "payment_id": "PAY001",
            "amount": 1000,
            "payment_date": "2026-08-24",
        },
        settlement={
            "settlement_id": "SET001",
            "payment_id": "PAY001",
            "gross_amount": 1000,
            "net_amount": 988.20,
            "settlement_date": "2026-08-29",
            "settlement_reference": "SET001",
        },
        bank={
            "transaction_id": "BANK001",
            "credit_amount": 988.20,
            "transaction_date": "2026-08-29",
            "reference": "SET001",
        },
    )

    assert (
        classify_chain_exception(chain)
        == ExceptionType.DATE_MISMATCH
    )
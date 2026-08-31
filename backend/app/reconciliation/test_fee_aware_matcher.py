from decimal import Decimal

from backend.app.reconciliation.fee_aware_matcher import (
    FEE_AMOUNT_TOLERANCE,
    expected_net_amount,
    fee_aware_match,
    fee_aware_match_status,
)
from backend.app.reconciliation.relationship_builder import (
    TransactionChain,
)


def make_chain(
    *,
    gross="1000.00",
    platform_fee="10.00",
    gst_on_fee="1.80",
    bank_amount="988.20",
    order_amount="1000.00",
    payment_amount="1000.00",
    settlement_reference="SET-441",
    bank_reference="SET_441",
    order_date="2026-08-24",
    payment_date="2026-08-24",
    settlement_date="2026-08-26",
    bank_date="2026-08-26",
):
    order = {
        "order_id": "ORD001",
        "order_amount": order_amount,
        "order_date": order_date,
    }

    payment = {
        "payment_id": "PAY001",
        "order_id": "ORD001",
        "amount": payment_amount,
        "payment_date": payment_date,
    }

    settlement = {
        "settlement_id": "SET001",
        "payment_id": "PAY001",
        "gross_amount": gross,
        "platform_fee": platform_fee,
        "gst_on_fee": gst_on_fee,
        "net_amount": "988.20",
        "settlement_reference": settlement_reference,
        "settlement_date": settlement_date,
    }

    bank = {
        "transaction_id": "BTX001",
        "reference": bank_reference,
        "credit_amount": bank_amount,
        "transaction_date": bank_date,
    }

    return TransactionChain(
        order=order,
        payment=payment,
        settlement=settlement,
        bank=bank,
    )


def test_expected_net_amount():

    settlement = {
        "gross_amount": "1000.00",
        "platform_fee": "10.00",
        "gst_on_fee": "1.80",
    }

    assert expected_net_amount(settlement) == Decimal(
        "988.20"
    )


def test_fee_aware_match_exact_expected_net():

    chain = make_chain(
        bank_amount="988.20",
    )

    assert fee_aware_match(chain) is True
    assert fee_aware_match_status(chain) == "MATCH"


def test_fee_aware_match_within_positive_tolerance():

    chain = make_chain(
        bank_amount="989.20",
    )

    assert fee_aware_match(chain) is True


def test_fee_aware_match_within_negative_tolerance():

    chain = make_chain(
        bank_amount="987.20",
    )

    assert fee_aware_match(chain) is True


def test_fee_aware_match_outside_tolerance():

    chain = make_chain(
        bank_amount="989.21",
    )

    assert fee_aware_match(chain) is False
    assert fee_aware_match_status(chain) == "UNRESOLVED"


def test_tolerance_is_one_rupee():

    assert FEE_AMOUNT_TOLERANCE == Decimal("1.00")


def test_fee_aware_match_rejects_wrong_order_payment_amount():

    chain = make_chain(
        payment_amount="999.00",
    )

    assert fee_aware_match(chain) is False


def test_fee_aware_match_rejects_wrong_reference():

    chain = make_chain(
        bank_reference="OTHER-REF",
    )

    assert fee_aware_match(chain) is False


def test_fee_aware_match_rejects_wrong_date_sequence():

    chain = make_chain(
        bank_date="2026-08-20",
    )

    assert fee_aware_match(chain) is False


def test_fee_aware_match_rejects_missing_payment():

    chain = make_chain()
    chain.payment = None

    assert fee_aware_match(chain) is False


def test_fee_aware_match_rejects_missing_settlement():

    chain = make_chain()
    chain.settlement = None

    assert fee_aware_match(chain) is False


def test_fee_aware_match_rejects_missing_bank():

    chain = make_chain()
    chain.bank = None

    assert fee_aware_match(chain) is False


def test_fee_aware_match_handles_normalized_reference():

    chain = make_chain(
        settlement_reference="RZP SET-441",
        bank_reference="SET_441",
    )

    assert fee_aware_match(chain) is True


def test_fee_aware_match_handles_decimal_amounts():

    chain = make_chain(
        gross="1234.50",
        platform_fee="12.35",
        gst_on_fee="2.22",
        bank_amount="1219.93",
    )

    assert fee_aware_match(chain) is True


def test_fee_aware_match_rejects_invalid_amount():

    chain = make_chain(
        bank_amount="not-an-amount",
    )

    assert fee_aware_match(chain) is False


def test_fee_aware_match_rejects_invalid_date():

    chain = make_chain(
        bank_date="invalid-date",
    )

    assert fee_aware_match(chain) is False


def test_fee_aware_match_rejects_invalid_fee_data():

    chain = make_chain(
        platform_fee="invalid-fee",
    )

    assert fee_aware_match(chain) is False
from backend.app.reconciliation.exact_matcher import (
    exact_match,
    exact_match_status,
)
from backend.app.reconciliation.relationship_builder import (
    TransactionChain,
)


def make_chain(
    *,
    order_id="ORD0001",
    payment_order_id="ORD0001",
    payment_id="PAY0001",
    settlement_payment_id="PAY0001",
    settlement_reference="SETTXN0001",
    bank_reference="SETTXN0001",
    order_amount="1000.00",
    payment_amount="1000.00",
    settlement_amount="988.20",
    bank_amount="988.20",
    order_date="2026-08-24",
    payment_date="2026-08-24",
    settlement_date="2026-08-26",
    bank_date="2026-08-26",
):
    order = {
        "order_id": order_id,
        "order_amount": order_amount,
        "order_date": order_date,
    }

    payment = {
        "payment_id": payment_id,
        "order_id": payment_order_id,
        "amount": payment_amount,
        "payment_date": payment_date,
    }

    settlement = {
        "settlement_id": "SET0001",
        "payment_id": settlement_payment_id,
        "settlement_reference": settlement_reference,
        "net_amount": settlement_amount,
        "settlement_date": settlement_date,
    }

    bank = {
        "transaction_id": "BTX0001",
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


def test_exact_match_complete_valid_chain():
    chain = make_chain()

    assert exact_match(chain) is True
    assert exact_match_status(chain) == "MATCH"


def test_missing_payment_is_unresolved():
    chain = make_chain(payment_order_id="ORD0001")
    chain.payment = None

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_missing_settlement_is_unresolved():
    chain = make_chain()
    chain.settlement = None

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_missing_bank_is_unresolved():
    chain = make_chain()
    chain.bank = None

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_order_payment_id_mismatch_is_unresolved():
    chain = make_chain(
        payment_order_id="ORD9999",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_payment_settlement_id_mismatch_is_unresolved():
    chain = make_chain(
        settlement_payment_id="PAY9999",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_settlement_bank_reference_must_match():
    chain = make_chain(
        bank_reference="DIFFERENT",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_reference_normalization_is_used():
    chain = make_chain(
        settlement_reference="RZP SET-441",
        bank_reference="SET_441",
    )

    assert exact_match(chain) is True
    assert exact_match_status(chain) == "MATCH"


def test_order_payment_amount_mismatch_is_unresolved():
    chain = make_chain(
        payment_amount="999.00",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_settlement_bank_amount_mismatch_is_unresolved():
    chain = make_chain(
        bank_amount="987.20",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_date_sequence_must_be_chronological():
    chain = make_chain(
        payment_date="2026-08-27",
        settlement_date="2026-08-26",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_settlement_before_payment_is_unresolved():
    chain = make_chain(
        payment_date="2026-08-26",
        settlement_date="2026-08-25",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_bank_before_settlement_is_unresolved():
    chain = make_chain(
        settlement_date="2026-08-26",
        bank_date="2026-08-25",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_invalid_date_is_unresolved():
    chain = make_chain(
        payment_date="not-a-date",
    )

    assert exact_match(chain) is False
    assert exact_match_status(chain) == "UNRESOLVED"


def test_currency_symbols_and_commas_are_normalized():
    chain = make_chain(
        order_amount="₹1,000.00",
        payment_amount="$1,000.00",
    )

    assert exact_match(chain) is True


def test_exact_amount_requires_no_difference():
    chain = make_chain(
        order_amount="1000.00",
        payment_amount="1000.01",
    )

    assert exact_match(chain) is False


def test_same_day_transactions_are_valid():
    chain = make_chain(
        order_date="2026-08-24",
        payment_date="2026-08-24",
        settlement_date="2026-08-24",
        bank_date="2026-08-24",
    )

    assert exact_match(chain) is True

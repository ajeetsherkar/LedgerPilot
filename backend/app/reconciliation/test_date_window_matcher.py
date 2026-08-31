from decimal import Decimal

from backend.app.reconciliation.date_window_matcher import (
    PAYMENT_TO_SETTLEMENT_MAX_DAYS,
    SETTLEMENT_TO_BANK_MAX_DAYS,
    date_window_match,
    date_window_match_status,
    valid_date_windows,
)
from backend.app.reconciliation.relationship_builder import (
    TransactionChain,
)


def make_chain(
    *,
    order_id="ORD001",
    payment_order_id="ORD001",
    payment_id="PAY001",
    settlement_payment_id="PAY001",
    settlement_reference="SET-441",
    bank_reference="SET_441",
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
        "settlement_id": "SET001",
        "payment_id": settlement_payment_id,
        "gross_amount": "1000.00",
        "platform_fee": "10.00",
        "gst_on_fee": "1.80",
        "net_amount": settlement_amount,
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


def test_default_windows_are_configurable_constants():
    assert PAYMENT_TO_SETTLEMENT_MAX_DAYS == 3
    assert SETTLEMENT_TO_BANK_MAX_DAYS == 2


def test_same_day_transactions_match():
    chain = make_chain(
        payment_date="2026-08-24",
        settlement_date="2026-08-24",
        bank_date="2026-08-24",
    )

    assert date_window_match(chain) is True


def test_payment_to_settlement_plus_one_day_matches():
    chain = make_chain(
        payment_date="2026-08-24",
        settlement_date="2026-08-25",
        bank_date="2026-08-25",
    )

    assert date_window_match(chain) is True


def test_payment_to_settlement_exact_three_days_matches():
    chain = make_chain(
        payment_date="2026-08-24",
        settlement_date="2026-08-27",
        bank_date="2026-08-27",
    )

    assert date_window_match(chain) is True


def test_payment_to_settlement_four_days_is_unresolved():
    chain = make_chain(
        payment_date="2026-08-24",
        settlement_date="2026-08-28",
        bank_date="2026-08-28",
    )

    assert date_window_match(chain) is False
    assert date_window_match_status(chain) == "UNRESOLVED"


def test_settlement_to_bank_plus_one_day_matches():
    chain = make_chain(
        payment_date="2026-08-24",
        settlement_date="2026-08-26",
        bank_date="2026-08-27",
    )

    assert date_window_match(chain) is True


def test_settlement_to_bank_exact_two_days_matches():
    chain = make_chain(
        payment_date="2026-08-24",
        settlement_date="2026-08-26",
        bank_date="2026-08-28",
    )

    assert date_window_match(chain) is True


def test_settlement_to_bank_three_days_is_unresolved():
    chain = make_chain(
        payment_date="2026-08-24",
        settlement_date="2026-08-26",
        bank_date="2026-08-29",
    )

    assert date_window_match(chain) is False
    assert date_window_match_status(chain) == "UNRESOLVED"


def test_settlement_before_payment_is_invalid():
    chain = make_chain(
        payment_date="2026-08-26",
        settlement_date="2026-08-25",
        bank_date="2026-08-26",
    )

    assert date_window_match(chain) is False


def test_bank_before_settlement_is_invalid():
    chain = make_chain(
        payment_date="2026-08-24",
        settlement_date="2026-08-26",
        bank_date="2026-08-25",
    )

    assert date_window_match(chain) is False


def test_payment_before_order_is_invalid():
    chain = make_chain(
        order_date="2026-08-25",
        payment_date="2026-08-24",
        settlement_date="2026-08-26",
        bank_date="2026-08-26",
    )

    assert date_window_match(chain) is False


def test_invalid_payment_date_is_unresolved():
    chain = make_chain(
        payment_date="not-a-date",
    )

    assert date_window_match(chain) is False
    assert date_window_match_status(chain) == "UNRESOLVED"


def test_invalid_settlement_date_is_unresolved():
    chain = make_chain(
        settlement_date="not-a-date",
    )

    assert date_window_match(chain) is False


def test_invalid_bank_date_is_unresolved():
    chain = make_chain(
        bank_date="not-a-date",
    )

    assert date_window_match(chain) is False


def test_missing_payment_is_unresolved():
    chain = make_chain()
    chain.payment = None

    assert date_window_match(chain) is False


def test_missing_settlement_is_unresolved():
    chain = make_chain()
    chain.settlement = None

    assert date_window_match(chain) is False


def test_missing_bank_is_unresolved():
    chain = make_chain()
    chain.bank = None

    assert date_window_match(chain) is False


def test_wrong_order_payment_reference_is_unresolved():
    chain = make_chain(
        payment_order_id="ORD999",
    )

    assert date_window_match(chain) is False


def test_wrong_payment_settlement_reference_is_unresolved():
    chain = make_chain(
        settlement_payment_id="PAY999",
    )

    assert date_window_match(chain) is False


def test_wrong_bank_reference_is_unresolved():
    chain = make_chain(
        bank_reference="OTHER-REF",
    )

    assert date_window_match(chain) is False


def test_wrong_order_payment_amount_is_unresolved():
    chain = make_chain(
        payment_amount="999.00",
    )

    assert date_window_match(chain) is False


def test_wrong_settlement_bank_amount_is_unresolved():
    chain = make_chain(
        bank_amount="987.20",
    )

    assert date_window_match(chain) is False


def test_reference_normalization_is_preserved():
    chain = make_chain(
        settlement_reference="RZP SET-441",
        bank_reference="SET_441",
    )

    assert date_window_match(chain) is True


def test_date_window_helper_accepts_boundary():
    assert valid_date_windows(
        {
            "order_date": "2026-08-24",
        },
        {
            "payment_date": "2026-08-24",
        },
        {
            "settlement_date": "2026-08-27",
        },
        {
            "transaction_date": "2026-08-29",
        },
    ) is True


def test_date_window_helper_rejects_payment_settlement_outside_window():
    assert valid_date_windows(
        {
            "order_date": "2026-08-24",
        },
        {
            "payment_date": "2026-08-24",
        },
        {
            "settlement_date": "2026-08-28",
        },
        {
            "transaction_date": "2026-08-29",
        },
    ) is False


def test_date_window_helper_rejects_settlement_bank_outside_window():
    assert valid_date_windows(
        {
            "order_date": "2026-08-24",
        },
        {
            "payment_date": "2026-08-24",
        },
        {
            "settlement_date": "2026-08-26",
        },
        {
            "transaction_date": "2026-08-29",
        },
    ) is False

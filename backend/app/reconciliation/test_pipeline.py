from backend.app.reconciliation.pipeline import reconcile_all

def make_order(
    order_id="ORD001",
    amount=1000.0,
):
    return {
        "order_id": order_id,
        "order_amount": amount,
        "currency": "INR",
        "order_date": "2026-01-01",
    }


def make_payment(
    payment_id="PAY001",
    order_id="ORD001",
    amount=1000.0,
):
    return {
        "payment_id": payment_id,
        "order_id": order_id,
        "amount": amount,
        "currency": "INR",
        "payment_date": "2026-01-01",
    }


def make_settlement(
    settlement_id="SET001",
    payment_id="PAY001",
    amount=1000.0,
    reference="REF001",
):
    return {
        "settlement_id": settlement_id,
        "payment_id": payment_id,
        "net_amount": amount,
        "currency": "INR",
        "settlement_date": "2026-01-01",
        "settlement_reference": reference,
        "platform_fee": 0.0,
        "gst_on_fee": 0.0,
    }


def make_bank(
    transaction_id="BANK001",
    amount=1000.0,
    reference="REF001",
):
    return {
        "transaction_id": transaction_id,
        "credit_amount": amount,
        "currency": "INR",
        "transaction_date": "2026-01-01",
        "reference": reference,
    }

def test_reconcile_all_returns_one_decision_per_order():
    orders = [
        make_order("ORD001"),
        make_order("ORD002"),
    ]

    payments = [
        make_payment(
            "PAY001",
            "ORD001",
        ),
        make_payment(
            "PAY002",
            "ORD002",
        ),
    ]

    settlements = [
        make_settlement(
            "SET001",
            "PAY001",
            reference="REF001",
        ),
        make_settlement(
            "SET002",
            "PAY002",
            reference="REF002",
        ),
    ]

    banks = [
        make_bank(
            "BANK001",
            reference="REF001",
        ),
        make_bank(
            "BANK002",
            reference="REF002",
        ),
    ]

    decisions = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
    )

    assert len(decisions) == 2


def test_complete_exact_chain_is_matched():
    orders = [
        make_order(),
    ]

    payments = [
        make_payment(),
    ]

    settlements = [
        make_settlement(),
    ]

    banks = [
        make_bank(),
    ]

    decisions = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
    )

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "MATCH"
    assert decision.method == "EXACT"
    assert decision.confidence == 1.0


def test_missing_payment_becomes_unresolved():
    orders = [
        make_order(),
    ]

    payments = []

    settlements = []

    banks = []

    decisions = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
    )

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "UNRESOLVED"
    assert decision.method == "NONE"


def test_missing_bank_does_not_crash_pipeline():
    orders = [
        make_order(),
    ]

    payments = [
        make_payment(),
    ]

    settlements = [
        make_settlement(),
    ]

    banks = []

    decisions = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
    )

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status in {
        "UNRESOLVED",
        "REVIEW",
    }
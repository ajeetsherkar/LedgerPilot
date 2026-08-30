from datetime import date

from scripts.generate_data import generate_dataset


def test_generate_50_clean_chains():
    orders, payments, settlements, banks = generate_dataset(50)

    assert len(orders) == 50
    assert len(payments) == 50
    assert len(settlements) == 50
    assert len(banks) == 50

    order_ids = {row["order_id"] for row in orders}
    payment_ids = {row["payment_id"] for row in payments}
    settlement_ids = {
        row["settlement_id"]
        for row in settlements
    }
    bank_ids = {
        row["transaction_id"]
        for row in banks
    }

    chain_ids = {
        row["chain_id"]
        for row in orders
    }

    assert len(order_ids) == 50
    assert len(payment_ids) == 50
    assert len(settlement_ids) == 50
    assert len(bank_ids) == 50
    assert len(chain_ids) == 50

    orders_by_id = {
        row["order_id"]: row
        for row in orders
    }

    payments_by_id = {
        row["payment_id"]: row
        for row in payments
    }

    settlements_by_ref = {
        row["settlement_reference"]: row
        for row in settlements
    }

    for payment in payments:
        order = orders_by_id[payment["order_id"]]

        assert payment["chain_id"] == order["chain_id"]
        assert float(payment["amount"]) == float(
            order["order_amount"]
        )
        assert payment["currency"] == "INR"

    for settlement in settlements:
        payment = payments_by_id[
            settlement["payment_id"]
        ]

        assert settlement["chain_id"] == payment["chain_id"]

        gross = float(settlement["gross_amount"])
        fee = float(settlement["platform_fee"])
        gst = float(settlement["gst_on_fee"])
        net = float(settlement["net_amount"])

        expected_net = gross - fee - gst

        assert abs(net - expected_net) < 0.01

    for bank in banks:
        settlement = settlements_by_ref[
            bank["reference"]
        ]

        assert bank["chain_id"] == settlement["chain_id"]

        assert abs(
            float(bank["credit_amount"])
            - float(settlement["net_amount"])
        ) < 0.01

        assert bank["currency"] == "INR"


def test_generate_100_clean_chains():
    orders, payments, settlements, banks = generate_dataset(100)

    assert len(orders) == 100
    assert len(payments) == 100
    assert len(settlements) == 100
    assert len(banks) == 100
    
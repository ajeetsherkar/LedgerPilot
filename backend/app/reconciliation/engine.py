from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

from backend.app.reconciliation.models import ReconciliationResult


DATA_DIR = Path("data")


def load_datasets():
    """
    Load the clean LedgerPilot datasets.
    """

    orders = pd.read_csv(DATA_DIR / "orders.csv")
    payments = pd.read_csv(DATA_DIR / "payments.csv")
    settlements = pd.read_csv(DATA_DIR / "settlements.csv")
    bank_transactions = pd.read_csv(DATA_DIR / "bank.csv")

    return (
        orders.to_dict("records"),
        payments.to_dict("records"),
        settlements.to_dict("records"),
        bank_transactions.to_dict("records"),
    )


def _to_decimal(value):
    return Decimal(str(value))


def _expected_settlement_amount(settlement):
    """
    Calculate the expected settlement net amount
    from gross amount, platform fee and GST.
    """

    gross = _to_decimal(settlement["gross_amount"])

    platform_fee = (
        gross * Decimal("0.01")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    gst_on_fee = (
        platform_fee * Decimal("0.18")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    return (
        gross
        - platform_fee
        - gst_on_fee
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def reconcile_order(
    order,
    payment,
    settlement,
    bank,
):
    """
    Reconcile one complete order -> payment ->
    settlement -> bank chain.
    """

    expected_amount = _to_decimal(
        order["order_amount"]
    )

    paid_amount = _to_decimal(
        payment["amount"]
    )

    settled_amount = _to_decimal(
        settlement["net_amount"]
    )

    expected_settlement = _expected_settlement_amount(
        settlement
    )

    bank_amount = (
        _to_decimal(bank["credit_amount"])
        if bank is not None
        else None
    )

    payment_status = "MATCHED"
    settlement_status = "MATCHED"
    bank_status = "MATCHED"

    difference = Decimal("0.00")
    exception_type = None

    # ---------------------------------------------------------
    # 1. ORDER -> PAYMENT
    # ---------------------------------------------------------

    payment_difference = (
        paid_amount - expected_amount
    )

    if payment_difference != Decimal("0.00"):
        payment_status = "MISMATCH"
        difference = abs(payment_difference)
        exception_type = "PAYMENT_MISMATCH"

    # ---------------------------------------------------------
    # 2. EXPECTED SETTLEMENT -> ACTUAL SETTLEMENT
    # ---------------------------------------------------------

    settlement_difference = (
        settled_amount - expected_settlement
    )

    if settlement_difference != Decimal("0.00"):
        settlement_status = "MISMATCH"

        if exception_type is None:
            difference = abs(settlement_difference)
            exception_type = "SETTLEMENT_MISMATCH"

    # ---------------------------------------------------------
    # 3. SETTLEMENT -> BANK
    # ---------------------------------------------------------

    if bank is None:
        bank_status = "MISSING"

        if exception_type is None:
            exception_type = "MISSING_BANK"

    else:
        bank_difference = (
            bank_amount - settled_amount
        )

        if bank_difference != Decimal("0.00"):
            bank_status = "MISMATCH"

            if exception_type is None:
                difference = abs(bank_difference)
                exception_type = "BANK_MISMATCH"

    # ---------------------------------------------------------
    # FINAL STATUS
    # ---------------------------------------------------------

    reconciliation_status = (
        "MATCHED"
        if exception_type is None
        else "EXCEPTION"
    )

    return ReconciliationResult(
        order_id=str(order["order_id"]),
        payment_id=str(payment["payment_id"]),
        settlement_id=str(settlement["settlement_id"]),
        bank_transaction_id=(
            str(bank["transaction_id"])
            if bank is not None
            else None
        ),
        payment_status=payment_status,
        settlement_status=settlement_status,
        bank_status=bank_status,
        expected_amount=float(expected_amount),
        paid_amount=float(paid_amount),
        settled_amount=float(settled_amount),
        bank_amount=(
            float(bank_amount)
            if bank_amount is not None
            else None
        ),
        difference=float(difference),
        reconciliation_status=reconciliation_status,
        exception_type=exception_type,
    )


def reconcile_all():
    """
    Reconcile every clean order/payment/
    settlement/bank chain.
    """

    (
        orders,
        payments,
        settlements,
        banks,
    ) = load_datasets()

    payments_by_order = {
        payment["order_id"]: payment
        for payment in payments
    }

    settlements_by_payment = {
        settlement["payment_id"]: settlement
        for settlement in settlements
    }

    banks_by_reference = {
        bank["reference"]: bank
        for bank in banks
    }

    results = []

    for order in orders:

        payment = payments_by_order.get(
            order["order_id"]
        )

        if payment is None:
            continue

        settlement = settlements_by_payment.get(
            payment["payment_id"]
        )

        if settlement is None:
            continue

        bank = banks_by_reference.get(
            settlement["settlement_reference"]
        )

        result = reconcile_order(
            order,
            payment,
            settlement,
            bank,
        )

        results.append(result)

    return results
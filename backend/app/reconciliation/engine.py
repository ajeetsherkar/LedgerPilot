from pathlib import Path
import csv

from .models import ReconciliationResult
from .exceptions import classify_exception


DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def load_csv(filename: str) -> list[dict]:
    file_path = DATA_DIR / filename

    with open(file_path, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_datasets():
    orders = load_csv("orders.csv")
    payments = load_csv("payments.csv")
    settlements = load_csv("settlements.csv")
    bank_transactions = load_csv("bank.csv")

    return orders, payments, settlements, bank_transactions


def reconcile_order(
    order: dict,
    payment: dict | None,
    settlement: dict | None,
    bank_transaction: dict | None,
) -> ReconciliationResult:

    order_amount = float(order["order_amount"])

    # ---- Stage 1: Payment ----
    if payment is None:
        payment_status = "MISSING"
        payment_amount = None
        payment_difference = None
    else:
        payment_amount = float(payment["amount"])
        payment_difference = payment_amount - order_amount

        payment_status = (
            "MATCHED"
            if abs(payment_difference) < 0.01
            else "MISMATCH"
        )

    # ---- Stage 2: Settlement ----
    if settlement is None:
        settlement_status = "MISSING"
        net_amount = None
        settlement_difference = None
    else:
        gross_amount = float(settlement["gross_amount"])
        platform_fee = float(settlement["platform_fee"])
        gst_on_fee = float(settlement["gst_on_fee"])
        net_amount = float(settlement["net_amount"])

        expected_net_amount = (
            gross_amount
            - platform_fee
            - gst_on_fee
        )

        settlement_difference = (
            net_amount - expected_net_amount
        )

        settlement_status = (
            "MATCHED"
            if abs(settlement_difference) < 0.01
            else "MISMATCH"
        )

    # ---- Stage 3: Bank ----
    if bank_transaction is None or net_amount is None:
        bank_status = "MISSING"
        bank_amount = None
        bank_difference = None
    else:
        bank_amount = float(bank_transaction["credit_amount"])

        bank_difference = (
            bank_amount - net_amount
        )

        bank_status = (
            "MATCHED"
            if abs(bank_difference) < 0.01
            else "MISMATCH"
        )

    # ---- Exception priority: PAYMENT > SETTLEMENT > BANK ----
    if payment_status == "MISMATCH":
        exception_type = "PAYMENT_MISMATCH"
        difference = abs(payment_difference)

    elif payment_status == "MISSING":
        exception_type = "PAYMENT_MISSING"
        difference = 0.0

    elif settlement_status == "MISMATCH":
        exception_type = "SETTLEMENT_MISMATCH"
        difference = abs(settlement_difference)

    elif settlement_status == "MISSING":
        exception_type = "SETTLEMENT_MISSING"
        difference = 0.0

    elif bank_status == "MISMATCH":
        exception_type = "BANK_MISMATCH"
        difference = abs(bank_difference)

    elif bank_status == "MISSING":
        exception_type = "BANK_MISSING"
        difference = 0.0

    else:
        exception_type = None
        difference = 0.0

    if exception_type:
        reconciliation_status = "EXCEPTION"
    else:
        reconciliation_status = "MATCHED"

    result = ReconciliationResult(
        order_id=order["order_id"],
        payment_status=payment_status,
        settlement_status=settlement_status,
        bank_status=bank_status,
        expected_amount=order_amount,
        paid_amount=payment_amount,
        settled_amount=net_amount,
        bank_amount=bank_amount,
        difference=difference,
        reconciliation_status=reconciliation_status,
        exception_type=exception_type,
    )

    return result

def reconcile_all() -> list[ReconciliationResult]:
    orders, payments, settlements, bank_transactions = load_datasets()

    payments_by_order = {
        payment["order_id"]: payment
        for payment in payments
    }

    settlements_by_payment_id = {
        settlement["payment_id"]: settlement
        for settlement in settlements
    }

    bank_by_reference = {
        transaction["reference"]: transaction
        for transaction in bank_transactions
    }

    results = []

    for order in orders:
        order_id = order["order_id"]

        payment = payments_by_order.get(order_id)

        settlement = None
        if payment:
            payment_id = payment["payment_id"]
            settlement = settlements_by_payment_id.get(payment_id)

        bank_transaction = None
        if settlement:
            settlement_reference = settlement["settlement_reference"]
            bank_transaction = bank_by_reference.get(
                settlement_reference
            )

        result = reconcile_order(
            order,
            payment,
            settlement,
            bank_transaction,
        )

        results.append(result)

    return results
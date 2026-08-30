from pathlib import Path
import csv

from .models import ReconciliationResult


DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def load_csv(filename: str) -> list[dict]:
    file_path = DATA_DIR / filename

    with open(file_path, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_datasets():
    orders = load_csv("orders.csv")
    payments = load_csv("payments.csv")
    settlements = load_csv("settlements.csv")
    bank_transactions = load_csv("bank_transactions.csv")

    return orders, payments, settlements, bank_transactions


def reconcile_order(
    order: dict,
    payment: dict | None,
    settlement: dict | None,
    bank_transaction: dict | None,
) -> ReconciliationResult:

    expected_amount = float(order["gross_amount"])

    paid_amount = (
        float(payment["paid_amount"])
        if payment
        else None
    )

    settled_amount = (
        float(settlement["settled_amount"])
        if settlement
        else None
    )

    bank_amount = (
        float(bank_transaction["amount"])
        if bank_transaction
        else None
    )

    payment_status = (
        "MATCHED"
        if payment and paid_amount == expected_amount
        else "MISMATCH"
        if payment
        else "MISSING"
    )

    settlement_status = (
        "MATCHED"
        if settlement and settled_amount == expected_amount
        else "MISMATCH"
        if settlement
        else "MISSING"
    )

    bank_status = (
        "MATCHED"
        if bank_transaction and bank_amount == expected_amount
        else "MISMATCH"
        if bank_transaction
        else "MISSING"
    )

    amounts = [
        amount
        for amount in [paid_amount, settled_amount, bank_amount]
        if amount is not None
    ]

    difference = (
        max([expected_amount] + amounts)
        - min([expected_amount] + amounts)
    )

    if (
        payment_status == "MATCHED"
        and settlement_status == "MATCHED"
        and bank_status == "MATCHED"
    ):
        reconciliation_status = "MATCHED"
    else:
        reconciliation_status = "EXCEPTION"

    return ReconciliationResult(
        order_id=order["order_id"],
        payment_status=payment_status,
        settlement_status=settlement_status,
        bank_status=bank_status,
        expected_amount=expected_amount,
        paid_amount=paid_amount,
        settled_amount=settled_amount,
        bank_amount=bank_amount,
        difference=difference,
        reconciliation_status=reconciliation_status,
    )

def reconcile_all() -> list[ReconciliationResult]:
    orders, payments, settlements, bank_transactions = load_datasets()

    payments_by_order = {
        payment["order_id"]: payment
        for payment in payments
    }

    settlements_by_order = {
        settlement["order_id"]: settlement
        for settlement in settlements
    }

    bank_by_transaction_ref = {
        transaction["transaction_ref"]: transaction
        for transaction in bank_transactions
    }

    results = []

    for order in orders:
        order_id = order["order_id"]

        payment = payments_by_order.get(order_id)
        settlement = settlements_by_order.get(order_id)

        bank_transaction = None

        if payment:
            transaction_ref = payment["transaction_ref"]
            bank_transaction = bank_by_transaction_ref.get(
                transaction_ref
            )

        result = reconcile_order(
            order,
            payment,
            settlement,
            bank_transaction,
        )

        results.append(result)

    return results
import csv
import random
from pathlib import Path
from datetime import date, timedelta


DATA_DIR = Path("data")

SEED = 42
random.seed(SEED)

NUM_RECORDS = 10

START_DATE = date(2026, 8, 1)

CURRENCIES = ["INR"]

PAYMENT_METHODS = [
    "UPI",
    "CARD",
    "NETBANKING",
]
def random_date():
    return START_DATE + timedelta(days=random.randint(0, 29))


def generate_orders():
    rows = []

    for i in range(1, NUM_RECORDS + 1):
        rows.append({
            "order_id": f"ORD{i:04d}",
            "order_date": random_date(),
            "customer_id": f"CUST{random.randint(1, 5):03d}",
            "currency": "INR",
            "gross_amount": random.randint(500, 10000),
        })

    return rows


def write_csv(filename, rows, fieldnames):
    path = DATA_DIR / filename

    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Wrote {len(rows)} rows to {path}")


def generate_payments(orders):
    rows = []

    for order in orders:
        rows.append({
            "payment_id": f"PAY{order['order_id'][3:]}",
            "order_id": order["order_id"],
            "payment_date": order["order_date"],
            "payment_method": random.choice(PAYMENT_METHODS),
            "currency": order["currency"],
            "paid_amount": order["gross_amount"],
            "transaction_ref": f"TXN{order['order_id'][3:]}",
        })

    return rows


def generate_settlements(orders):
    rows = []

    for order in orders:
        rows.append({
            "settlement_id": f"SET{order['order_id'][3:]}",
            "order_id": order["order_id"],
            "settlement_date": order["order_date"] + timedelta(days=2),
            "currency": order["currency"],
            "settled_amount": order["gross_amount"],
            "settlement_ref": f"SETTXN{order['order_id'][3:]}",
        })

    return rows


def generate_bank_transactions(orders):
    rows = []

    for order in orders:
        rows.append({
            "bank_txn_id": f"BTX{order['order_id'][3:]}",
            "transaction_date": order["order_date"] + timedelta(days=2),
            "currency": order["currency"],
            "amount": order["gross_amount"],
            "transaction_ref": f"TXN{order['order_id'][3:]}",
            "description": f"Settlement for {order['order_id']}",
        })

    return rows


def main():
    orders = generate_orders()

    payments = []

    for order in orders:
        payments.append({
            "payment_id": f"PAY{order['order_id'][3:]}",
            "order_id": order["order_id"],
            "payment_date": order["order_date"],
            "payment_method": random.choice(PAYMENT_METHODS),
            "currency": order["currency"],
            "paid_amount": order["gross_amount"],
            "transaction_ref": f"TXN{order['order_id'][3:]}"
        })

    settlements = []

    for payment in payments:
        settlement_date = payment["payment_date"] + timedelta(days=2)

        settlements.append({
            "settlement_id": f"SET{payment['payment_id'][3:]}",
            "order_id": payment["order_id"],
            "settlement_date": settlement_date,
            "currency": payment["currency"],
            "settled_amount": payment["paid_amount"],
            "settlement_ref": f"SETTXN{payment['payment_id'][3:]}"
        })

    bank_transactions = []

    for settlement in settlements:
        bank_transactions.append({
            "bank_txn_id": f"BTX{settlement['settlement_id'][3:]}",
            "transaction_date": settlement["settlement_date"],
            "currency": settlement["currency"],
            "amount": settlement["settled_amount"],
            "transaction_ref": f"TXN{settlement['order_id'][3:]}",
            "description": f"Settlement for {settlement['order_id']}"
        })

    write_csv(
        "orders.csv",
        orders,
        [
            "order_id",
            "order_date",
            "customer_id",
            "currency",
            "gross_amount"
        ]
    )

    write_csv(
        "payments.csv",
        payments,
        [
            "payment_id",
            "order_id",
            "payment_date",
            "payment_method",
            "currency",
            "paid_amount",
            "transaction_ref"
        ]
    )

    write_csv(
        "settlements.csv",
        settlements,
        [
            "settlement_id",
            "order_id",
            "settlement_date",
            "currency",
            "settled_amount",
            "settlement_ref"
        ]
    )

    write_csv(
        "bank_transactions.csv",
        bank_transactions,
        [
            "bank_txn_id",
            "transaction_date",
            "currency",
            "amount",
            "transaction_ref",
            "description"
        ]
    )


if __name__ == "__main__":
    main()
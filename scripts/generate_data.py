import csv
import random
from datetime import date, timedelta
from pathlib import Path


DATA_DIR = Path("data")

SEED = 42
random.seed(SEED)

NUM_RECORDS = 10
START_DATE = date(2026, 8, 1)

PAYMENT_METHODS = [
    "UPI",
    "CARD",
    "NETBANKING",
]


def random_date():
    return START_DATE + timedelta(days=random.randint(0, 29))


def generate_orders():
    rows = []

    customer_names = {
        "CUST001": "Aarav Sharma",
        "CUST002": "Ishita Patel",
        "CUST003": "Rohan Verma",
        "CUST004": "Ananya Joshi",
        "CUST005": "Vikram Singh",
    }

    for i in range(1, NUM_RECORDS + 1):
        customer_id = f"CUST{random.randint(1, 5):03d}"

        rows.append(
            {
                "order_id": f"ORD{i:04d}",
                "merchant_id": "MERCH001",
                "customer_id": customer_id,
                "customer_name": customer_names[customer_id],
                "order_amount": random.randint(500, 10000),
                "currency": "INR",
                "order_date": random_date(),
                "status": "COMPLETED",
            }
        )

    return rows


def generate_payments(orders):
    rows = []

    for order in orders:
        payment_method = random.choice(PAYMENT_METHODS)

        if payment_method == "UPI":
            upi_ref = f"UPI/RZP/{random.randint(100000000000, 999999999999)}"
        else:
            upi_ref = ""

        rows.append(
            {
                "payment_id": f"PAY{order['order_id'][3:]}",
                "order_id": order["order_id"],
                "payment_method": payment_method,
                "upi_ref": upi_ref,
                "amount": order["order_amount"],
                "currency": order["currency"],
                "payment_date": order["order_date"],
                "status": "SUCCESS",
            }
        )

    return rows


def generate_settlements(payments):
    rows = []

    for payment in payments:
        gross_amount = payment["amount"]

        # Synthetic platform fee: 1% of gross amount.
        platform_fee = round(gross_amount * 0.01, 2)

        # Synthetic GST on platform fee: 18%.
        gst_on_fee = round(platform_fee * 0.18, 2)

        # Critical reconciliation invariant.
        net_amount = round(
            gross_amount - platform_fee - gst_on_fee,
            2,
        )

        rows.append(
            {
                "settlement_id": f"SET{payment['payment_id'][3:]}",
                "payment_id": payment["payment_id"],
                "gross_amount": gross_amount,
                "platform_fee": platform_fee,
                "gst_on_fee": gst_on_fee,
                "net_amount": net_amount,
                "settlement_date": payment["payment_date"] + timedelta(days=2),
                "settlement_reference": (
                    f"SETTXN{payment['payment_id'][3:]}"
                ),
            }
        )

    return rows


def generate_bank_transactions(settlements):
    rows = []

    for settlement in settlements:
        rows.append(
            {
                "transaction_id": (
                    f"BTX{settlement['settlement_id'][3:]}"
                ),
                "transaction_date": settlement["settlement_date"],
                "credit_amount": settlement["net_amount"],
                "currency": "INR",
                "narration": (
                    f"Settlement for {settlement['payment_id']}"
                ),
                "reference": settlement["settlement_reference"],
            }
        )

    return rows


def write_csv(filename, rows, fieldnames):
    path = DATA_DIR / filename

    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Wrote {len(rows)} rows to {path}")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    orders = generate_orders()
    payments = generate_payments(orders)
    settlements = generate_settlements(payments)
    bank_transactions = generate_bank_transactions(settlements)

    write_csv(
        "orders.csv",
        orders,
        [
            "order_id",
            "merchant_id",
            "customer_id",
            "customer_name",
            "order_amount",
            "currency",
            "order_date",
            "status",
        ],
    )

    write_csv(
        "payments.csv",
        payments,
        [
            "payment_id",
            "order_id",
            "payment_method",
            "upi_ref",
            "amount",
            "currency",
            "payment_date",
            "status",
        ],
    )

    write_csv(
        "settlements.csv",
        settlements,
        [
            "settlement_id",
            "payment_id",
            "gross_amount",
            "platform_fee",
            "gst_on_fee",
            "net_amount",
            "settlement_date",
            "settlement_reference",
        ],
    )

    write_csv(
        "bank.csv",
        bank_transactions,
        [
            "transaction_id",
            "transaction_date",
            "credit_amount",
            "currency",
            "narration",
            "reference",
        ],
    )


if __name__ == "__main__":
    main()

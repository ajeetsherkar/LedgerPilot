import csv
import random

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


DATA_DIR = Path("data")

SEED = 42
START_DATE = date(2026, 8, 1)

PAYMENT_METHODS = [
    "UPI",
    "CARD",
    "NETBANKING",
]

CUSTOMER_NAMES = {
    "CUST001": "Aarav Sharma",
    "CUST002": "Ishita Patel",
    "CUST003": "Rohan Verma",
    "CUST004": "Ananya Joshi",
    "CUST005": "Vikram Singh",
}


def random_date(rng):
    return START_DATE + timedelta(
        days=rng.randint(0, 29)
    )


def generate_orders(n, rng):
    rows = []

    for i in range(1, n + 1):
        chain_id = f"CHAIN{i:06d}"
        order_id = f"ORD{i:04d}"

        customer_id = f"CUST{rng.randint(1, 5):03d}"

        rows.append(
            {
                "chain_id": chain_id,
                "order_id": order_id,
                "merchant_id": "MERCH001",
                "customer_id": customer_id,
                "customer_name": CUSTOMER_NAMES[customer_id],
                "order_amount": rng.randint(500, 10000),
                "currency": "INR",
                "order_date": random_date(rng),
                "status": "COMPLETED",
            }
        )

    return rows


def generate_payments(orders, rng):
    rows = []

    for order in orders:
        payment_method = rng.choice(PAYMENT_METHODS)

        if payment_method == "UPI":
            upi_ref = (
                f"UPI/RZP/"
                f"{rng.randint(100000000000, 999999999999)}"
            )
        else:
            upi_ref = ""

        rows.append(
            {
                "chain_id": order["chain_id"],
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
        gross_amount = Decimal(str(payment["amount"]))

        platform_fee = (
            gross_amount * Decimal("0.01")
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

        net_amount = (
            gross_amount
            - platform_fee
            - gst_on_fee
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        rows.append(
            {
                "chain_id": payment["chain_id"],
                "settlement_id": (
                    f"SET{payment['payment_id'][3:]}"
                ),
                "payment_id": payment["payment_id"],
                "gross_amount": gross_amount,
                "platform_fee": platform_fee,
                "gst_on_fee": gst_on_fee,
                "net_amount": net_amount,
                "settlement_date": (
                    payment["payment_date"]
                    + timedelta(days=2)
                ),
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
                "chain_id": settlement["chain_id"],
                "transaction_id": (
                    f"BTX{settlement['settlement_id'][3:]}"
                ),
                "transaction_date": (
                    settlement["settlement_date"]
                ),
                "credit_amount": settlement["net_amount"],
                "currency": "INR",
                "narration": (
                    f"Settlement for "
                    f"{settlement['payment_id']}"
                ),
                "reference": (
                    settlement["settlement_reference"]
                ),
            }
        )

    return rows


def generate_dataset(n):
    if not isinstance(n, int):
        raise TypeError("n must be an integer")

    if n <= 0:
        raise ValueError("n must be greater than 0")

    rng = random.Random(SEED)

    orders = generate_orders(n, rng)
    payments = generate_payments(orders, rng)
    settlements = generate_settlements(payments)
    bank_transactions = generate_bank_transactions(
        settlements
    )

    return (
        orders,
        payments,
        settlements,
        bank_transactions,
    )


def write_csv(filename, rows, fieldnames):
    path = DATA_DIR / filename

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(rows)

    print(
        f"✅ Wrote {len(rows)} rows to {path}"
    )


def main():
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    n = 10

    (
        orders,
        payments,
        settlements,
        bank_transactions,
    ) = generate_dataset(n)

    write_csv(
        "orders.csv",
        orders,
        [
            "chain_id",
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
            "chain_id",
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
            "chain_id",
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
            "chain_id",
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
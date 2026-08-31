import csv
import random
from pathlib import Path

from scripts.generate_data import generate_dataset
from scripts.exceptions import (
    apply_exceptions,
    DEFAULT_EXCEPTION_RATES,
)


DATA_DIR = Path("data")
GROUND_TRUTH_FILE = DATA_DIR / "ground_truth.csv"
EXCEPTIONS_FILE = DATA_DIR / "exceptions.csv"

SEED = 42

GROUND_TRUTH_FIELDS = [
    "chain_id",
    "order_id",
    "payment_id",
    "settlement_id",
    "bank_transaction_id",
    "true_match",
    "exception_type",
]

EXCEPTION_FIELDS = [
    "exception_type",
    "chain_id",
    "payment_id",
    "settlement_id",
    "bank_transaction_id",
]


def build_clean_ground_truth(
    orders,
    payments,
    settlements,
    banks,
):
    """Build authoritative relationships from clean data."""

    orders_by_chain = {
        order["chain_id"]: order
        for order in orders
    }

    banks_by_reference = {
        bank["reference"]: bank
        for bank in banks
    }

    rows = []

    for settlement in settlements:
        payment_id = settlement["payment_id"]
        chain_id = settlement["chain_id"]

        order = orders_by_chain.get(chain_id)

        bank = banks_by_reference.get(
            settlement["settlement_reference"]
        )

        if order is None or bank is None:
            continue

        rows.append(
            {
                "chain_id": chain_id,
                "order_id": order["order_id"],
                "payment_id": payment_id,
                "settlement_id": settlement["settlement_id"],
                "bank_transaction_id": bank["transaction_id"],
                "true_match": "true",
                "exception_type": "NONE",
            }
        )

    return rows


def write_csv(filename, rows, fieldnames):
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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

    print(f"✅ Wrote {len(rows)} rows to {path}")


def main():

    print("=" * 60)
    print("GENERATING CLEAN DATASET")
    print("=" * 60)

    orders, payments, settlements, banks = generate_dataset(100)

    print("✅ Generated 100 clean chains")

    # ---------------------------------------------------------
    # 1. Build ground truth BEFORE corruption
    # ---------------------------------------------------------

    ground_truth = build_clean_ground_truth(
        orders,
        payments,
        settlements,
        banks,
    )

    write_csv(
        "ground_truth.csv",
        ground_truth,
        GROUND_TRUTH_FIELDS,
    )

    # ---------------------------------------------------------
    # 2. Apply controlled corruption
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("APPLYING EXCEPTIONS")
    print("=" * 60)

    events = []

    (
        corrupted_orders,
        corrupted_payments,
        corrupted_settlements,
        corrupted_banks,
    ) = apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(SEED),
        rates=DEFAULT_EXCEPTION_RATES,
        events=events,
    )

    print(
        f"✅ Generated {len(events)} exception events"
    )

    # ---------------------------------------------------------
    # 3. Save corrupted datasets
    # ---------------------------------------------------------

    write_csv(
        "corrupted_orders.csv",
        corrupted_orders,
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
        "corrupted_payments.csv",
        corrupted_payments,
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
        "corrupted_settlements.csv",
        corrupted_settlements,
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
        "corrupted_bank.csv",
        corrupted_banks,
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

    # ---------------------------------------------------------
    # 4. Save exception events
    # ---------------------------------------------------------

    write_csv(
        "exceptions.csv",
        events,
        EXCEPTION_FIELDS,
    )

    print()
    print("=" * 60)
    print("DATA GENERATION COMPLETE")
    print("=" * 60)

    print(f"Clean orders:       {len(orders)}")
    print(f"Clean payments:     {len(payments)}")
    print(f"Clean settlements:  {len(settlements)}")
    print(f"Clean bank:         {len(banks)}")

    print()
    print(f"Corrupted orders:      {len(corrupted_orders)}")
    print(f"Corrupted payments:    {len(corrupted_payments)}")
    print(f"Corrupted settlements: {len(corrupted_settlements)}")
    print(f"Corrupted bank:        {len(corrupted_banks)}")

    print()
    print(f"Exception events:      {len(events)}")


if __name__ == "__main__":
    main()
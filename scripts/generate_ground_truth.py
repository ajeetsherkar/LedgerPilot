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

SEED = 42

FIELDNAMES = [
    "chain_id",
    "order_id",
    "payment_id",
    "settlement_id",
    "bank_transaction_id",
    "true_match",
    "exception_type",
]


def build_clean_ground_truth(
    orders,
    payments,
    settlements,
    banks,
):
    """
    Build the authoritative clean payment -> settlement -> bank
    relationships.

    This function does not use the reconciliation engine.
    """

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


def write_ground_truth(rows):
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        GROUND_TRUTH_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(rows)

    print(
        f"✅ Wrote {len(rows)} rows to {GROUND_TRUTH_FILE}"
    )


def main():
    """
    Generate the clean authoritative ground truth.

    The corrupted dataset is generated only to verify that
    ground truth generation does not depend on reconciliation.
    """

    orders, payments, settlements, banks = generate_dataset(100)

    # Generate corrupted data independently.
    #
    # IMPORTANT:
    # Ground truth is NOT passed into apply_exceptions().
    #
    apply_exceptions(
        orders,
        payments,
        settlements,
        banks,
        random.Random(SEED),
        rates=DEFAULT_EXCEPTION_RATES,
    )

    ground_truth = build_clean_ground_truth(
        orders,
        payments,
        settlements,
        banks,
    )

    write_ground_truth(ground_truth)


if __name__ == "__main__":
    main()

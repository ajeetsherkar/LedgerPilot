import csv
import random
from pathlib import Path

from scripts.generate_data import generate_dataset
from scripts.generate_ground_truth import build_clean_ground_truth
from scripts.exceptions import (
    apply_exceptions,
    DEFAULT_EXCEPTION_RATES,
)


DATA_DIR = Path("data")

DEV_DIR = DATA_DIR / "dev"
HELDOUT_DIR = DATA_DIR / "heldout"
GROUND_TRUTH_DIR = DATA_DIR / "ground_truth"

DEV_COUNT = 350
HELDOUT_COUNT = 150

DEV_SEED = 42
HELDOUT_SEED = 4242

DEV_EXCEPTION_SEED = 1042
HELDOUT_EXCEPTION_SEED = 5242

ORDERS_FIELDS = [
    "chain_id",
    "order_id",
    "merchant_id",
    "customer_id",
    "customer_name",
    "order_amount",
    "currency",
    "order_date",
    "status",
]

PAYMENTS_FIELDS = [
    "chain_id",
    "payment_id",
    "order_id",
    "payment_method",
    "upi_ref",
    "amount",
    "currency",
    "payment_date",
    "status",
]

SETTLEMENTS_FIELDS = [
    "chain_id",
    "settlement_id",
    "payment_id",
    "gross_amount",
    "platform_fee",
    "gst_on_fee",
    "net_amount",
    "settlement_date",
    "settlement_reference",
]

BANK_FIELDS = [
    "chain_id",
    "transaction_id",
    "transaction_date",
    "credit_amount",
    "currency",
    "narration",
    "reference",
]

GROUND_TRUTH_FIELDS = [
    "chain_id",
    "order_id",
    "payment_id",
    "settlement_id",
    "bank_transaction_id",
    "true_match",
    "exception_type",
]


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)

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

    print(f"✅ {path}: {len(rows)} rows")


def write_dataset(
    output_dir,
    orders,
    payments,
    settlements,
    banks,
):
    write_csv(
        output_dir / "orders.csv",
        orders,
        ORDERS_FIELDS,
    )

    write_csv(
        output_dir / "payments.csv",
        payments,
        PAYMENTS_FIELDS,
    )

    write_csv(
        output_dir / "settlements.csv",
        settlements,
        SETTLEMENTS_FIELDS,
    )

    write_csv(
        output_dir / "bank.csv",
        banks,
        BANK_FIELDS,
    )


def generate_split(
    name,
    count,
    data_seed,
    exception_seed,
    output_dir,
    id_prefix="",
):
    print()
    print("=" * 60)
    print(f"GENERATING {name}")
    print("=" * 60)

    # ---------------------------------------------------------
    # 1. Generate independent clean dataset
    # ---------------------------------------------------------

    orders, payments, settlements, banks = generate_dataset(
        count,
        seed=data_seed,
        id_prefix=id_prefix,
    )

    print(
        f"✅ Generated {count} clean {name.lower()} chains"
    )

    # ---------------------------------------------------------
    # 2. Build ground truth BEFORE corruption
    # ---------------------------------------------------------

    ground_truth = build_clean_ground_truth(
        orders,
        payments,
        settlements,
        banks,
    )

    # ---------------------------------------------------------
    # 3. Apply controlled corruption
    # ---------------------------------------------------------

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
        random.Random(exception_seed),
        rates=DEFAULT_EXCEPTION_RATES,
        events=events,
    )

    print(
        f"✅ Generated {len(events)} exception events"
    )

    # ---------------------------------------------------------
    # 4. Write corrupted dataset
    # ---------------------------------------------------------

    write_dataset(
        output_dir,
        corrupted_orders,
        corrupted_payments,
        corrupted_settlements,
        corrupted_banks,
    )

    # ---------------------------------------------------------
    # 5. Return ground truth and events
    # ---------------------------------------------------------

    return ground_truth, events


def validate_counts():
    print()
    print("=" * 60)
    print("VALIDATING FINAL COUNTS")
    print("=" * 60)

    expected = {
        DEV_DIR / "orders.csv": DEV_COUNT,
        DEV_DIR / "payments.csv": DEV_COUNT,
        HELDOUT_DIR / "orders.csv": HELDOUT_COUNT,
        HELDOUT_DIR / "payments.csv": HELDOUT_COUNT,
    }

    for path, expected_count in expected.items():
        if not path.exists():
            raise RuntimeError(
                f"Missing expected file: {path}"
            )

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:
            actual_count = sum(
                1 for _ in file
            ) - 1

        if actual_count != expected_count:
            raise RuntimeError(
                f"{path}: expected {expected_count}, "
                f"found {actual_count}"
            )

        print(
            f"✅ {path}: {actual_count} rows"
        )

    # Settlement and bank row counts are allowed
    # to change because corruption can add/remove
    # records through duplicates, partial settlements,
    # missing-bank events, and combined settlements.
    variable_files = [
        DEV_DIR / "settlements.csv",
        DEV_DIR / "bank.csv",
        HELDOUT_DIR / "settlements.csv",
        HELDOUT_DIR / "bank.csv",
    ]

    for path in variable_files:
        if not path.exists():
            raise RuntimeError(
                f"Missing expected file: {path}"
            )

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:
            actual_count = sum(
                1 for _ in file
            ) - 1

        if actual_count <= 0:
            raise RuntimeError(
                f"{path}: file is empty"
            )

        print(
            f"✅ {path}: {actual_count} rows "
            "(corruption-adjusted)"
        )


def validate_chain_independence():
    print()
    print("=" * 60)
    print("VALIDATING DEV / HELD-OUT INDEPENDENCE")
    print("=" * 60)

    dev_chain_ids = set()

    with open(
        DEV_DIR / "orders.csv",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            dev_chain_ids.add(row["chain_id"])

    heldout_chain_ids = set()

    with open(
        HELDOUT_DIR / "orders.csv",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            heldout_chain_ids.add(row["chain_id"])

    overlap = dev_chain_ids & heldout_chain_ids

    if overlap:
        raise RuntimeError(
            f"DEV / HELD-OUT chain overlap: {overlap}"
        )

    print(
        "✅ No chain IDs overlap between DEV and HELD-OUT"
    )


def main():
    print()
    print("#" * 60)
    print("# LEDGERPILOT — SESSION 10 FINAL DATASET")
    print("#" * 60)

    # ---------------------------------------------------------
    # Generate DEV
    # ---------------------------------------------------------

    dev_ground_truth, _ = generate_split(
        name="DEVELOPMENT",
        count=DEV_COUNT,
        data_seed=DEV_SEED,
        exception_seed=DEV_EXCEPTION_SEED,
        output_dir=DEV_DIR,
        id_prefix="",
    )

    # ---------------------------------------------------------
    # Generate HELD-OUT
    # ---------------------------------------------------------

    heldout_ground_truth, _ = generate_split(
        name="HELD-OUT",
        count=HELDOUT_COUNT,
        data_seed=HELDOUT_SEED,
        exception_seed=HELDOUT_EXCEPTION_SEED,
        output_dir=HELDOUT_DIR,
        id_prefix="H",
    )

    # ---------------------------------------------------------
    # Ground truth
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("WRITING GROUND TRUTH")
    print("=" * 60)

    write_csv(
        GROUND_TRUTH_DIR / "dev_ground_truth.csv",
        dev_ground_truth,
        GROUND_TRUTH_FIELDS,
    )

    write_csv(
        GROUND_TRUTH_DIR / "heldout_ground_truth.csv",
        heldout_ground_truth,
        GROUND_TRUTH_FIELDS,
    )

    # ---------------------------------------------------------
    # Final structural validation
    # ---------------------------------------------------------

    validate_counts()
    validate_chain_independence()

    print()
    print("#" * 60)
    print("# SESSION 10 DATASET GENERATION COMPLETE")
    print("#" * 60)
    print()
    print("DEV:       350 chains")
    print("HELD-OUT:  150 chains")
    print("TOTAL:     500 chains")
    print()
    print("⚠️ HELD-OUT DATASET MUST NOW BE FROZEN.")
    print("⚠️ DO NOT USE HELD-OUT GROUND TRUTH FOR ENGINE TUNING.")


if __name__ == "__main__":
    main()
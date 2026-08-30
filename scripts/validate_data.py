import pandas as pd
from pathlib import Path


DATA_DIR = Path("data")

EXPECTED_COLUMNS = {
    "orders.csv": [
        "order_id",
        "order_date",
        "customer_id",
        "currency",
        "gross_amount",
    ],
    "payments.csv": [
        "payment_id",
        "order_id",
        "payment_date",
        "payment_method",
        "currency",
        "paid_amount",
        "transaction_ref",
    ],
    "settlements.csv": [
        "settlement_id",
        "order_id",
        "settlement_date",
        "currency",
        "settled_amount",
        "settlement_ref",
    ],
    "bank_transactions.csv": [
        "bank_txn_id",
        "transaction_date",
        "currency",
        "amount",
        "transaction_ref",
        "description",
    ],
}


def validate_file(filename, expected_columns):
    path = DATA_DIR / filename

    if not path.exists():
        print(f"❌ {filename}: file not found")
        return False

    df = pd.read_csv(path)

    if df.empty:
        print(f"❌ {filename}: file is empty")
        return False

    actual_columns = list(df.columns)

    if actual_columns != expected_columns:
        print(f"❌ {filename}: column mismatch")
        print(f"   Expected: {expected_columns}")
        print(f"   Found:    {actual_columns}")
        return False

    print(f"✅ {filename}: valid ({len(df)} rows)")
    return True


def main():
    print("LedgerPilot Data Validation")
    print("=" * 30)

    results = []

    for filename, expected_columns in EXPECTED_COLUMNS.items():
        results.append(
            validate_file(filename, expected_columns)
        )

    print("=" * 30)

    if all(results):
        print("✅ All datasets passed validation.")
    else:
        print("❌ Dataset validation failed.")


if __name__ == "__main__":
    main()
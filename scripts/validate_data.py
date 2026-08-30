import pandas as pd
from pathlib import Path


DATA_DIR = Path("data")

EXPECTED_COLUMNS = {
    "orders.csv": [
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

    "payments.csv": [
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

    "settlements.csv": [
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

    "bank.csv": [
        "chain_id",
        "transaction_id",
        "transaction_date",
        "credit_amount",
        "currency",
        "narration",
        "reference",
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
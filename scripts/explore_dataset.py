import pandas as pd
from pathlib import Path

from scripts.exceptions import DEFAULT_EXCEPTION_RATES


DATA_DIR = Path("data")


def load_datasets():
    """
    Load the datasets used for Session 9 exploration.

    ground_truth.csv represents the 100 clean chains.

    corrupted_*.csv represent the datasets after
    exception injection.

    exceptions.csv contains the injected exception events.
    """

    ground_truth = pd.read_csv(
        DATA_DIR / "ground_truth.csv"
    )

    corrupted = {
        "orders": pd.read_csv(
            DATA_DIR / "corrupted_orders.csv"
        ),
        "payments": pd.read_csv(
            DATA_DIR / "corrupted_payments.csv"
        ),
        "settlements": pd.read_csv(
            DATA_DIR / "corrupted_settlements.csv"
        ),
        "bank": pd.read_csv(
            DATA_DIR / "corrupted_bank.csv"
        ),
    }

    exceptions = pd.read_csv(
        DATA_DIR / "exceptions.csv"
    )

    return ground_truth, corrupted, exceptions


def print_total_records(ground_truth, corrupted):
    print("=" * 60)
    print("1. TOTAL RECORDS")
    print("=" * 60)

    print(
        f"{'Dataset':<15}"
        f"{'Clean':>10}"
        f"{'Corrupted':>12}"
    )

    clean_count = len(ground_truth)

    for name in ["orders", "payments", "settlements", "bank"]:

        print(
            f"{name.capitalize():<15}"
            f"{clean_count:>10}"
            f"{len(corrupted[name]):>12}"
        )

    print()

    total_chains = (
        ground_truth["chain_id"].nunique()
    )

    print(f"Total chains:       {total_chains}")


def print_exception_distribution(exceptions):
    print("=" * 60)
    print("2. EXCEPTION DISTRIBUTION")
    print("=" * 60)

    exception_types = [
        "NONE",
        "DATE_DRIFT",
        "MISSING_BANK",
        "AMOUNT_MISMATCH",
        "DUPLICATE",
        "FUZZY_REFERENCE",
        "PARTIAL_SETTLEMENT",
        "COMBINED_SETTLEMENT",
    ]

    counts = exceptions["exception_type"].value_counts()

    total_chains = (
        pd.read_csv(
            DATA_DIR / "ground_truth.csv"
        )["chain_id"].nunique()
    )

    injected_count = (
        exceptions["chain_id"].nunique()
    )

    counts_with_none = counts.to_dict()

    counts_with_none["NONE"] = (
        total_chains - injected_count
    )

    for exception_type in exception_types:

        print(
            f"{exception_type:<25}"
            f"{counts_with_none.get(exception_type, 0):>5}"
        )


def describe_amounts(df, column):
    series = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    return {
        "count": series.count(),
        "mean": series.mean(),
        "min": series.min(),
        "max": series.max(),
        "median": series.median(),
    }


def print_amount_stats(label, stats):
    print(f"\n{label}")
    print(f"count:   {stats['count']}")
    print(f"mean:    {stats['mean']:.2f}")
    print(f"min:     {stats['min']:.2f}")
    print(f"max:     {stats['max']:.2f}")
    print(f"median:  {stats['median']:.2f}")


def print_amount_distribution(corrupted):
    print("=" * 60)
    print("3. AMOUNT DISTRIBUTION")
    print("=" * 60)

    columns = {
        "Orders": ("orders", "order_amount"),
        "Payments": ("payments", "amount"),
        "Settlements": ("settlements", "net_amount"),
        "Bank": ("bank", "credit_amount"),
    }

    for label, (dataset_name, column) in columns.items():
        stats = describe_amounts(
            corrupted[dataset_name],
            column
        )

        print_amount_stats(
            f"{label} - Generated",
            stats
        )


def print_date_range(label, df, column):
    dates = pd.to_datetime(
        df[column],
        errors="coerce"
    )

    print(
        f"{label:<25}"
        f"{dates.min().date()} -> "
        f"{dates.max().date()}"
    )


def print_date_range_section(corrupted):
    print("=" * 60)
    print("4. DATE RANGE")
    print("=" * 60)

    columns = {
        "Orders": ("orders", "order_date"),
        "Payments": ("payments", "payment_date"),
        "Settlements": ("settlements", "settlement_date"),
        "Bank": ("bank", "transaction_date"),
    }

    for label, (dataset_name, column) in columns.items():
        print_date_range(
            f"{label} - Generated",
            corrupted[dataset_name],
            column,
        )


def print_clean_vs_corrupted(
    ground_truth,
    exceptions
):
    print("=" * 60)
    print("5. CLEAN VS CORRUPTED")
    print("=" * 60)

    total_chains = (
        ground_truth["chain_id"].nunique()
    )

    corrupted_chains = (
        exceptions["chain_id"].nunique()
    )

    clean_chains = (
        total_chains - corrupted_chains
    )

    print(f"Total chains:       {total_chains}")
    print(f"Clean chains:       {clean_chains}")
    print(f"Corrupted chains:   {corrupted_chains}")


def print_injection_rates(
    ground_truth,
    exceptions
):
    print("=" * 60)
    print("6. INJECTION-RATE COMPARISON")
    print("=" * 60)

    configured_rates = DEFAULT_EXCEPTION_RATES

    total_chains = (
        ground_truth["chain_id"].nunique()
    )

    counts = (
        exceptions["exception_type"]
        .value_counts()
    )

    mapping = {
        "date_drift": "DATE_DRIFT",
        "amount_mismatch": "AMOUNT_MISMATCH",
        "missing_bank": "MISSING_BANK",
        "duplicate": "DUPLICATE",
        "fuzzy_reference": "FUZZY_REFERENCE",
        "partial_settlement": "PARTIAL_SETTLEMENT",
        "combined_settlement": "COMBINED_SETTLEMENT",
    }

    print(
        f"{'Scenario':<25}"
        f"{'Configured':>12}"
        f"{'Actual':>12}"
    )

    print("-" * 49)

    for config_name, exception_type in mapping.items():

        configured_rate = (
            configured_rates.get(
                config_name,
                0
            )
        )

        exception_count = counts.get(
            exception_type,
            0
        )

        actual_rate = (
            exception_count / total_chains
            if total_chains
            else 0
        )

        label = (
            exception_type
            .replace("_", " ")
            .title()
        )

        print(
            f"{label:<25}"
            f"{configured_rate * 100:>10.1f}%"
            f"{actual_rate * 100:>10.1f}%"
        )


def main():

    (
        ground_truth,
        corrupted,
        exceptions
    ) = load_datasets()

    print_total_records(
        ground_truth,
        corrupted
    )

    print_exception_distribution(
        exceptions
    )

    print_amount_distribution(
        corrupted
    )

    print_date_range_section(
        corrupted
    )

    print_clean_vs_corrupted(
        ground_truth,
        exceptions
    )

    print_injection_rates(
        ground_truth,
        exceptions
    )


if __name__ == "__main__":
    main()
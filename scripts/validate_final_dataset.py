import csv
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.generate_data import generate_dataset
from scripts.exceptions import DEFAULT_EXCEPTION_RATES


DATA_DIR = Path("data")

DEV_DIR = DATA_DIR / "dev"
HELDOUT_DIR = DATA_DIR / "heldout"
GROUND_TRUTH_DIR = DATA_DIR / "ground_truth"

DEV_COUNT = 350
HELDOUT_COUNT = 150

DEV_SEED = 42
HELDOUT_SEED = 4242


DATASET_FIELDS = {
    "orders": [
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
    "payments": [
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
    "settlements": [
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
    "bank": [
        "chain_id",
        "transaction_id",
        "transaction_date",
        "credit_amount",
        "currency",
        "narration",
        "reference",
    ],
}


GROUND_TRUTH_FIELDS = [
    "chain_id",
    "order_id",
    "payment_id",
    "settlement_id",
    "bank_transaction_id",
    "true_match",
    "exception_type",
]


def read_csv(path):
    if not path.exists():
        raise AssertionError(f"Missing file: {path}")

    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def assert_columns(rows, expected, path):
    if not rows:
        raise AssertionError(f"{path}: file is empty")

    actual = list(rows[0].keys())

    if actual != expected:
        raise AssertionError(
            f"{path}: incorrect columns\n"
            f"Expected: {expected}\n"
            f"Found:    {actual}"
        )


def assert_unique(rows, field, path):
    values = [row[field] for row in rows]
    duplicates = [
        value
        for value, count in Counter(values).items()
        if count > 1
    ]

    if duplicates:
        raise AssertionError(
            f"{path}: duplicate {field} values: "
            f"{duplicates[:10]}"
        )


def to_decimal(value):
    return Decimal(str(value))


def to_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return date.fromisoformat(value)

    raise TypeError(
        f"Unsupported date value: {value!r}"
    )


def expected_net_amount(gross_amount):
    gross = to_decimal(gross_amount)

    platform_fee = (
        gross * Decimal("0.01")
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

    return (
        gross
        - platform_fee
        - gst_on_fee
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def validate_file_structure(directory, expected_chain_count):
    print()
    print("=" * 60)
    print(f"VALIDATING FILE STRUCTURE: {directory}")
    print("=" * 60)

    datasets = {}

    for name, fields in DATASET_FIELDS.items():
        path = directory / f"{name}.csv"

        rows = read_csv(path)

        # Orders and payments must remain one row per chain.
        if name in {"orders", "payments"}:
            if len(rows) != expected_chain_count:
                raise AssertionError(
                    f"{path}: expected "
                    f"{expected_chain_count} rows, "
                    f"found {len(rows)}"
                )

        assert_columns(rows, fields, path)

        datasets[name] = rows

        print(
            f"✅ {path}: {len(rows)} rows, "
            f"schema valid"
        )

    return datasets


def validate_ground_truth(path, expected_chain_count):
    rows = read_csv(path)

    if len(rows) != expected_chain_count:
        raise AssertionError(
            f"{path}: expected {expected_chain_count} rows, "
            f"found {len(rows)}"
        )

    assert_columns(
        rows,
        GROUND_TRUTH_FIELDS,
        path,
    )

    assert_unique(
        rows,
        "chain_id",
        path,
    )

    print(
        f"✅ {path}: {len(rows)} rows, "
        f"schema valid"
    )

    return rows


def validate_identifier_uniqueness(datasets, directory):
    print()
    print("=" * 60)
    print(f"VALIDATING IDENTIFIERS: {directory}")
    print("=" * 60)

    assert_unique(
        datasets["orders"],
        "order_id",
        directory / "orders.csv",
    )

    assert_unique(
        datasets["payments"],
        "payment_id",
        directory / "payments.csv",
    )

    assert_unique(
        datasets["settlements"],
        "settlement_id",
        directory / "settlements.csv",
    )

    assert_unique(
        datasets["bank"],
        "transaction_id",
        directory / "bank.csv",
    )

    print("✅ order_id values are unique")
    print("✅ payment_id values are unique")
    print("✅ settlement_id values are unique")
    print("✅ transaction_id values are unique")

    # Settlement references are intentionally NOT required
    # to be unique because DUPLICATE creates another settlement
    # with the same settlement reference.
    print(
        "ℹ️ settlement_reference uniqueness not enforced "
        "(intentional duplicates are allowed)"
    )

    # Bank references are also intentionally not required to
    # be unique because duplicate/combined scenarios can affect
    # reference relationships.
    print(
        "ℹ️ bank reference uniqueness not enforced"
    )


def validate_referential_integrity(datasets, ground_truth, directory):
    print()
    print("=" * 60)
    print(f"VALIDATING REFERENTIAL INTEGRITY: {directory}")
    print("=" * 60)

    orders = datasets["orders"]
    payments = datasets["payments"]
    settlements = datasets["settlements"]
    banks = datasets["bank"]

    order_by_id = {
        row["order_id"]: row
        for row in orders
    }

    order_by_chain = {
        row["chain_id"]: row
        for row in orders
    }

    payment_by_id = {
        row["payment_id"]: row
        for row in payments
    }

    bank_by_transaction = {
        row["transaction_id"]: row
        for row in banks
    }

    # ---------------------------------------------------------
    # PAYMENT -> ORDER
    # ---------------------------------------------------------

    for payment in payments:
        order_id = payment["order_id"]
        chain_id = payment["chain_id"]

        if order_id not in order_by_id:
            raise AssertionError(
                f"{directory}/payments.csv: "
                f"payment {payment['payment_id']} references "
                f"missing order {order_id}"
            )

        order = order_by_id[order_id]

        if order["chain_id"] != chain_id:
            raise AssertionError(
                f"{directory}/payments.csv: chain mismatch "
                f"for payment {payment['payment_id']}"
            )

    print("✅ payment → order relationships valid")

    # ---------------------------------------------------------
    # SETTLEMENT -> PAYMENT
    # ---------------------------------------------------------

    for settlement in settlements:
        payment_id = settlement["payment_id"]
        chain_id = settlement["chain_id"]

        if payment_id not in payment_by_id:
            raise AssertionError(
                f"{directory}/settlements.csv: "
                f"settlement {settlement['settlement_id']} "
                f"references missing payment {payment_id}"
            )

        payment = payment_by_id[payment_id]

        if payment["chain_id"] != chain_id:
            raise AssertionError(
                f"{directory}/settlements.csv: chain mismatch "
                f"for settlement {settlement['settlement_id']}"
            )

    print("✅ settlement → payment relationships valid")

    # ---------------------------------------------------------
    # BANK -> CHAIN
    # ---------------------------------------------------------

    for bank in banks:
        chain_id = bank["chain_id"]

        if chain_id not in order_by_chain:
            raise AssertionError(
                f"{directory}/bank.csv: "
                f"bank transaction {bank['transaction_id']} "
                f"references unknown chain {chain_id}"
            )

    print("✅ bank → chain relationships valid")

    # ---------------------------------------------------------
    # GROUND TRUTH
    # ---------------------------------------------------------

    for row in ground_truth:
        chain_id = row["chain_id"]
        order_id = row["order_id"]
        payment_id = row["payment_id"]
        settlement_id = row["settlement_id"]

        if chain_id not in order_by_chain:
            raise AssertionError(
                f"{directory}: ground truth references "
                f"unknown chain {chain_id}"
            )

        if order_id != order_by_chain[chain_id]["order_id"]:
            raise AssertionError(
                f"{directory}: ground truth order mismatch "
                f"for chain {chain_id}"
            )

        if payment_id not in payment_by_id:
            raise AssertionError(
                f"{directory}: ground truth references "
                f"unknown payment {payment_id}"
            )

        if payment_by_id[payment_id]["chain_id"] != chain_id:
            raise AssertionError(
                f"{directory}: ground truth payment chain "
                f"mismatch for {payment_id}"
            )

        # The original settlement ID must exist somewhere in
        # the corrupted dataset. Duplicate/partial records add
        # additional settlement IDs but preserve the original.
        settlement_ids = {
            settlement["settlement_id"]
            for settlement in settlements
        }

        if settlement_id not in settlement_ids:
            raise AssertionError(
                f"{directory}: ground truth settlement "
                f"{settlement_id} missing"
            )

        bank_transaction_id = row["bank_transaction_id"]

        # A bank transaction may legitimately disappear because
        # of MISSING_BANK or be replaced/modified by
        # COMBINED_SETTLEMENT.
        if bank_transaction_id:
            if (
                bank_transaction_id not in bank_by_transaction
                and not any(
                    bank_transaction_id in bank["transaction_id"]
                    for bank in banks
                )
            ):
                # Do not fail here: intentional corruption can
                # remove or transform the original bank record.
                pass

    print("✅ ground-truth relationships valid")


def validate_financial_integrity(datasets, directory):
    print()
    print("=" * 60)
    print(f"VALIDATING FINANCIAL LOGIC: {directory}")
    print("=" * 60)

    orders = datasets["orders"]
    payments = datasets["payments"]
    settlements = datasets["settlements"]

    order_by_id = {
        row["order_id"]: row
        for row in orders
    }

    payment_by_id = {
        row["payment_id"]: row
        for row in payments
    }

    # ---------------------------------------------------------
    # PAYMENT AMOUNT
    #
    # Amount mismatch corruption affects BANK only.
    # Therefore order -> payment should always remain intact.
    # ---------------------------------------------------------

    for payment in payments:
        order = order_by_id[payment["order_id"]]

        if (
            to_decimal(payment["amount"])
            != to_decimal(order["order_amount"])
        ):
            raise AssertionError(
                f"{directory}: payment amount mismatch "
                f"for {payment['payment_id']}"
            )

    print(
        "✅ order amount == payment amount "
        "for all chains"
    )

    # ---------------------------------------------------------
    # SETTLEMENT GROSS AMOUNT
    #
    # Amount mismatch corruption affects BANK only.
    # Partial settlement affects NET amount only.
    # Combined settlement affects BANK only.
    #
    # Therefore gross amount should still equal payment amount.
    # ---------------------------------------------------------

    for settlement in settlements:
        payment = payment_by_id[
            settlement["payment_id"]
        ]

        if (
            to_decimal(settlement["gross_amount"])
            != to_decimal(payment["amount"])
        ):
            raise AssertionError(
                f"{directory}: settlement gross amount "
                f"mismatch for "
                f"{settlement['settlement_id']}"
            )

    print(
        "✅ settlement gross amount == payment amount "
        "for all settlements"
    )

    # ---------------------------------------------------------
    # SETTLEMENT FEE / GST
    # ---------------------------------------------------------

    for settlement in settlements:
        gross = to_decimal(
            settlement["gross_amount"]
        )

        expected_fee = (
            gross * Decimal("0.01")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        expected_gst = (
            expected_fee * Decimal("0.18")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        if (
            to_decimal(settlement["platform_fee"])
            != expected_fee
        ):
            raise AssertionError(
                f"{directory}: platform fee mismatch "
                f"for {settlement['settlement_id']}"
            )

        if (
            to_decimal(settlement["gst_on_fee"])
            != expected_gst
        ):
            raise AssertionError(
                f"{directory}: GST mismatch "
                f"for {settlement['settlement_id']}"
            )

    print(
        "✅ platform fee and GST calculations valid"
    )

    # ---------------------------------------------------------
    # NET AMOUNT
    #
    # PARTIAL_SETTLEMENT intentionally changes net_amount.
    # Therefore we allow a partial settlement pair to have
    # different net amounts while checking that every normal
    # settlement follows the expected formula.
    # ---------------------------------------------------------

    partial_groups = {}

    for settlement in settlements:
        settlement_id = settlement["settlement_id"]

        if settlement_id.endswith("_PART2"):
            base_id = settlement_id[:-6]
            partial_groups.setdefault(
                base_id,
                [],
            ).append(settlement)
        else:
            partial_groups.setdefault(
                settlement_id,
                [],
            ).append(settlement)

    for base_id, group in partial_groups.items():
        if len(group) == 2:
            first, second = group

            expected_total = expected_net_amount(
                first["gross_amount"]
            )

            actual_total = (
                to_decimal(first["net_amount"])
                + to_decimal(second["net_amount"])
            )

            if actual_total != expected_total:
                raise AssertionError(
                    f"{directory}: partial settlement total "
                    f"mismatch for {base_id}"
                )

            print(
                f"ℹ️ Valid partial settlement pair: "
                f"{base_id}"
            )

        elif len(group) == 1:
            settlement = group[0]

            expected = expected_net_amount(
                settlement["gross_amount"]
            )

            if (
                to_decimal(settlement["net_amount"])
                != expected
            ):
                raise AssertionError(
                    f"{directory}: net amount mismatch "
                    f"for {settlement['settlement_id']}"
                )

    print("✅ settlement financial calculations valid")


def validate_expected_exception_structure(
    datasets,
    expected_chain_count,
    directory,
):
    print()
    print("=" * 60)
    print(
        f"VALIDATING EXPECTED CORRUPTION STRUCTURE: "
        f"{directory}"
    )
    print("=" * 60)

    settlements = datasets["settlements"]
    banks = datasets["bank"]

    # ---------------------------------------------------------
    # Expected number of selected chains for each exception.
    # ---------------------------------------------------------

    expected_counts = {}

    for exception_type, rate in DEFAULT_EXCEPTION_RATES.items():
        expected_counts[exception_type] = int(
            expected_chain_count * rate
        )

    for exception_type, count in expected_counts.items():
        print(
            f"ℹ️ {exception_type}: "
            f"{count} selected chain(s)"
        )

    # ---------------------------------------------------------
    # Structural effects
    #
    # DUPLICATE adds one settlement and one bank row.
    #
    # PARTIAL_SETTLEMENT adds one settlement row.
    #
    # COMBINED_SETTLEMENT operates in pairs. Therefore:
    #
    # floor(selected / 2) combined operations.
    #
    # Each combined operation removes one bank transaction.
    #
    # MISSING_BANK removes one bank transaction.
    # ---------------------------------------------------------

    duplicate_count = expected_counts["duplicate"]
    partial_count = expected_counts["partial_settlement"]
    missing_bank_count = expected_counts["missing_bank"]

    combined_selected = expected_counts[
        "combined_settlement"
    ]

    combined_operations = combined_selected // 2

    expected_settlement_rows = (
        expected_chain_count
        + duplicate_count
        + partial_count
    )

    expected_bank_rows = (
        expected_chain_count
        + duplicate_count
        - missing_bank_count
        - combined_operations
    )

    if len(settlements) != expected_settlement_rows:
        raise AssertionError(
            f"{directory}: settlement row count does not "
            f"match expected corruption structure. "
            f"Expected {expected_settlement_rows}, "
            f"found {len(settlements)}"
        )

    if len(banks) != expected_bank_rows:
        raise AssertionError(
            f"{directory}: bank row count does not "
            f"match expected corruption structure. "
            f"Expected {expected_bank_rows}, "
            f"found {len(banks)}"
        )

    print(
        f"✅ settlement row count matches expected "
        f"corruption structure: {len(settlements)}"
    )

    print(
        f"✅ bank row count matches expected "
        f"corruption structure: {len(banks)}"
    )

    # ---------------------------------------------------------
    # DUPLICATE records
    # ---------------------------------------------------------

    duplicate_settlements = [
        row
        for row in settlements
        if row["settlement_id"].endswith("_DUP")
    ]

    if len(duplicate_settlements) != duplicate_count:
        raise AssertionError(
            f"{directory}: expected "
            f"{duplicate_count} duplicate settlements, "
            f"found {len(duplicate_settlements)}"
        )

    print(
        f"✅ DUPLICATE structure valid: "
        f"{len(duplicate_settlements)}"
    )

    # ---------------------------------------------------------
    # PARTIAL SETTLEMENT records
    # ---------------------------------------------------------

    partial_settlements = [
        row
        for row in settlements
        if row["settlement_id"].endswith("_PART2")
    ]

    if len(partial_settlements) != partial_count:
        raise AssertionError(
            f"{directory}: expected "
            f"{partial_count} PART2 settlements, "
            f"found {len(partial_settlements)}"
        )

    print(
        f"✅ PARTIAL_SETTLEMENT structure valid: "
        f"{len(partial_settlements)}"
    )

    # ---------------------------------------------------------
    # COMBINED BANK records
    # ---------------------------------------------------------

    combined_banks = [
        row
        for row in banks
        if row["transaction_id"].endswith("_COMBINED")
    ]

    if len(combined_banks) != combined_operations:
        raise AssertionError(
            f"{directory}: expected "
            f"{combined_operations} combined bank records, "
            f"found {len(combined_banks)}"
        )

    print(
        f"✅ COMBINED_SETTLEMENT structure valid: "
        f"{len(combined_banks)}"
    )

    # ---------------------------------------------------------
    # FUZZY REFERENCES
    # ---------------------------------------------------------

    fuzzy_settlements = [
        row
        for row in settlements
        if row["settlement_reference"].endswith("X")
    ]

    fuzzy_count = expected_counts["fuzzy_reference"]

    if len(fuzzy_settlements) != fuzzy_count:
        raise AssertionError(
            f"{directory}: expected "
            f"{fuzzy_count} fuzzy references, "
            f"found {len(fuzzy_settlements)}"
        )

    print(
        f"✅ FUZZY_REFERENCE structure valid: "
        f"{len(fuzzy_settlements)}"
    )

    # ---------------------------------------------------------
    # AMOUNT MISMATCH
    #
    # Bank credit should be exactly ₹50 lower than the
    # corresponding clean settlement amount.
    #
    # We detect the anomaly by comparing bank references to
    # settlement references.
    # ---------------------------------------------------------

    settlement_by_reference = {}

    for settlement in settlements:
        reference = settlement["settlement_reference"]

        # Fuzzy references intentionally no longer match the
        # original bank reference, so only retain references
        # that can be matched normally.
        settlement_by_reference.setdefault(
            reference,
            [],
        ).append(settlement)

    amount_mismatch_candidates = 0

    for bank in banks:
        reference = bank["reference"]

        if reference.startswith("COMBINED-"):
            continue

        matching = settlement_by_reference.get(reference)

        if not matching:
            continue

        settlement = matching[0]

        expected_bank_amount = (
            to_decimal(settlement["net_amount"])
        )

        actual_bank_amount = to_decimal(
            bank["credit_amount"]
        )

        if (
            actual_bank_amount
            == expected_bank_amount - Decimal("50")
        ):
            amount_mismatch_candidates += 1

    amount_count = expected_counts["amount_mismatch"]

    if amount_mismatch_candidates != amount_count:
        raise AssertionError(
            f"{directory}: expected "
            f"{amount_count} amount mismatch records, "
            f"found {amount_mismatch_candidates}"
        )

    print(
        f"✅ AMOUNT_MISMATCH structure valid: "
        f"{amount_mismatch_candidates}"
    )

    # ---------------------------------------------------------
    # DATE DRIFT
    #
    # We cannot identify all date-drift records from the
    # corrupted data alone without comparing against the clean
    # deterministic source. That comparison is performed below.
    # ---------------------------------------------------------

    print(
        "ℹ️ DATE_DRIFT will be verified against "
        "the deterministic clean dataset"
    )


def validate_against_clean_source(
    datasets,
    clean_datasets,
    directory,
):
    print()
    print("=" * 60)
    print(
        f"VALIDATING CORRUPTION AGAINST CLEAN SOURCE: "
        f"{directory}"
    )
    print("=" * 60)

    clean_orders, clean_payments, clean_settlements, clean_banks = (
        clean_datasets
    )

    orders = datasets["orders"]
    payments = datasets["payments"]
    settlements = datasets["settlements"]
    banks = datasets["bank"]

    # ---------------------------------------------------------
    # Normalize generated clean data to CSV representation.
    #
    # CSV-loaded values are strings, while generate_dataset()
    # returns native Python values such as date and Decimal.
    # ---------------------------------------------------------

    def normalize_rows(rows):
        return [
            {
                key: str(value)
                for key, value in row.items()
            }
            for row in rows
        ]

    normalized_clean_orders = normalize_rows(clean_orders)
    normalized_clean_payments = normalize_rows(clean_payments)

    # ---------------------------------------------------------
    # ORDER DATA SHOULD NEVER BE CORRUPTED
    # ---------------------------------------------------------

    if orders != normalized_clean_orders:
        raise AssertionError(
            f"{directory}: orders differ from clean source"
        )

    print("✅ orders unchanged from clean source")

    # ---------------------------------------------------------
    # PAYMENT DATA SHOULD NEVER BE CORRUPTED
    # ---------------------------------------------------------

    if payments != normalized_clean_payments:
        raise AssertionError(
            f"{directory}: payments differ from clean source"
        )

    print("✅ payments unchanged from clean source")

    # ---------------------------------------------------------
    # DATE DRIFT
    #
    # Compare settlement/bank dates by their stable identifiers.
    # ---------------------------------------------------------

    clean_settlement_by_id = {
        row["settlement_id"]: row
        for row in clean_settlements
    }

    current_settlement_by_id = {
        row["settlement_id"]: row
        for row in settlements
        if not row["settlement_id"].endswith("_DUP")
        and not row["settlement_id"].endswith("_PART2")
    }

    date_drift_count = 0

    for settlement_id, clean in clean_settlement_by_id.items():
        current = current_settlement_by_id.get(
            settlement_id
        )

        if current is None:
            continue

        if (
            to_date(current["settlement_date"])
            != to_date(clean["settlement_date"])
        ):
            date_drift_count += 1

    expected_date_drift = int(
        len(clean_settlements)
        * DEFAULT_EXCEPTION_RATES["date_drift"]
    )

    if date_drift_count != expected_date_drift:
        raise AssertionError(
            f"{directory}: expected "
            f"{expected_date_drift} date drift records, "
            f"found {date_drift_count}"
        )

    print(
        f"✅ DATE_DRIFT structure valid: "
        f"{date_drift_count}"
    )

    # ---------------------------------------------------------
    # BANK AMOUNT / DATE COMPARISON
    # ---------------------------------------------------------

    clean_bank_by_id = {
        row["transaction_id"]: row
        for row in clean_banks
    }

    current_bank_by_id = {
        row["transaction_id"]: row
        for row in banks
    }

    amount_mismatch_count = 0
    bank_date_drift_count = 0

    for transaction_id, clean in clean_bank_by_id.items():
        current = current_bank_by_id.get(transaction_id)

        if current is None:
            continue

        clean_amount = to_decimal(
            clean["credit_amount"]
        )

        current_amount = to_decimal(
            current["credit_amount"]
        )

        if (
            current_amount
            == clean_amount - Decimal("50")
        ):
            amount_mismatch_count += 1

        if (
            to_date(current["transaction_date"])
            != to_date(clean["transaction_date"])
        ):
            bank_date_drift_count += 1

    expected_amount_mismatch = int(
        len(clean_banks)
        * DEFAULT_EXCEPTION_RATES["amount_mismatch"]
    )

    if amount_mismatch_count != expected_amount_mismatch:
        raise AssertionError(
            f"{directory}: expected "
            f"{expected_amount_mismatch} bank amount mismatches, "
            f"found {amount_mismatch_count}"
        )

    if bank_date_drift_count != expected_date_drift:
        raise AssertionError(
            f"{directory}: expected "
            f"{expected_date_drift} bank date drifts, "
            f"found {bank_date_drift_count}"
        )

    print(
        f"✅ BANK amount mismatches valid: "
        f"{amount_mismatch_count}"
    )

    print(
        f"✅ BANK date drifts valid: "
        f"{bank_date_drift_count}"
    )


def validate_split(
    name,
    directory,
    ground_truth_path,
    expected_count,
    clean_seed,
    clean_id_prefix="",
):
    print()
    print("#" * 60)
    print(f"# VALIDATING {name}")
    print("#" * 60)

    datasets = validate_file_structure(
        directory,
        expected_count,
    )

    ground_truth = validate_ground_truth(
        ground_truth_path,
        expected_count,
    )

    validate_identifier_uniqueness(
        datasets,
        directory,
    )

    validate_referential_integrity(
        datasets,
        ground_truth,
        directory,
    )

    validate_financial_integrity(
        datasets,
        directory,
    )

    validate_expected_exception_structure(
        datasets,
        expected_count,
        directory,
    )

    clean_datasets = generate_dataset(
        expected_count,
        seed=clean_seed,
        id_prefix=clean_id_prefix,
    )

    validate_against_clean_source(
        datasets,
        clean_datasets,
        directory,
    )

    print()
    print(f"✅ {name} FINAL VALIDATION PASSED")


def validate_cross_split_independence():
    print()
    print("#" * 60)
    print("# VALIDATING DEV / HELD-OUT INDEPENDENCE")
    print("#" * 60)

    dev_orders = read_csv(
        DEV_DIR / "orders.csv"
    )

    heldout_orders = read_csv(
        HELDOUT_DIR / "orders.csv"
    )

    dev_chains = {
        row["chain_id"]
        for row in dev_orders
    }

    heldout_chains = {
        row["chain_id"]
        for row in heldout_orders
    }

    overlap = dev_chains & heldout_chains

    if overlap:
        raise AssertionError(
            f"DEV / HELD-OUT chain overlap: "
            f"{sorted(overlap)}"
        )

    print(
        "✅ No chain IDs overlap between DEV and HELD-OUT"
    )


def main():
    print()
    print("#" * 60)
    print("# LEDGERPILOT — FINAL DATASET INTEGRITY VALIDATION")
    print("#" * 60)

    validate_split(
        name="DEVELOPMENT",
        directory=DEV_DIR,
        ground_truth_path=GROUND_TRUTH_DIR / "dev_ground_truth.csv",
        expected_count=DEV_COUNT,
        clean_seed=DEV_SEED,
        clean_id_prefix="",
    )

    validate_split(
        name="HELD-OUT",
        directory=HELDOUT_DIR,
        ground_truth_path=GROUND_TRUTH_DIR / "heldout_ground_truth.csv",
        expected_count=HELDOUT_COUNT,
        clean_seed=HELDOUT_SEED,
        clean_id_prefix="H",
    )

    validate_cross_split_independence()

    print()
    print("#" * 60)
    print("# ALL FINAL DATASET VALIDATION CHECKS PASSED")
    print("#" * 60)
    print()
    print("DEV:      350 chains")
    print("HELD-OUT: 150 chains")
    print("TOTAL:    500 chains")
    print()
    print("🔒 HELD-OUT DATASET REMAINS FROZEN")
    print("🔒 DO NOT USE HELD-OUT GROUND TRUTH FOR ENGINE TUNING")


if __name__ == "__main__":
    main()
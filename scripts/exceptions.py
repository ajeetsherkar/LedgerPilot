from copy import deepcopy
from datetime import timedelta
from decimal import Decimal


DEFAULT_EXCEPTION_RATES = {
    "date_drift": 0.10,
    "amount_mismatch": 0.05,
    "missing_bank": 0.05,
    "duplicate": 0.03,
    "fuzzy_reference": 0.03,
    "partial_settlement": 0.02,
    "combined_settlement": 0.02,
}


def apply_date_drift(settlement, bank, days):
    """
    Shift settlement and bank transaction dates
    without changing amounts or references.
    """

    settlement["settlement_date"] += timedelta(days=days)
    bank["transaction_date"] += timedelta(days=days)


def apply_missing_bank(settlement, banks):
    """
    Remove the bank transaction corresponding to a settlement.

    The settlement itself remains unchanged.
    """

    settlement_reference = settlement["settlement_reference"]

    for index, bank in enumerate(banks):
        if bank["reference"] == settlement_reference:
            banks.pop(index)
            return True

    return False


def apply_amount_mismatch(bank, amount_difference=50):
    """
    Change the bank credit amount while keeping the
    underlying settlement unchanged.
    """

    bank["credit_amount"] -= amount_difference

    return True


def apply_duplicate(settlements, banks, settlement_index):
    """
    Duplicate one settlement and its corresponding bank transaction.
    """
    settlement = deepcopy(settlements[settlement_index])

    settlement["settlement_id"] = (
        f"{settlement['settlement_id']}_DUP"
    )

    bank = None

    for candidate in banks:
        if candidate["reference"] == settlements[settlement_index]["settlement_reference"]:
            bank = deepcopy(candidate)
            break

    if bank is None:
        return False

    bank["transaction_id"] = (
        f"{bank['transaction_id']}_DUP"
    )

    settlements.append(settlement)
    banks.append(bank)

    return True


def apply_fuzzy_reference(settlement, bank):
    """
    Slightly modify the settlement reference while keeping
    the underlying transaction otherwise unchanged.
    """
    reference = settlement["settlement_reference"]

    if not reference:
        return False

    settlement["settlement_reference"] = (
        reference + "X"
    )

    return True


def apply_partial_settlement(settlements, settlement_index):
    """
    Convert one settlement into two settlement records
    for the same payment.

    The total settlement amount remains unchanged.
    """

    original = deepcopy(settlements[settlement_index])

    first_amount = (
        original["net_amount"] / Decimal("2")
    ).quantize(Decimal("0.01"))

    second_amount = original["net_amount"] - first_amount

    settlements[settlement_index]["net_amount"] = first_amount

    second = deepcopy(original)

    second["settlement_id"] = (
        f"{original['settlement_id']}_PART2"
    )

    second["net_amount"] = second_amount

    settlements.append(second)

    return True


def apply_combined_settlement(settlements, banks, first_index, second_index):
    """
    Combine two settlement-related bank transactions into
    one bank credit representing multiple payments.
    """

    first_settlement = settlements[first_index]
    second_settlement = settlements[second_index]

    first_reference = first_settlement["settlement_reference"]
    second_reference = second_settlement["settlement_reference"]

    first_bank = None
    second_bank = None

    for bank in banks:
        if bank["reference"] == first_reference:
            first_bank = bank

        if bank["reference"] == second_reference:
            second_bank = bank

    if first_bank is None or second_bank is None:
        return False

    first_bank["credit_amount"] = (
        first_bank["credit_amount"]
        + second_bank["credit_amount"]
    )

    first_bank["transaction_id"] = (
        f"{first_bank['transaction_id']}_COMBINED"
    )

    first_bank["reference"] = (
        f"COMBINED-{first_reference}-{second_reference}"
    )

    first_bank["narration"] = (
        f"Combined settlement for "
        f"{first_settlement['payment_id']} and "
        f"{second_settlement['payment_id']}"
    )

    banks.remove(second_bank)

    return True


def apply_exceptions(
    orders,
    payments,
    settlements,
    banks,
    rng,
    rates=None,
):
    """
    Apply controlled corruption to an already-clean dataset.

    Ground-truth design:
        CLEAN DATA
             ↓
        CORRUPTION
             ↓
        CORRUPTED DATA

    The original clean dataset is never modified in place.

    Exception records are selected deterministically using the
    supplied random number generator.
    """

    if rates is None:
        rates = DEFAULT_EXCEPTION_RATES.copy()

    # Deep-copy all datasets so the clean source remains untouched.
    orders = deepcopy(orders)
    payments = deepcopy(payments)
    settlements = deepcopy(settlements)
    banks = deepcopy(banks)

    # Nothing to corrupt.
    if not settlements:
        return (
            orders,
            payments,
            settlements,
            banks,
        )

    # Select settlement records deterministically.
    #
    # Using one shuffled list and separate slices means:
    # - selections are deterministic for a given RNG seed
    # - exception types do not overlap
    # - each configured rate gets its own records
    indices = list(range(len(settlements)))
    rng.shuffle(indices)

    def select_indices(rate):
        count = int(len(indices) * rate)
        return indices[:count]

    date_drift_indices = select_indices(
        rates.get("date_drift", 0)
    )

    remaining = [
        index
        for index in indices
        if index not in date_drift_indices
    ]

    def select_from_remaining(rate):
        count = int(len(indices) * rate)
        selected = remaining[:count]
        del remaining[:count]
        return selected

    amount_mismatch_indices = select_from_remaining(
        rates.get("amount_mismatch", 0)
    )

    missing_bank_indices = select_from_remaining(
        rates.get("missing_bank", 0)
    )

    duplicate_indices = select_from_remaining(
        rates.get("duplicate", 0)
    )

    fuzzy_reference_indices = select_from_remaining(
        rates.get("fuzzy_reference", 0)
    )

    partial_settlement_indices = select_from_remaining(
        rates.get("partial_settlement", 0)
    )

    combined_settlement_indices = select_from_remaining(
        rates.get("combined_settlement", 0)
    )

    # Build a lookup from settlement reference to bank record.
    bank_by_reference = {
        bank["reference"]: bank
        for bank in banks
    }

    # ---------------------------------------------------------
    # 1. DATE DRIFT
    # ---------------------------------------------------------
    for index in date_drift_indices:
        settlement = settlements[index]

        bank = bank_by_reference.get(
            settlement["settlement_reference"]
        )

        if bank is not None:
            apply_date_drift(
                settlement,
                bank,
                days=3,
            )

    # ---------------------------------------------------------
    # 2. AMOUNT MISMATCH
    # ---------------------------------------------------------
    for index in amount_mismatch_indices:
        settlement = settlements[index]

        bank = bank_by_reference.get(
            settlement["settlement_reference"]
        )

        if bank is not None:
            apply_amount_mismatch(bank)

    # ---------------------------------------------------------
    # 3. MISSING BANK
    # ---------------------------------------------------------
    for index in missing_bank_indices:
        settlement = settlements[index]

        apply_missing_bank(
            settlement,
            banks,
        )

    # ---------------------------------------------------------
    # 4. DUPLICATE
    # ---------------------------------------------------------
    for index in duplicate_indices:
        apply_duplicate(
            settlements,
            banks,
            index,
        )

    # ---------------------------------------------------------
    # 5. FUZZY REFERENCE
    # ---------------------------------------------------------
    for index in fuzzy_reference_indices:
        settlement = settlements[index]

        bank = bank_by_reference.get(
            settlement["settlement_reference"]
        )

        if bank is not None:
            apply_fuzzy_reference(
                settlement,
                bank,
            )

    # ---------------------------------------------------------
    # 6. PARTIAL SETTLEMENT
    # ---------------------------------------------------------
    for index in partial_settlement_indices:
        apply_partial_settlement(
            settlements,
            index,
        )

    # ---------------------------------------------------------
    # 7. COMBINED SETTLEMENT
    # ---------------------------------------------------------
    combined_indices = combined_settlement_indices[:]

    while len(combined_indices) >= 2:
        first_index = combined_indices.pop()
        second_index = combined_indices.pop()

        apply_combined_settlement(
            settlements,
            banks,
            first_index,
            second_index,
        )

    return (
        orders,
        payments,
        settlements,
        banks,
    )
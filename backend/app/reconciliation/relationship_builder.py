from dataclasses import dataclass

from typing import Any, Optional

from backend.app.reconciliation.normalizer import normalize_reference


@dataclass
class TransactionChain:
    """
    Represents the relationship between:

        Order -> Payment -> Settlement -> Bank

    Chains are allowed to be incomplete.

    The primary settlement/bank are kept in the original fields for
    backwards compatibility. Additional related records are retained
    so exception classification can detect multi-record settlement
    structures without changing the basic chain API.
    """

    order: dict[str, Any]
    payment: Optional[dict[str, Any]]
    settlement: Optional[dict[str, Any]]
    bank: Optional[dict[str, Any]]
    duplicate_bank_transactions: list[dict[str, Any]] | None = None

    # Session 7 multi-record relationship information.
    related_settlements: list[dict[str, Any]] | None = None
    combined_bank_transactions: list[dict[str, Any]] | None = None

    @property
    def order_id(self) -> str:
        return str(self.order["order_id"])

    @property
    def payment_id(self) -> Optional[str]:
        if self.payment is None:
            return None
        return str(self.payment["payment_id"])

    @property
    def settlement_id(self) -> Optional[str]:
        if self.settlement is None:
            return None
        return str(self.settlement["settlement_id"])

    @property
    def bank_transaction_id(self) -> Optional[str]:
        if self.bank is None:
            return None
        return str(self.bank["transaction_id"])


def build_transaction_chains(
    orders: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    banks: list[dict[str, Any]],
) -> list[TransactionChain]:
    """
    Build Order -> Payment -> Settlement -> Bank
    transaction chains using explicit references.

    Chains may be incomplete.

    Multi-settlement and combined-bank relationships are retained
    for exception classification.

    This module does not perform matching, scoring, date-window
    logic, or reconciliation decisions.
    """

    payments_by_order = {
        str(payment["order_id"]): payment
        for payment in payments
    }

    # IMPORTANT:
    # A payment may have multiple settlement records.
    settlements_by_payment: dict[str, list[dict[str, Any]]] = {}

    for settlement in settlements:
        payment_id = str(settlement["payment_id"])

        settlements_by_payment.setdefault(
            payment_id,
            [],
        ).append(settlement)

    banks_by_reference: dict[str, list[dict[str, Any]]] = {}

    for bank in banks:
        normalized_reference = normalize_reference(
            bank["reference"]
        )

        banks_by_reference.setdefault(
            normalized_reference,
            [],
        ).append(bank)

    chains = []

    for order in orders:
        order_id = str(order["order_id"])

        payment = payments_by_order.get(order_id)

        settlement = None
        bank = None
        duplicate_bank_transactions = None
        related_settlements = None
        combined_bank_transactions = None

        if payment is not None:
            payment_id = str(payment["payment_id"])

            related_settlements = settlements_by_payment.get(
                payment_id,
                [],
            )

            if related_settlements:
                # Preserve the original single-settlement API.
                settlement = related_settlements[0]

        if settlement is not None:
            settlement_reference = normalize_reference(
                settlement["settlement_reference"]
            )

            matching_banks = banks_by_reference.get(
                settlement_reference,
                [],
            )

            if matching_banks:
                bank = matching_banks[0]

                if len(matching_banks) > 1:
                    duplicate_bank_transactions = matching_banks

            # -----------------------------------------------------
            # COMBINED SETTLEMENT SUPPORT
            # -----------------------------------------------------
            #
            # The synthetic corruption changes:
            #
            #     SETTXN001
            #
            # into:
            #
            #     COMBINED-SETTXN001-SETTXN002
            #
            # and combines the two bank credits.
            #
            # Retain that bank record in the chain so the exception
            # classifier can identify the multi-payment relationship.
            #
            if bank is None:
                combined_matches = []

                for candidate in banks:
                    if not isinstance(candidate, dict):
                        continue

                    reference = str(
                        candidate.get("reference", "")
                    )

                    if not reference.startswith("COMBINED-"):
                        continue

                    combined_references = [
                        normalize_reference(part)
                        for part in reference.split("-")[1:]
                    ]

                    if settlement_reference in combined_references:
                        combined_matches.append(candidate)

                if combined_matches:
                    bank = combined_matches[0]
                    combined_bank_transactions = combined_matches

        chains.append(
            TransactionChain(
                order=order,
                payment=payment,
                settlement=settlement,
                bank=bank,
                duplicate_bank_transactions=duplicate_bank_transactions,
                related_settlements=related_settlements,
                combined_bank_transactions=combined_bank_transactions,
            )
        )

    return chains
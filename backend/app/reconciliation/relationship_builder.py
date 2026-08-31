from dataclasses import dataclass
from typing import Any, Optional

from backend.app.reconciliation.normalizer import normalize_reference


@dataclass
class TransactionChain:
    """
    Represents the relationship between:
    Order -> Payment -> Settlement -> Bank.

    Chains are allowed to be incomplete.
    This module only constructs relationships.
    It does not perform matching or reconciliation.
    """

    order: dict[str, Any]
    payment: Optional[dict[str, Any]]
    settlement: Optional[dict[str, Any]]
    bank: Optional[dict[str, Any]]

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

    No matching, scoring, date-window logic, or
    reconciliation decision is performed here.
    """

    payments_by_order = {
        str(payment["order_id"]): payment
        for payment in payments
    }

    settlements_by_payment = {
        str(settlement["payment_id"]): settlement
        for settlement in settlements
    }

    banks_by_reference = {}

    for bank in banks:
        normalized_reference = normalize_reference(
            bank["reference"]
        )
        banks_by_reference[normalized_reference] = bank

    chains = []

    for order in orders:
        order_id = str(order["order_id"])

        payment = payments_by_order.get(order_id)
        settlement = None
        bank = None

        if payment is not None:
            payment_id = str(payment["payment_id"])
            settlement = settlements_by_payment.get(payment_id)

        if settlement is not None:
            settlement_reference = normalize_reference(
                settlement["settlement_reference"]
            )
            bank = banks_by_reference.get(settlement_reference)

        chains.append(
            TransactionChain(
                order=order,
                payment=payment,
                settlement=settlement,
                bank=bank,
            )
        )

    return chains

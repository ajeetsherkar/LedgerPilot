from dataclasses import dataclass
from typing import Optional


@dataclass
class ReconciliationResult:
    """
    Represents the final reconciliation result for
    an Order -> Payment -> Settlement -> Bank chain.
    """

    order_id: str

    payment_id: Optional[str]
    settlement_id: Optional[str]
    bank_transaction_id: Optional[str]

    payment_status: str
    settlement_status: str
    bank_status: str

    expected_amount: float
    paid_amount: Optional[float]
    settled_amount: Optional[float]
    bank_amount: Optional[float]

    difference: float
    reconciliation_status: str
    exception_type: Optional[str]
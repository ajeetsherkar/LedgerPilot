from dataclasses import dataclass
from typing import Optional


@dataclass
class ReconciliationResult:
    order_id: str

    payment_status: str
    settlement_status: str
    bank_status: str

    expected_amount: float
    paid_amount: Optional[float]
    settled_amount: Optional[float]
    bank_amount: Optional[float]

    difference: float
    reconciliation_status: str
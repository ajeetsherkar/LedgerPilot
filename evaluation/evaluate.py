from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.reconciliation.pipeline import reconcile_all


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ORDERS_PATH = PROJECT_ROOT / "data" / "dev" / "orders.csv"
PAYMENTS_PATH = PROJECT_ROOT / "data" / "dev" / "payments.csv"
SETTLEMENTS_PATH = PROJECT_ROOT / "data" / "dev" / "settlements.csv"
BANK_PATH = PROJECT_ROOT / "data" / "dev" / "bank.csv"
GROUND_TRUTH_PATH = (
    PROJECT_ROOT
    / "data"
    / "ground_truth"
    / "dev_ground_truth.csv"
)


CHAIN_FIELDS = (
    "order_id",
    "payment_id",
    "settlement_id",
    "bank_transaction_id",
)


def _load_csv(path: Path) -> list[dict[str, Any]]:
    df = pd.read_csv(path)
    return df.where(pd.notna(df), None).to_dict(orient="records")


def _decision_chain(decision: Any) -> tuple[Any, ...]:
    return tuple(
        getattr(decision, field, None)
        for field in CHAIN_FIELDS
    )


def _ground_truth_chain(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(field) for field in CHAIN_FIELDS)


def _is_match_prediction(decision: Any) -> bool:
    return decision.method != "NONE" and any(
        getattr(decision, field, None) is not None
        for field in CHAIN_FIELDS
    )


def evaluate() -> dict[str, Any]:
    orders = _load_csv(ORDERS_PATH)
    payments = _load_csv(PAYMENTS_PATH)
    settlements = _load_csv(SETTLEMENTS_PATH)
    banks = _load_csv(BANK_PATH)

    ground_truth_df = pd.read_csv(GROUND_TRUTH_PATH)

    ground_truth = ground_truth_df.to_dict(orient="records")

    decisions = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
        bank_candidates=banks,
    )

    predictions_by_order = {
        decision.order_id: decision
        for decision in decisions
        if decision.order_id is not None
    }

    correct_matches = 0
    predicted_matches = 0

    auto_resolved_total = 0
    auto_resolved_correct = 0

    for truth in ground_truth:
        decision = predictions_by_order.get(truth["order_id"])

        if decision is None:
            continue

        predicted = _is_match_prediction(decision)

        if predicted:
            predicted_matches += 1

        correct = (
            predicted
            and _decision_chain(decision)
            == _ground_truth_chain(truth)
        )

        if correct:
            correct_matches += 1

        if decision.status == "AUTO_RESOLVED":
            auto_resolved_total += 1
            if correct:
                auto_resolved_correct += 1

    total_ground_truth = len(ground_truth)

    match_rate = (
        correct_matches / total_ground_truth
        if total_ground_truth
        else 0.0
    )

    precision = (
        correct_matches / predicted_matches
        if predicted_matches
        else 0.0
    )

    recall = (
        correct_matches / total_ground_truth
        if total_ground_truth
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    auto_resolution_precision = (
        auto_resolved_correct / auto_resolved_total
        if auto_resolved_total
        else 0.0
    )

    return {
        "total_ground_truth": total_ground_truth,
        "predicted_matches": predicted_matches,
        "correct_matches": correct_matches,
        "match_rate": match_rate,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auto_resolved_total": auto_resolved_total,
        "auto_resolved_correct": auto_resolved_correct,
        "auto_resolution_precision": auto_resolution_precision,
    }


if __name__ == "__main__":
    metrics = evaluate()

    print("LedgerPilot Evaluation")
    print("=" * 40)

    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

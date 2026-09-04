from __future__ import annotations

import sys
import time
from pathlib import Path
from statistics import median
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_data import generate_dataset
from backend.app.reconciliation.pipeline import reconcile_all


BENCHMARK_SIZES = (250, 500, 1000)
RUNS = 3


def run_once(n: int, seed: int) -> tuple[float, int]:
    orders, payments, settlements, banks = generate_dataset(
        n,
        seed=seed,
        id_prefix=f"BENCH{n}_",
    )

    start = time.perf_counter()

    decisions = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
        bank_candidates=banks,
    )

    elapsed = time.perf_counter() - start

    return elapsed, len(decisions)


def benchmark() -> list[dict[str, Any]]:
    results = []

    for n in BENCHMARK_SIZES:
        timings = []

        # Warm-up run so the measured runs are less affected by
        # first-use/import/runtime startup effects.
        run_once(n, seed=9000 + n)

        for run in range(RUNS):
            elapsed, decision_count = run_once(
                n,
                seed=10000 + n + run,
            )
            timings.append(elapsed)

        elapsed = median(timings)
        records_per_second = n / elapsed

        results.append(
            {
                "records": n,
                "runs": RUNS,
                "median_seconds": elapsed,
                "records_per_second": records_per_second,
                "decisions": decision_count,
            }
        )

    return results


def main() -> None:
    results = benchmark()

    print()
    print("=" * 78)
    print("LEDGERPILOT THROUGHPUT BENCHMARK")
    print("=" * 78)
    print("Pipeline: in-memory generate_dataset -> reconcile_all")
    print(f"Measured runs per size: {RUNS}")
    print("Reported timing: median of measured runs")
    print()
    print(
        f"{'Records':>10} {'Time (s)':>14} "
        f"{'Records/sec':>16} {'Decisions':>12}"
    )
    print("-" * 78)

    for result in results:
        print(
            f"{result['records']:>10} "
            f"{result['median_seconds']:>14.6f} "
            f"{result['records_per_second']:>16.2f} "
            f"{result['decisions']:>12}"
        )

    print("=" * 78)


if __name__ == "__main__":
    main()

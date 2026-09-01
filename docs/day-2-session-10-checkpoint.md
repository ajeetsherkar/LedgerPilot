# Day 2 — Session 10 Checkpoint

## Non-AI Reconciliation Baseline

Session 10 validates the complete reconciliation pipeline on a
350-record development dataset.

### Pipeline

Orders
→ Payments
→ Settlements
→ Normalization
→ Exact Matching
→ Fee-Aware Matching
→ Date-Window Matching
→ Candidate Generation
→ Similarity Scoring
→ Match Decision

## 350-Record End-to-End Validation

- Orders: 350
- Payments: 350
- Settlements: 350
- Bank candidate records: 350
- Transaction chains: 350
- Decisions: 350

For the true fallback validation, directly linked bank records
were excluded from the transaction chains and the 350 bank records
were supplied as candidate records.

### Similarity Fallback Results

- Similarity decisions: 350
- MATCH: 266
- REVIEW: 84
- UNRESOLVED: 0
- Similarity automatic match rate: 76.00%

### Before-AI Baseline

**76.00% automatic match rate**

This represents the pre-AI baseline for subsequent benchmarking.

The 84 REVIEW decisions are retained for manual review rather than
being automatically matched. No records were left UNRESOLVED in
this 350-record fallback run.

## Validation Status

- 350-record pipeline execution: PASS
- Candidate generation: PASS
- Similarity scoring: PASS
- Similarity fallback: PASS
- Automatic MATCH decisions: 266
- REVIEW decisions: 84
- UNRESOLVED decisions: 0
- Full pytest suite: 200 tests passed

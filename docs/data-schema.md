# LedgerPilot Data Schema

## 1. Purpose

This document defines the canonical data contract for LedgerPilot.

LedgerPilot reconciles four financial data sources:

1. Orders
2. Payments
3. Settlements
4. Bank Transactions

The schema is designed to support:

- Multi-source reconciliation
- Fee-aware matching
- Candidate scoring
- Confidence-gated decisions
- Exception classification
- Human review
- Audit trails
- Ground-truth evaluation
- Precision, recall, and match-rate metrics

---

# 2. Entity Relationships

```text
Order
  |
  | order_id
  v
Payment
  |
  | payment_id / order_id
  v
Settlement
  |
  | settlement_id
  v
Bank Transaction

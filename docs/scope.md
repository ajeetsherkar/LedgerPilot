# LedgerPilot — Project Scope

## Project
LedgerPilot v0.1 — Payment Reconciliation Engine

## Domain
Indian digital payments

## Currency
INR

## Input Sources

LedgerPilot reconciles data from four input sources:

1. Orders
2. Payments
3. Settlements
4. Bank

## Transaction Relationship

The core transaction chain is:

Order → Payment → Settlement → Bank

Each transaction chain should be uniquely traceable across these four sources.

## Reconciliation Outcomes

The reconciliation system produces three possible outcomes:

1. Auto-resolved
2. AI-suggested
3. Human-review

## Scope Boundary

The Day 1 synthetic financial world is limited to Indian digital-payment
reconciliation using INR-denominated transactions and the four defined
input sources.

The underlying ground truth is known during dataset generation and is
kept separate from the reconciliation engine so that later evaluation
can objectively measure correctness.

## Out of Scope

The following are outside the current LedgerPilot v0.1 scope:

- Non-INR currencies
- Non-Indian payment domains
- Additional financial data sources outside the four defined inputs
- Production banking integrations
- Live payment processing
- Real customer financial data

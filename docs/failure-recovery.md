# Failure Recovery Story — ORD0346

## Real DEV failure case

This case is taken from the frozen DEV failure analysis and reproduced against
the historical pipeline immediately before the ambiguity-gate fix.

**Order:** `ORD0346`

**Ground-truth chain:**

- Order: `ORD0346`
- Payment: `PAY0346`
- Settlement: `SET0346`
- Bank transaction: `BTX0346`

The DEV failure analysis classified this record as `AMBIGUOUS_MATCH`.

## What the system did before the fix

The historical pipeline was reproduced from commit `370ff92^` using the same
DEV source records.

For `ORD0346`, the similarity scorer produced two top bank candidates with
exactly the same score:

| Rank | Bank candidate | Score |
|---|---|---:|
| 1 | `BTX0171` | `0.696791` |
| 2 | `BTX0171_DUP` | `0.696791` |
| 3 | `BTX0019` | `0.658224` |

The score gap between the first and second candidates was therefore:

`0.696791 - 0.696791 = 0.000000`

The pre-fix pipeline returned:

- Status: `REVIEW`
- Method: `SIMILARITY`
- Confidence: `0.696791`
- Bank transaction ID in the final decision: `None`

The important failure was not an unsafe automatic resolution. The historical
pipeline did not auto-resolve this record. The failure was that the candidate
selection logic still had a preferred top candidate despite an exact score tie,
creating a situation in which the system could appear to have a "best" match
when the evidence did not distinguish the candidates.

The ground truth was `BTX0346`, not either of the tied top candidates.

## How evaluation surfaced the problem

The DEV evaluation compares the complete predicted transaction chain against
the ground-truth chain.

`ORD0346` was one of the ten DEV records classified as `AMBIGUOUS_MATCH` in
the failure analysis.

The failure analysis showed that the record contained competing bank
candidates whose similarity scores were too close to justify choosing one.

This made the case useful as a concrete failure-recovery example: the system
needed an explicit rule for refusing to guess when candidate evidence was
effectively tied.

The held-out evaluation remained frozen and was not used to discover or tune
this case. The failure investigation was performed on the DEV set.

## Exactly what changed

The fix was introduced in commit `370ff92`:

`feat: top-vs-second-candidate ambiguity gate (refuse to guess on close calls)`

The decision engine now calculates the difference between the highest and
second-highest candidate scores.

The configured minimum score margin is:

`MIN_SCORE_MARGIN = 0.05`

The ambiguity rule is:

- If there is more than one candidate, and
- the top-vs-second score gap is less than `0.05`,
- the system marks the result as ambiguous and sends it to review.

For `ORD0346`:

`score gap = 0.000000 < 0.05`

Therefore the system refuses to guess.

An important historical detail is that the numeric value `0.05` already
existed in the earlier configuration. The substantive change was the explicit
enforcement of that margin as a top-vs-second-candidate ambiguity gate.

## Corrected behavior after the fix

Running `ORD0346` through the current frozen pipeline produces:

- Status: `HUMAN_REVIEW`
- Method: `SIMILARITY`
- Confidence: `0.0`
- Selected bank transaction: `None`

The reason explicitly states that the top two bank candidates are below the
configured ambiguity margin and that the system refuses to guess.

The current decision also records deterministic verification failures for the
proposed candidate, so the case remains with a human instead of being
silently resolved.

The ground truth remains:

`BTX0346`

## Before → after demo script

**Before:**

> "For order ORD0346, the similarity model sees BTX0171 and BTX0171_DUP as
> equally strong candidates. Their scores are both 0.696791, so the gap is
> zero. The old pipeline could still identify a preferred top candidate
> internally, even though there was no evidence separating the two."

**Failure discovered:**

> "DEV failure analysis exposed this as an ambiguous-match scenario. The
> correct bank transaction is BTX0346, while the two highest-scoring
> candidates are tied and incorrect."

**Fix:**

> "We added an explicit top-vs-second-candidate ambiguity gate. If the score
> gap is below 0.05, the system refuses to guess and routes the case to human
> review."

**After:**

> "The same ORD0346 record now produces HUMAN_REVIEW with no selected bank
> transaction. The system explicitly says it refuses to guess. This converts
> an ambiguous candidate-selection situation into a controlled human-review
> outcome."

## Why this matters

The lesson is not simply that similarity scoring can be wrong. The important
controller behavior is that **close evidence must not be treated as confident
evidence**.

The reconciliation controller therefore uses a conservative rule:

> When the evidence does not clearly distinguish the top candidates, do not
> guess.

That rule makes the system safer for financial reconciliation because an
ambiguous transaction is surfaced for review instead of being silently
assigned to an arbitrary candidate.

# LedgerPilot

## AI Settlement Reconciliation Controller

> **Reconcile the money. Explain the exceptions. Automate only what you can verify.**

LedgerPilot is an AI-assisted financial reconciliation system that reconciles **orders, payments, settlements, and bank transactions** while keeping financial decisions deterministic, explainable, and reviewable.

The system uses deterministic matching and verification for evidence that can be checked reliably. Ambiguous cases are isolated behind a structured AI reasoning boundary and can be escalated to human review instead of being silently resolved.

---

## 🚀 Live Demo

### Frontend
**https://ledgerpilot-frontend.onrender.com**

### Backend API
**https://ledgerpilot-backend.onrender.com**

### API Health
- `/health`
- `/api/health`

---

# 1. Problem Statement

Financial reconciliation requires matching records that originate from different systems:

- Orders
- Payments
- Settlements
- Bank transactions

These records may contain different:

- references
- dates
- amounts
- fees
- currencies
- transaction identifiers

A naive reconciliation system may simply select the "best" candidate even when the evidence is ambiguous.

In a financial workflow, **silently guessing is dangerous**.

LedgerPilot addresses this by combining:

1. Deterministic matching
2. Candidate generation
3. Explainable similarity scoring
4. Confidence-based decisions
5. An explicit ambiguity gate
6. Deterministic verification
7. Structured AI reasoning for ambiguous cases
8. Exception classification
9. Human review
10. Frozen held-out evaluation

---

# 2. Core Principle

LedgerPilot follows a simple rule:

> **When the evidence is strong, automate. When the evidence is ambiguous, explain and escalate. Never let confidence replace verification.**

The system is designed to **refuse to guess** when competing evidence is too close.

---

# 3. Architecture

```mermaid
flowchart TD

    U[User] --> F[Streamlit Frontend]

    F --> API[FastAPI Backend]

    API --> ING[Input Validation & Ingestion]
    ING --> N[Normalization]
    N --> R[Relationship Builder]

    R --> M[Matching Engine]

    M --> E[Exact Matching]
    M --> FW[Fee-Aware Matching]
    M --> DW[Date-Window Matching]
    M --> CG[Candidate Generation]
    M --> SS[Similarity Scoring]

    E --> DE[Decision Engine]
    FW --> DE
    DW --> DE
    SS --> DE

    DE --> V[Deterministic Verification]

    V -->|Verified| AR[AUTO_RESOLVED]
    V -->|Ambiguous| AI[AI Reasoning Boundary]
    V -->|Unsafe / Failed| HR[HUMAN_REVIEW]

    AI --> AIS[AI_SUGGESTED]
    AI --> HR

    AR --> DB[(PostgreSQL)]
    AIS --> DB
    HR --> DB

    HR --> REV[Human Review]
    REV --> DB

    API --> DB
    API --> F

    EVAL[Held-Out Evaluation] --> MET[Evaluation Metrics]
```

### Production Architecture

```text
                 ┌─────────────────────┐
                 │       Browser       │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Streamlit Frontend  │
                 └──────────┬──────────┘
                            │
                  Server-side requests
                            │
                            ▼
                 ┌─────────────────────┐
                 │   FastAPI Backend   │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │     PostgreSQL      │
                 └─────────────────────┘
```

The Streamlit frontend communicates with FastAPI through server-side Python requests. The browser does not directly communicate with the API, so browser CORS middleware is not required by the current architecture.

---

# 4. End-to-End Workflow

```text
CSV Upload
    ↓
Input Validation
    ↓
Ingestion
    ↓
Normalization
    ↓
Relationship Building
    ↓
Candidate Generation
    ↓
Matching
    ↓
Confidence Classification
    ↓
Ambiguity Gate
    ↓
Deterministic Verification
    ↓
Decision
    ├── AUTO_RESOLVED
    ├── AI_SUGGESTED
    └── HUMAN_REVIEW
```

### Step 1 — Upload

The user uploads four CSV files:

* Orders
* Payments
* Settlements
* Bank transactions

### Step 2 — Validate & Ingest

The backend validates the source files and creates a reconciliation batch.

### Step 3 — Normalize

Identifiers, amounts, dates, currencies, and references are normalized before comparison.

### Step 4 — Build Relationships

Relationships between orders, payments, settlements, and bank records are constructed.

### Step 5 — Generate Candidates

Potential bank candidates are generated for each transaction.

### Step 6 — Match

The system applies multiple matching strategies:

* Exact matching
* Fee-aware matching
* Date-window matching
* Similarity scoring

### Step 7 — Decide

The decision engine classifies the result according to controlled confidence and ambiguity policies.

### Step 8 — Verify

Before automatic resolution, the system performs deterministic verification.

### Step 9 — Escalate

Ambiguous or unsafe cases are routed to human review.

### Step 10 — Human Review

A reviewer can inspect the evidence and approve or reject the reconciliation decision.

---

# 5. Why AI Is Used — And Where It Is Not

## Why AI?

AI is useful when deterministic evidence is ambiguous.

For example, multiple bank transactions may look similarly relevant to the same order. Instead of blindly choosing one, LedgerPilot can use a structured AI reasoning interface to help classify and explain the ambiguous situation.

The AI response contract contains:

```text
classification
recommended_action
reason
confidence
```

The response is schema-validated rather than accepting arbitrary model output.

---

## Where AI Is NOT Used

AI is deliberately not responsible for:

* changing transaction amounts
* bypassing deterministic verification
* bypassing uniqueness checks
* replacing the matching engine
* turning financially inconsistent evidence into a valid match
* replacing human approval

The financial authority remains deterministic verification.

```text
Deterministic Evidence
        ↓
Deterministic Verification
        ↓
Controlled Decision
        ↓
Human Escalation when necessary
```

---

## Current AI Integration Status

The repository contains:

* structured AI reasoning schema
* AI service boundary
* AI response validation
* decision integration
* frontend AI reasoning display

The current production reconciliation runs used for deployment verification produced:

```text
AI_SUGGESTED = 0
```

No external LLM provider is required for the current deterministic reconciliation pipeline.

This is intentional: the core financial reconciliation process remains reproducible and does not depend on an external LLM being available.

The AI layer is designed as a controlled boundary that can support provider integration without allowing AI output to bypass deterministic financial controls.

---

# 6. Dataset

LedgerPilot uses a controlled synthetic reconciliation dataset.

```text
Total chains: 500
```

The dataset is explicitly divided into:

| Split    | Records | Purpose                                      |
| -------- | ------: | -------------------------------------------- |
| DEV      |     350 | Development, debugging, and failure analysis |
| HELD-OUT |     150 | Frozen final evaluation                      |

Each transaction chain represents:

```text
Order
  ↓
Payment
  ↓
Settlement
  ↓
Bank Transaction
```

The dataset contains controlled normal and exception scenarios designed to test the reconciliation pipeline.

---

# 7. Ground Truth Methodology

Each synthetic transaction chain has a known correct relationship across the four source systems.

For example:

```text
Order:       ORD0001
     ↓
Payment:     PAY0001
     ↓
Settlement:  SET0001
     ↓
Bank:        BTX0001
```

The ground-truth mappings are stored separately from the reconciliation decision logic.

This allows the evaluation system to compare the **complete predicted transaction chain** against the expected ground-truth chain.

---

# 8. DEV vs HELD-OUT Evaluation

LedgerPilot maintains a strict separation between development and evaluation data.

### DEV

The DEV dataset is used for:

* development
* debugging
* failure analysis
* identifying edge cases
* validating fixes

### HELD-OUT

The held-out dataset is frozen and used for final evaluation.

The held-out dataset was not used to discover or tune the ambiguity failure described in the failure-recovery story.

This separation helps prevent the final reported metrics from being tuned against the evaluation examples.

---

# 9. Evaluation Methodology

The frozen evaluation artifact is:

```text
evaluation/results/held_out_metrics.json
```

The held-out evaluation contains:

```text
Total ground truth: 150
Predicted matches:  138
Correct matches:    130
```

## Metrics

### Match Rate

The proportion of ground-truth transactions for which a correct predicted match was recovered.

```text
130 / 150 = 86.67%
```

### Precision

The proportion of predicted matches that were correct.

```text
130 / 138 = 94.20%
```

### Recall

The proportion of ground-truth matches successfully recovered.

```text
130 / 150 = 86.67%
```

### F1 Score

The harmonic mean of precision and recall.

```text
90.28%
```

### Auto-Resolution Precision

The proportion of automatically resolved transactions that were correct.

```text
123 / 123 = 100.00%
```

---

# 10. Frozen Held-Out Results

| Metric                    |      Result |
| ------------------------- | ----------: |
| Total ground truth        |         150 |
| Predicted matches         |         138 |
| Correct matches           |         130 |
| Match rate                |  **86.67%** |
| Precision                 |  **94.20%** |
| Recall                    |  **86.67%** |
| F1                        |  **90.28%** |
| Auto-resolved total       |         123 |
| Auto-resolved correct     |         123 |
| Auto-resolution precision | **100.00%** |

These values are taken directly from the committed frozen evaluation artifact.

---

# 11. Decision States

LedgerPilot uses controlled decision states:

| State           | Meaning                                                      |
| --------------- | ------------------------------------------------------------ |
| `AUTO_RESOLVED` | High-confidence result passed deterministic verification     |
| `AI_SUGGESTED`  | Structured AI reasoning is available for an ambiguous case   |
| `HUMAN_REVIEW`  | System refuses to make an unsafe or ambiguous final decision |
| `UNRESOLVED`    | Safe terminal state for failed or malformed processing paths |

The critical safety boundary is:

```text
AUTO_RESOLVED
      ↓
Deterministic Verification
      ↓
Only then is the result accepted
```

---

# 12. Deterministic Verification

Before a transaction can become `AUTO_RESOLVED`, the verification layer checks:

* Amount
* Fee
* Date
* Currency
* Reference
* Uniqueness

Therefore:

> **A high similarity score alone is never sufficient for automatic financial resolution.**

The same deterministic verification principle is applied before an AI-proposed match can influence the workflow.

---

# 13. Ambiguity Gate

One of LedgerPilot's key safety controls is the **top-vs-second-candidate ambiguity gate**.

The configured minimum score margin is:

```text
MIN_SCORE_MARGIN = 0.05
```

If multiple candidates exist and the score difference between the highest and second-highest candidates is below `0.05`, the system refuses to guess.

```text
top_score - second_score < 0.05
                ↓
        AMBIGUOUS_MATCH
                ↓
         HUMAN_REVIEW
```

This prevents a candidate from being treated as confidently correct merely because it ranked first by a very small margin.

---

# 14. Real Failure Found and Fixed

A concrete DEV failure was identified for:

```text
ORD0346
```

The historical pipeline produced:

| Rank | Bank Candidate |    Score |
| ---- | -------------- | -------: |
| 1    | `BTX0171`      | 0.696791 |
| 2    | `BTX0171_DUP`  | 0.696791 |
| 3    | `BTX0019`      | 0.658224 |

The top two candidates had exactly the same score:

```text
0.696791 - 0.696791 = 0.000000
```

However, the correct ground-truth bank transaction was:

```text
BTX0346
```

---

## What was wrong?

The historical pipeline did not automatically resolve this record.

However, the candidate-selection logic could still appear to prefer one of the tied candidates even though there was no evidence separating them.

That created a dangerous situation:

> A candidate could look like the "best" candidate even when the evidence could not distinguish it from another candidate.

---

## How the Problem Was Found

The failure was discovered during DEV failure analysis.

The held-out evaluation remained frozen.

The investigation therefore did not tune the system against the final evaluation set.

---

## The Fix

The decision engine was changed to explicitly enforce the top-vs-second-candidate ambiguity margin.

Configured threshold:

```text
MIN_SCORE_MARGIN = 0.05
```

For `ORD0346`:

```text
score gap = 0.000000
threshold  = 0.05

0.000000 < 0.05
```

Therefore:

```text
REFUSE TO GUESS
        ↓
HUMAN_REVIEW
```

---

## Corrected Behavior

The current frozen pipeline produces:

```text
Status:              HUMAN_REVIEW
Method:              SIMILARITY
Confidence:          0.0
Selected bank:       None
```

Instead of silently choosing one of the tied candidates, LedgerPilot explicitly escalates the transaction.

The complete failure-recovery story is available in:

```text
docs/failure-recovery.md
```

---

# 15. Exception Taxonomy

LedgerPilot classifies reconciliation exceptions into controlled categories:

1. `MISSING_BANK_RECORD`
2. `AMOUNT_MISMATCH`
3. `DUPLICATE_BANK_TRANSACTION`
4. `UNKNOWN_REFERENCE`
5. `AMBIGUOUS_MATCH`
6. `PARTIAL_SETTLEMENT`
7. `COMBINED_SETTLEMENT`
8. `DATE_MISMATCH`
9. `MISSING_PAYMENT`
10. `MISSING_SETTLEMENT`

This makes exceptions searchable, filterable, and explainable.

---

# 16. Human Review

Human review is a first-class workflow.

For a `HUMAN_REVIEW` transaction, the reviewer can:

* inspect the evidence chain
* inspect deterministic verification
* inspect the decision explanation
* inspect candidate information
* approve the decision
* reject the decision

Review records persist:

```text
reviewer
reason
reviewed_at
final_decision
```

The review state is persisted in PostgreSQL.

Therefore, an approval or rejection remains visible after refreshing the application.

---

# 17. Explainability

The Transaction Detail screen provides a complete evidence chain.

```text
Order
  ↓
Payment
  ↓
Settlement
  ↓
Bank Transaction
```

It also provides a verification checklist:

```text
✓ Amount
✓ Fee
✓ Date
✓ Currency
✓ Reference
✓ Uniqueness
```

The UI explains why a transaction became:

* `AUTO_RESOLVED`
* `AI_SUGGESTED`
* `HUMAN_REVIEW`

For ambiguous cases, the interface can also expose:

* top candidates
* score margin
* configured ambiguity threshold
* escalation policy

---

# 18. Application Screens

The frontend intentionally contains exactly four screens.

## 1. Upload

Upload:

* Orders CSV
* Payments CSV
* Settlements CSV
* Bank CSV

Then run reconciliation.

---

## 2. Dashboard

Displays:

* total records
* auto-resolved count
* AI-suggested count
* human-review count
* match rate
* precision
* recall
* F1
* auto-resolution precision

---

## 3. Exceptions

Provides a filterable table of reconciliation exceptions.

---

## 4. Transaction Detail

Provides:

* evidence chain
* verification results
* decision explanation
* candidate information
* AI reasoning where applicable
* human review actions

---

# 19. Deployment

LedgerPilot is deployed using Docker on Render.

## Frontend

```text
https://ledgerpilot-frontend.onrender.com
```

## Backend

```text
https://ledgerpilot-backend.onrender.com
```

## Database

Production persistence uses PostgreSQL.

The architecture is:

```text
Streamlit
    ↓
FastAPI
    ↓
PostgreSQL
```

The browser does not connect directly to PostgreSQL.

---

# 20. Deployment Issue Found and Fixed

During the first deployment verification, the Dashboard could not initially access the held-out evaluation metrics.

## Cause

The frontend Docker image did not contain the `evaluation/` directory because it was excluded by the Docker ignore configuration.

## Fix

The frontend Dockerfile was changed to include:

```dockerfile
COPY evaluation ./evaluation
```

The evaluation directory was also removed from the Docker ignore rules.

After redeployment, the production Dashboard correctly displayed:

```text
Match rate:                 86.67%
Precision:                  94.20%
Recall:                     86.67%
F1:                         90.28%
Auto-resolution precision: 100.00%
```

---

## Render Cold Start

A separate infrastructure behavior was observed during deployment testing.

Render's free-tier service can sleep when idle.

The first request after sleeping required more than 50 seconds while the backend instance woke up.

This was confirmed as infrastructure cold-start behavior rather than a reconciliation-code failure.

After the service became active, the production workflow worked normally.

---

# 21. Local Development

## Requirements

* Python 3.11+
* PostgreSQL
* Docker
* Docker Compose

---

## Clone

```bash
git clone https://github.com/ajeetsherkar/LedgerPilot.git
cd LedgerPilot
```

---

## Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Configuration

Create a local `.env` based on:

```text
.env.example
```

Example local database configuration:

```text
DATABASE_URL=postgresql://ledgerpilot:ledgerpilot_dev@localhost:5432/ledgerpilot
```

Never commit `.env` or secret values.

---

# 22. Start PostgreSQL

```bash
docker compose up -d postgres
```

Local PostgreSQL configuration:

```text
Database: ledgerpilot
User:     ledgerpilot
Password: ledgerpilot_dev
Port:     5432
```

---

# 23. Start Backend

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Health endpoints:

```text
http://localhost:8000/health
http://localhost:8000/api/health
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

---

# 24. Start Frontend

In another terminal:

```bash
streamlit run frontend/app.py
```

The application normally runs at:

```text
http://localhost:8501
```

---

# 25. Docker

Build the backend:

```bash
docker build -f backend/Dockerfile -t ledgerpilot-backend .
```

Build the frontend:

```bash
docker build -f frontend/Dockerfile -t ledgerpilot-frontend .
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

The Docker configuration supports independent backend and frontend containers with PostgreSQL as the persistent database.

---

# 26. API Overview

```text
GET  /health
GET  /api/health

POST /upload

POST /reconciliation/run
GET  /reconciliation/{batch_id}

GET  /reconciliation/{batch_id}/reviews
GET  /reconciliation/{batch_id}/reviews/{review_id}

POST /reconciliation/{batch_id}/reviews/{review_id}/approve
POST /reconciliation/{batch_id}/reviews/{review_id}/reject

GET  /results
GET  /results/{result_id}

GET  /exceptions
GET  /metrics
```

---

# 27. Project Structure

```text
LedgerPilot/
│
├── backend/
│   ├── Dockerfile
│   └── app/
│       ├── main.py
│       ├── database.py
│       └── reconciliation/
│           ├── ai_schema.py
│           ├── ai_service.py
│           ├── batch_loader.py
│           ├── candidate_generator.py
│           ├── confidence.py
│           ├── date_window_matcher.py
│           ├── decision_engine.py
│           ├── decision_status.py
│           ├── engine.py
│           ├── exact_matcher.py
│           ├── exception_classifier.py
│           ├── exception_types.py
│           ├── fee_aware_matcher.py
│           ├── human_review.py
│           ├── ingestion.py
│           ├── input_validator.py
│           ├── models.py
│           ├── normalizer.py
│           ├── persistence.py
│           ├── pipeline.py
│           ├── relationship_builder.py
│           ├── similarity_scorer.py
│           └── verification.py
│
├── frontend/
│   ├── Dockerfile
│   └── app.py
│
├── data/
│   ├── dev/
│   ├── heldout/
│   └── ground_truth/
│
├── docs/
│   ├── data-schema.md
│   ├── failure-recovery.md
│   └── scope.md
│
├── evaluation/
│   ├── evaluate.py
│   └── results/
│       └── held_out_metrics.json
│
├── tests/
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

# 28. Testing

The project contains automated tests covering:

* API routes
* ingestion
* input validation
* normalization
* relationship building
* exact matching
* fee-aware matching
* date-window matching
* candidate generation
* similarity scoring
* confidence classification
* decision engine
* exception classification
* deterministic verification
* AI schema/service behavior
* human review
* reconciliation pipeline

Run the complete test suite:

```bash
pytest -q
```

Final project verification:

```text
308 passed
```

---

# 29. Reproducibility

The project separates development data from evaluation data.

The frozen evaluation artifact is:

```text
evaluation/results/held_out_metrics.json
```

The reported metrics are therefore stored as a repository artifact rather than manually entered into the frontend.

This allows reviewers to inspect the exact evaluation values used by the project.

---

# 30. Key Differentiators

## 1. AI is not the financial authority

AI is isolated behind deterministic financial controls.

## 2. The system can refuse to guess

Close candidate scores trigger an explicit ambiguity gate.

## 3. Automatic resolution requires verification

A high similarity score alone cannot produce an automatic financial resolution.

## 4. Human review is integrated

Reviewers can approve or reject cases and the decision is persisted.

## 5. Full evidence chain

The application connects:

```text
Order
  ↓
Payment
  ↓
Settlement
  ↓
Bank Transaction
```

## 6. Explainable decisions

The UI explains why a transaction was automatically resolved or escalated.

## 7. Frozen held-out evaluation

Development and evaluation data are separated.

## 8. Real failure-recovery story

The project documents a concrete ambiguity failure, the root cause, the fix, and the corrected behavior.

---

# 31. Limitations

* The dataset is synthetic and controlled rather than production bank data.
* The reported evaluation reflects the frozen project dataset.
* The current Render deployment uses the free tier and may experience cold-start latency.
* The AI provider integration is kept behind a structured boundary and is not required by the deterministic reconciliation pipeline.
* Production-scale authentication, authorization, audit logging, enterprise security, and large-scale throughput would require additional engineering.

---

# 32. Project Status

LedgerPilot currently includes:

* ✅ Multi-source financial reconciliation
* ✅ Deterministic matching
* ✅ Fee-aware matching
* ✅ Date-window matching
* ✅ Candidate generation
* ✅ Similarity scoring
* ✅ Confidence-based decisions
* ✅ Ambiguity gate
* ✅ Deterministic verification
* ✅ Structured AI reasoning interface
* ✅ Exception classification
* ✅ Human review
* ✅ PostgreSQL persistence
* ✅ FastAPI backend
* ✅ Streamlit frontend
* ✅ Docker deployment
* ✅ Production deployment
* ✅ Held-out evaluation
* ✅ Failure-recovery documentation
* ✅ End-to-end production verification
* ✅ 308 automated tests

---

# 33. Final Principle

> **When the evidence is strong, automate.
> When the evidence is ambiguous, explain and escalate.
> Never let confidence replace verification.**
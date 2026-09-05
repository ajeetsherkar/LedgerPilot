from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

import pandas as pd
from psycopg.rows import dict_row

from backend.app.database import (
    get_connection,
    initialize_database,
)
from backend.app.reconciliation.batch_loader import load_batch
from backend.app.reconciliation.pipeline import reconcile_all
from backend.app.reconciliation.ingestion import ingest_csv_files
from backend.app.reconciliation.persistence import (
    persist_source_records,
    persist_decisions,
)
from backend.app.reconciliation.human_review import (
    create_or_get_review,
    get_review,
    list_reviews,
    resolve_review,
)

from backend.app.reconciliation.candidate_generator import (
    generate_candidates,
)

from backend.app.reconciliation.similarity_scorer import (
    score_candidates,
)

from backend.app.reconciliation.decision_engine import (
    select_best_candidate,
)

from backend.app.reconciliation.verification import (
    verify_match,
)


class ReviewResolutionRequest(BaseModel):
    reviewer: str
    reason: str


class ReconciliationRunRequest(BaseModel):
    batch_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="LedgerPilot",
    description="AI-assisted financial reconciliation and settlement controller",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "LedgerPilot",
    }


@app.post("/upload")
def upload_csv_files(
    orders: UploadFile = File(...),
    payments: UploadFile = File(...),
    settlements: UploadFile = File(...),
    bank: UploadFile = File(...),
):
    try:
        result = ingest_csv_files(
            orders_file=orders,
            payments_file=payments,
            settlements_file=settlements,
            bank_file=bank,
        )
    except (ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid reconciliation input: {exc}",
        ) from None

    return {
        "status": "success",
        **result,
    }


@app.post("/reconciliation/run")
def run_reconciliation(request: ReconciliationRunRequest):
    batch_id = request.batch_id

    connection = get_connection()
    try:
        existing_total = connection.execute(
            """
            SELECT COUNT(*)
            FROM reconciliation_results
            WHERE batch_id = %s
            """,
            (batch_id,),
        ).fetchone()[0]

        if existing_total > 0:
            rows = connection.execute(
                """
                SELECT status, COUNT(*)
                FROM reconciliation_results
                WHERE batch_id = %s
                GROUP BY status
                """,
                (batch_id,),
            ).fetchall()

            status_counts = dict(rows)

            return {
                "batch_id": batch_id,
                "total": existing_total,
                "auto_resolved": status_counts.get(
                    "AUTO_RESOLVED",
                    0,
                ),
                "ai_suggested": status_counts.get(
                    "AI_SUGGESTED",
                    0,
                ),
                "human_review": status_counts.get(
                    "HUMAN_REVIEW",
                    0,
                ),
            }
    finally:
        connection.close()

    try:
        (
            orders,
            payments,
            settlements,
            banks,
        ) = load_batch(batch_id)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Batch not found or could not be loaded: {batch_id}",
        ) from exc

    persist_source_records(
        batch_id=batch_id,
        orders=orders,
        payments=payments,
        settlements=settlements,
        banks=banks,
    )

    results = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
        bank_candidates=banks,
    )

    persist_decisions(
        batch_id=batch_id,
        decisions=results,
    )

    return {
        "batch_id": batch_id,
        "total": len(results),
        "auto_resolved": sum(
            result.status == "AUTO_RESOLVED"
            for result in results
        ),
        "ai_suggested": sum(
            result.status == "AI_SUGGESTED"
            for result in results
        ),
        "human_review": sum(
            result.status == "HUMAN_REVIEW"
            for result in results
        ),
    }


@app.get("/results")
def get_results():
    connection = get_connection()
    try:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    result_id,
                    batch_id,
                    order_id,
                    payment_id,
                    settlement_id,
                    bank_transaction_id,
                    status,
                    method,
                    confidence::double precision AS confidence,
                    confidence_bucket,
                    reason,
                    candidate,
                    ai_reasoning,
                    exception_type,
                    created_at
                FROM reconciliation_results
                ORDER BY created_at DESC, result_id DESC
                """
            )
            results = [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()

    return {
        "total": len(results),
        "results": results,
    }


@app.get("/results/{result_id}")
def get_result(result_id: str):
    connection = get_connection()

    try:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    r.result_id,
                    r.batch_id,
                    r.order_id,
                    r.payment_id,
                    r.settlement_id,
                    r.bank_transaction_id,
                    r.status,
                    r.method,
                    r.confidence::double precision AS confidence,
                    r.confidence_bucket,
                    r.reason,
                    r.candidate,
                    r.ai_reasoning,
                    r.exception_type,
                    r.created_at,

                    o.order_amount::double precision AS order_amount,
                    o.currency AS order_currency,
                    o.order_date,
                    o.merchant_id,
                    o.customer_id,
                    o.customer_name,
                    o.status AS order_status,

                    p.amount::double precision AS payment_amount,
                    p.currency AS payment_currency,
                    p.payment_date,
                    p.payment_method,
                    p.upi_ref,
                    p.status AS payment_status,

                    s.gross_amount::double precision AS settlement_gross_amount,
                    s.platform_fee::double precision AS settlement_platform_fee,
                    s.gst_on_fee::double precision AS settlement_gst_on_fee,
                    s.net_amount::double precision AS settlement_net_amount,
                    s.settlement_date,
                    s.settlement_reference,

                    b.transaction_id AS actual_bank_transaction_id,
                    b.credit_amount::double precision AS bank_credit_amount,
                    b.currency AS bank_currency,
                    b.transaction_date AS bank_transaction_date,
                    b.narration AS bank_narration,
                    b.reference AS bank_reference

                FROM reconciliation_results AS r

                LEFT JOIN orders AS o
                    ON r.order_id = o.order_id

                LEFT JOIN payments AS p
                    ON r.payment_id = p.payment_id

                LEFT JOIN settlements AS s
                    ON r.settlement_id = s.settlement_id

                LEFT JOIN bank_transactions AS b
                    ON r.bank_transaction_id = b.transaction_id

                WHERE r.result_id = %s
                """,
                (result_id,),
            )

            result = cursor.fetchone()

    finally:
        connection.close()

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Reconciliation result not found: {result_id}",
        )

    result = dict(result)

    # ---------------------------------------------------------
    # LOAD BANK CANDIDATES FOR CANONICAL RE-VERIFICATION
    # ---------------------------------------------------------

    connection = get_connection()

    try:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    transaction_id,
                    batch_id,
                    chain_id,
                    transaction_date,
                    credit_amount,
                    currency,
                    narration,
                    reference
                FROM bank_transactions
                WHERE batch_id = %s
                ORDER BY transaction_id
                """,
                (result["batch_id"],),
            )
            bank_candidates = [
                dict(row)
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()

    # ---------------------------------------------------------
    # CANONICAL CANDIDATE RECONSTRUCTION
    # ---------------------------------------------------------

    ranked_candidates = []
    score_margin = None

    if (
        result.get("method") == "SIMILARITY"
        and result.get("settlement_id") is not None
        and result.get("settlement_net_amount") is not None
    ):
        scoring_candidates = [
            {
                **candidate,
                "net_amount": candidate.get("credit_amount"),
                "settlement_date": candidate.get("transaction_date"),
                "settlement_reference": candidate.get("reference"),
            }
            for candidate in bank_candidates
            if isinstance(candidate, dict)
        ]

        if scoring_candidates:
            candidates = generate_candidates(
                {
                    "settlement_id": result.get("settlement_id"),
                    "net_amount": result.get("settlement_net_amount"),
                    "settlement_date": result.get("settlement_date"),
                    "settlement_reference": result.get(
                        "settlement_reference"
                    ),
                    "currency": result.get("payment_currency")
                    or result.get("order_currency"),
                },
                scoring_candidates,
                amount_field="net_amount",
                date_field="settlement_date",
            )

            if candidates:
                scored_candidates = score_candidates(
                    {
                        "settlement_id": result.get("settlement_id"),
                        "net_amount": result.get("settlement_net_amount"),
                        "settlement_date": result.get("settlement_date"),
                        "settlement_reference": result.get(
                            "settlement_reference"
                        ),
                        "currency": result.get("payment_currency")
                        or result.get("order_currency"),
                    },
                    candidates,
                    amount_field="net_amount",
                    date_field="settlement_date",
                    target_reference_field="settlement_reference",
                    candidate_reference_field="settlement_reference",
                )

                if scored_candidates:
                    selection = select_best_candidate(
                        scored_candidates
                    )

                    if selection is not None:
                        ranked_candidates = selection.get(
                            "ranked_candidates",
                            [],
                        )
                        score_margin = selection.get(
                            "score_margin"
                        )

    # ---------------------------------------------------------
    # CANONICAL DETERMINISTIC VERIFICATION
    # ---------------------------------------------------------

    stored_candidate = result.get("candidate")

    if not isinstance(stored_candidate, dict):
        stored_candidate = None

    verification_candidate = stored_candidate

    if verification_candidate is None and result.get(
        "actual_bank_transaction_id"
    ):
        verification_candidate = {
            "transaction_id": result.get(
                "actual_bank_transaction_id"
            ),
            "credit_amount": result.get(
                "bank_credit_amount"
            ),
            "currency": result.get("bank_currency"),
            "transaction_date": result.get(
                "bank_transaction_date"
            ),
            "reference": result.get("bank_reference"),
        }

    payment_currency = result.get("payment_currency")
    order_currency = result.get("order_currency")

    expected_currency = (
        payment_currency
        if payment_currency is not None
        else order_currency
    )

    verification_settlement = {
        "settlement_id": result.get("settlement_id"),
        "gross_amount": result.get(
            "settlement_gross_amount"
        ),
        "platform_fee": result.get(
            "settlement_platform_fee"
        ),
        "gst_on_fee": result.get(
            "settlement_gst_on_fee"
        ),
        "net_amount": result.get(
            "settlement_net_amount"
        ),
        "settlement_date": result.get(
            "settlement_date"
        ),
        "settlement_reference": result.get(
            "settlement_reference"
        ),
        "currency": expected_currency,
    }

    if verification_candidate is not None:
        verification_result = verify_match(
            verification_settlement,
            verification_candidate,
            bank_candidates,
            method=result.get("method") or "EXACT",
        )

        verification = {
            "amount": {
                "status": (
                    "PASS"
                    if verification_result.amount_passed
                    else "FAIL"
                ),
                "order_amount": result.get("order_amount"),
                "payment_amount": result.get("payment_amount"),
                "settlement_net_amount": result.get(
                    "settlement_net_amount"
                ),
                "bank_credit_amount": result.get(
                    "bank_credit_amount"
                ),
            },
            "fee": {
                "status": (
                    "PASS"
                    if verification_result.fee_passed
                    else "FAIL"
                ),
                "gross_amount": result.get(
                    "settlement_gross_amount"
                ),
                "platform_fee": result.get(
                    "settlement_platform_fee"
                ),
                "gst_on_fee": result.get(
                    "settlement_gst_on_fee"
                ),
                "net_amount": result.get(
                    "settlement_net_amount"
                ),
            },
            "date": {
                "status": (
                    "PASS"
                    if verification_result.date_passed
                    else "FAIL"
                ),
                "settlement_date": result.get(
                    "settlement_date"
                ),
                "bank_date": result.get(
                    "bank_transaction_date"
                ),
            },
            "currency": {
                "status": (
                    "PASS"
                    if verification_result.currency_passed
                    else "FAIL"
                ),
                "expected_currency": expected_currency,
                "bank_currency": result.get(
                    "bank_currency"
                ),
            },
            "reference": {
                "status": (
                    "PASS"
                    if verification_result.reference_passed
                    else "FAIL"
                ),
                "settlement_reference": result.get(
                    "settlement_reference"
                ),
                "bank_reference": result.get(
                    "bank_reference"
                ),
            },
            "uniqueness": {
                "status": (
                    "PASS"
                    if verification_result.uniqueness_passed
                    else "FAIL"
                ),
                "bank_transaction_id": (
                    verification_candidate.get(
                        "transaction_id"
                    )
                    if isinstance(
                        verification_candidate,
                        dict,
                    )
                    else None
                ),
            },
            "passed": verification_result.passed,
            "reasons": verification_result.reasons,
        }
    else:
        verification = {
            "amount": {"status": "FAIL"},
            "fee": {"status": "FAIL"},
            "date": {"status": "FAIL"},
            "currency": {"status": "FAIL"},
            "reference": {"status": "FAIL"},
            "uniqueness": {"status": "FAIL"},
            "passed": False,
            "reasons": [
                "No bank candidate is available for deterministic verification."
            ],
        }

    result["verification"] = verification

    # ---------------------------------------------------------
    # EVIDENCE CHAIN
    # ---------------------------------------------------------

    result["evidence_chain"] = {
        "order": {
            "id": result.get("order_id"),
            "amount": result.get("order_amount"),
            "currency": result.get("order_currency"),
            "date": result.get("order_date"),
            "merchant_id": result.get("merchant_id"),
            "customer_id": result.get("customer_id"),
            "customer_name": result.get("customer_name"),
            "status": result.get("order_status"),
        },
        "payment": {
            "id": result.get("payment_id"),
            "amount": result.get("payment_amount"),
            "currency": result.get("payment_currency"),
            "date": result.get("payment_date"),
            "method": result.get("payment_method"),
            "upi_ref": result.get("upi_ref"),
            "status": result.get("payment_status"),
        },
        "settlement": {
            "id": result.get("settlement_id"),
            "gross_amount": result.get(
                "settlement_gross_amount"
            ),
            "platform_fee": result.get(
                "settlement_platform_fee"
            ),
            "gst_on_fee": result.get(
                "settlement_gst_on_fee"
            ),
            "net_amount": result.get(
                "settlement_net_amount"
            ),
            "date": result.get("settlement_date"),
            "reference": result.get(
                "settlement_reference"
            ),
        },
        "bank": {
            "id": result.get("bank_transaction_id"),
            "transaction_id": result.get(
                "actual_bank_transaction_id"
            ),
            "credit_amount": result.get(
                "bank_credit_amount"
            ),
            "currency": result.get("bank_currency"),
            "date": result.get(
                "bank_transaction_date"
            ),
            "reference": result.get("bank_reference"),
            "narration": result.get("bank_narration"),
        },
    }

    # ---------------------------------------------------------
    # DECISION EXPLANATION
    # ---------------------------------------------------------

    result["decision_explanation"] = {
        "status": result.get("status"),
        "method": result.get("method"),
        "confidence": result.get("confidence"),
        "confidence_bucket": result.get(
            "confidence_bucket"
        ),
        "reason": result.get("reason"),
        "verification_passed": verification["passed"],
        "verification_reasons": verification.get(
            "reasons",
            [],
        ),
        "ai_reasoning": result.get("ai_reasoning"),
    }

    # ---------------------------------------------------------
    # AMBIGUITY / TOP-TWO CANDIDATES
    # ---------------------------------------------------------

    if result.get("exception_type") == "AMBIGUOUS_MATCH":
        top_two = []

        for item in ranked_candidates[:2]:
            candidate = item.get("candidate", {})
            score = item.get("score", {})

            if not isinstance(candidate, dict):
                continue

            top_two.append(
                {
                    "transaction_id": candidate.get(
                        "transaction_id"
                    ),
                    "credit_amount": candidate.get(
                        "credit_amount"
                    ),
                    "currency": candidate.get(
                        "currency"
                    ),
                    "transaction_date": candidate.get(
                        "transaction_date"
                    ),
                    "reference": candidate.get(
                        "reference"
                    ),
                    "narration": candidate.get(
                        "narration"
                    ),
                    "score": score.get(
                        "total_score",
                        0.0,
                    ),
                }
            )

        result["ambiguity"] = {
            "top_two_candidates": top_two,
            "score_margin": score_margin,
            "configured_margin": 0.05,
            "margin_percentage_points": (
                round(score_margin * 100, 2)
                if score_margin is not None
                else None
            ),
            "policy": (
                "Top two candidate scores differ by less "
                "than 0.05 (5 percentage points), so the "
                "system refuses to guess and escalates to "
                "HUMAN_REVIEW."
            ),
        }

        result["escalation_policy"] = {
            "trigger": (
                "Top two candidate scores differ by "
                "less than 0.05."
            ),
            "margin": 0.05,
            "margin_percentage_points": 5,
            "action": "HUMAN_REVIEW",
        }
    else:
        result["ambiguity"] = None
        result["escalation_policy"] = None

    return result


@app.get("/exceptions")
def get_exceptions():
    connection = get_connection()
    try:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    e.exception_id,
                    e.result_id,
                    e.batch_id,
                    e.exception_type,
                    e.status,
                    e.reason,
                    e.created_at,
                    o.order_amount::double precision AS amount
                FROM exceptions AS e
                LEFT JOIN reconciliation_results AS r
                    ON e.result_id = r.result_id
                LEFT JOIN orders AS o
                    ON r.order_id = o.order_id
                ORDER BY e.created_at DESC, e.exception_id DESC
                """
            )
            exceptions = [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()

    return {
        "total": len(exceptions),
        "exceptions": exceptions,
    }


@app.get("/metrics")
def get_metrics():
    connection = get_connection()
    try:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE status = 'AUTO_RESOLVED'
                    ) AS auto_resolved,
                    COUNT(*) FILTER (
                        WHERE status = 'AI_SUGGESTED'
                    ) AS ai_suggested,
                    COUNT(*) FILTER (
                        WHERE status = 'HUMAN_REVIEW'
                    ) AS human_review
                FROM reconciliation_results
                """
            )
            status_counts = dict(cursor.fetchone())

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_exceptions
                FROM exceptions
                """
            )
            exception_counts = dict(cursor.fetchone())

            cursor.execute(
                """
                SELECT
                    exception_type,
                    COUNT(*) AS count
                FROM exceptions
                GROUP BY exception_type
                ORDER BY count DESC, exception_type ASC
                """
            )
            exceptions_by_type = [
                dict(row) for row in cursor.fetchall()
            ]
    finally:
        connection.close()

    total = int(status_counts["total"])
    auto_resolved = int(status_counts["auto_resolved"])
    ai_suggested = int(status_counts["ai_suggested"])
    human_review = int(status_counts["human_review"])
    total_exceptions = int(exception_counts["total_exceptions"])

    return {
        "total": total,
        "auto_resolved": auto_resolved,
        "ai_suggested": ai_suggested,
        "human_review": human_review,
        "total_exceptions": total_exceptions,
        "exceptions_by_type": exceptions_by_type,
    }


@app.get("/reconciliation/{batch_id}")
def reconciliation(batch_id: str):

    (
        orders,
        payments,
        settlements,
        banks,
    ) = load_batch(batch_id)

    # Persist the typed source records for this batch.
    persist_source_records(
        batch_id=batch_id,
        orders=orders,
        payments=payments,
        settlements=settlements,
        banks=banks,
    )

    results = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
        bank_candidates=banks,
    )

    # Persist the canonical Day 3 decisions, exceptions, and audit events.
    persist_decisions(
        batch_id=batch_id,
        decisions=results,
    )

    response_results = []

    for result in results:

        review_id = None

        if result.status == "HUMAN_REVIEW":
            review = create_or_get_review(
                batch_id=batch_id,
                order_id=result.order_id,
                payment_id=result.payment_id,
                settlement_id=result.settlement_id,
                bank_transaction_id=result.bank_transaction_id,
                original_decision=result.status,
                reason=result.reason,
            )

            review_id = review["review_id"]

        response_result = {
            "order_id": result.order_id,
            "payment_id": result.payment_id,
            "settlement_id": result.settlement_id,
            "bank_transaction_id": result.bank_transaction_id,
            "status": result.status,
            "method": result.method,
            "confidence": result.confidence,
            "confidence_bucket": result.confidence_bucket,
            "reason": result.reason,
            "candidate": result.candidate,
            "ai_reasoning": result.ai_reasoning,
        }

        if review_id is not None:
            response_result["review_id"] = review_id

        response_results.append(response_result)

    return {
        "batch_id": batch_id,
        "total": len(results),
        "matched": sum(
            result.status == "AUTO_RESOLVED"
            for result in results
        ),
        "review": sum(
            result.status == "HUMAN_REVIEW"
            for result in results
        ),
        "unresolved": 0,
        "exceptions": 0,
        "results": response_results,
    }


@app.get("/reconciliation/{batch_id}/reviews")
def get_reviews(batch_id: str):

    reviews = list_reviews(batch_id)

    return {
        "batch_id": batch_id,
        "total": len(reviews),
        "reviews": reviews,
    }


@app.get("/reconciliation/{batch_id}/reviews/{review_id}")
def get_review_by_id(
    batch_id: str,
    review_id: str,
):

    review = get_review(review_id)

    if review is None:
        raise HTTPException(
            status_code=404,
            detail=f"Human review not found: {review_id}",
        )

    if review["batch_id"] != batch_id:
        raise HTTPException(
            status_code=404,
            detail=f"Human review not found: {review_id}",
        )

    return review


@app.post(
    "/reconciliation/{batch_id}/reviews/{review_id}/approve"
)
def approve_review(
    batch_id: str,
    review_id: str,
    request: ReviewResolutionRequest,
):

    review = get_review(review_id)

    if review is None or review["batch_id"] != batch_id:
        raise HTTPException(
            status_code=404,
            detail=f"Human review not found: {review_id}",
        )

    try:
        return resolve_review(
            review_id=review_id,
            final_decision="APPROVE",
            reviewer=request.reviewer,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@app.post(
    "/reconciliation/{batch_id}/reviews/{review_id}/reject"
)
def reject_review(
    batch_id: str,
    review_id: str,
    request: ReviewResolutionRequest,
):

    review = get_review(review_id)

    if review is None or review["batch_id"] != batch_id:
        raise HTTPException(
            status_code=404,
            detail=f"Human review not found: {review_id}",
        )

    try:
        return resolve_review(
            review_id=review_id,
            final_decision="REJECT",
            reviewer=request.reviewer,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

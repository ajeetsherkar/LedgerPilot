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
                WHERE result_id = %s
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

    return dict(result)


@app.get("/exceptions")
def get_exceptions():
    connection = get_connection()
    try:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    exception_id,
                    result_id,
                    batch_id,
                    exception_type,
                    status,
                    reason,
                    created_at
                FROM exceptions
                ORDER BY created_at DESC, exception_id DESC
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

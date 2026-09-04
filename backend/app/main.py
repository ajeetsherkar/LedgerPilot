from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

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
    result = ingest_csv_files(
        orders_file=orders,
        payments_file=payments,
        settlements_file=settlements,
        bank_file=bank,
    )

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

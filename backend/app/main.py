from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.database import initialize_database
from backend.app.reconciliation.engine import load_datasets
from backend.app.reconciliation.batch_loader import load_batch
from backend.app.reconciliation.pipeline import reconcile_all
from backend.app.reconciliation.ingestion import ingest_csv_files
from backend.app.reconciliation.human_review import (
    get_review,
    list_reviews,
    resolve_review,
)


class ReviewResolutionRequest(BaseModel):
    reviewer: str
    reason: str


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


@app.get("/reconciliation/{batch_id}")
def reconciliation(batch_id: str):
    (
        orders,
        payments,
        settlements,
        banks,
    ) = load_batch(batch_id)

    results = reconcile_all(
        orders,
        payments,
        settlements,
        banks,
        bank_candidates=banks,
    )

    return {
        "batch_id": batch_id,
        "total": len(results),
        "matched": sum(
            result.status == "MATCH"
            for result in results
        ),
        "review": sum(
            result.status == "REVIEW"
            for result in results
        ),
        "unresolved": sum(
            result.status == "UNRESOLVED"
            for result in results
        ),
        "exceptions": sum(
            result.status == "EXCEPTION"
            for result in results
        ),
        "results": [
            {
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
            for result in results
        ],
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
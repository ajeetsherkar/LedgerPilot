from fastapi import FastAPI, File, UploadFile

from backend.app.database import initialize_database

from backend.app.reconciliation.engine import load_datasets

from backend.app.reconciliation.batch_loader import load_batch
from backend.app.reconciliation.pipeline import reconcile_all

from backend.app.reconciliation.ingestion import ingest_csv_files


app = FastAPI(
    title="LedgerPilot",
    description="AI-assisted financial reconciliation and settlement controller",
    version="0.1.0",
)


@app.on_event("startup")
def startup():
    initialize_database()


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
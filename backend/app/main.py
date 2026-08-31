from fastapi import FastAPI, File, UploadFile

from backend.app.database import initialize_database
from backend.app.reconciliation.engine import reconcile_all
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


@app.get("/reconciliation")
def reconciliation():
    results = reconcile_all()

    return {
        "total": len(results),
        "matched": sum(
            result.reconciliation_status == "MATCHED"
            for result in results
        ),
        "exceptions": sum(
            result.reconciliation_status == "EXCEPTION"
            for result in results
        ),
        "results": [
            {
                "order_id": result.order_id,
                "payment_status": result.payment_status,
                "settlement_status": result.settlement_status,
                "bank_status": result.bank_status,
                "expected_amount": result.expected_amount,
                "paid_amount": result.paid_amount,
                "settled_amount": result.settled_amount,
                "bank_amount": result.bank_amount,
                "difference": result.difference,
                "reconciliation_status": result.reconciliation_status,
                "exception_type": result.exception_type,
            }
            for result in results
        ],
    }

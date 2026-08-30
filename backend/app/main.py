from fastapi import FastAPI

from backend.app.reconciliation.engine import reconcile_all


app = FastAPI(
    title="LedgerPilot",
    description="AI-assisted financial reconciliation and settlement controller",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "LedgerPilot",
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
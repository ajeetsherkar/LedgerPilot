from fastapi import FastAPI

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

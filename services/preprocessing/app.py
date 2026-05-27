from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from services.common.preprocessing import clean_payload


app = FastAPI(title="WE Churn Preprocessing", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/preprocess")
def preprocess(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = clean_payload(payload)
    if not cleaned:
        raise HTTPException(status_code=400, detail="No usable feature was provided")
    return {"features": cleaned}
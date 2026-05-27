from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException

from services.common.preprocessing import build_feature_frame, clean_payload


MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))
PREPROCESSING_URL = os.getenv("PREPROCESSING_URL", "http://preprocessing:8001")
MONITORING_URL = os.getenv("MONITORING_URL", "http://monitoring:8002")
CHURN_THRESHOLD = float(os.getenv("CHURN_THRESHOLD", "0.5"))


@dataclass
class ModelArtifacts:
    churn_model: Any
    offer_model: Any
    feature_columns: list[str]


app = FastAPI(title="WE Churn Inference", version="0.1.0")
_artifacts: ModelArtifacts | None = None


@app.get("/health")
def health() -> dict[str, str]:
    get_artifacts()
    return {"status": "ok"}


@app.post("/predict")
def predict(payload: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        result = predict_payload(payload)
        status_code = 200
        return result
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        latency_ms = (time.perf_counter() - started_at) * 1000
        event = {
            "status_code": status_code,
            "latency_ms": latency_ms,
            "endpoint": "/predict",
        }
        if "result" in locals():
            event.update(result)
        send_monitoring_event(event)


def predict_payload(payload: dict[str, Any]) -> dict[str, Any]:
    artifacts = get_artifacts()
    features = preprocess_payload(payload)
    if not features:
        raise HTTPException(status_code=400, detail="No usable feature was provided")

    frame = build_feature_frame([features], artifacts.feature_columns)
    churn_probability = float(artifacts.churn_model.predict_proba(frame)[0][1])
    if churn_probability >= CHURN_THRESHOLD:
        recommended_offer = str(artifacts.offer_model.predict(frame)[0])
    else:
        recommended_offer = "offre_standard"
    return {
        "churn_probability": round(churn_probability, 4),
        "recommended_offer": recommended_offer,
    }


def preprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not PREPROCESSING_URL:
        return clean_payload(payload)
    try:
        response = requests.post(f"{PREPROCESSING_URL.rstrip('/')}/preprocess", json=payload, timeout=3)
        response.raise_for_status()
        data = response.json()
        return dict(data.get("features", {}))
    except requests.RequestException:
        return clean_payload(payload)


def get_artifacts() -> ModelArtifacts:
    global _artifacts
    if _artifacts is None:
        metadata_path = MODEL_DIR / "model_metadata.json"
        churn_path = MODEL_DIR / "churn_pipeline.pkl"
        offer_path = MODEL_DIR / "offer_pipeline.pkl"
        if not metadata_path.exists() or not churn_path.exists() or not offer_path.exists():
            raise HTTPException(status_code=503, detail="Model artifacts are missing. Run scripts/train_models.py first.")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        _artifacts = ModelArtifacts(
            churn_model=joblib.load(churn_path),
            offer_model=joblib.load(offer_path),
            feature_columns=list(metadata["feature_columns"]),
        )
    return _artifacts


def send_monitoring_event(event: dict[str, Any]) -> None:
    if not MONITORING_URL:
        return
    try:
        requests.post(f"{MONITORING_URL.rstrip('/')}/events", json=event, timeout=1)
    except requests.RequestException:
        pass
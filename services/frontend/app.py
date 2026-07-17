from __future__ import annotations

import csv
import os
import random
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


INFERENCE_URL = os.getenv("INFERENCE_URL", "http://inference-svc:8000")
MONITORING_URL = os.getenv("MONITORING_URL", "http://monitoring-svc:8002")
DATA_PATH = Path(os.getenv("DATA_PATH", "data/churn.csv"))
STATIC_DIR = Path(__file__).parent / "static"

# Colonnes cible / identifiantes a ne jamais transmettre au modele. Volontairement
# dupliquees de services.common.preprocessing pour garder l'image du front legere
# (pas de dependance pandas dans ce service passerelle).
IGNORED_COLUMNS = {
    "CustomerID",
    "customerID",
    "Churn",
    "Churn Label",
    "Churn Value",
    "Churn Score",
    "Churn Reason",
}

app = FastAPI(title="WE Churn Frontend", version="0.1.0")

_rows_cache: list[dict[str, str]] | None = None


def load_rows() -> list[dict[str, str]]:
    """Charge (et met en cache) les lignes du dataset pour tirer un client au hasard."""
    global _rows_cache
    if _rows_cache is None:
        if not DATA_PATH.exists():
            _rows_cache = []
        else:
            # utf-8-sig retire l'eventuel BOM : sans lui, la 1re colonne serait lue
            # "﻿CustomerID" et echapperait au filtre IGNORED_COLUMNS.
            with DATA_PATH.open(encoding="utf-8-sig") as handle:
                _rows_cache = list(csv.DictReader(handle))
    return _rows_cache


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sample")
def sample() -> dict[str, Any]:
    """Retourne un profil client tire aleatoirement, sans les colonnes cible/identifiantes."""
    rows = load_rows()
    if not rows:
        raise HTTPException(status_code=503, detail="Dataset indisponible")
    row = random.choice(rows)
    profile = {key: value for key, value in row.items() if key and key not in IGNORED_COLUMNS}
    return {"profile": profile}


@app.post("/api/predict")
def predict(payload: dict[str, Any]) -> Any:
    """Passe-plat vers le service d'inference (DNS interne ClusterIP)."""
    try:
        response = requests.post(f"{INFERENCE_URL.rstrip('/')}/predict", json=payload, timeout=5)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Service d'inference injoignable: {exc}")
    return JSONResponse(status_code=response.status_code, content=_safe_json(response))


@app.get("/api/metrics")
def metrics() -> Any:
    """Passe-plat vers le service de monitoring (DNS interne ClusterIP)."""
    try:
        response = requests.get(f"{MONITORING_URL.rstrip('/')}/metrics", timeout=5)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Service de monitoring injoignable: {exc}")
    return JSONResponse(status_code=response.status_code, content=_safe_json(response))


def _safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"error": response.text}


# La page statique est montee en dernier pour ne pas masquer les routes /api et /health.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

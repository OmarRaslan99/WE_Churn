from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from services.common.monitoring import MetricsStore


app = FastAPI(title="WE Churn Monitoring", version="0.1.0")
store = MetricsStore()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events")
def collect_event(event: dict[str, Any]) -> dict[str, str]:
    store.add(event)
    return {"status": "recorded"}


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return store.summary()


@app.get("/summary")
def summary() -> dict[str, Any]:
    return store.summary()
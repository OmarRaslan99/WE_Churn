from __future__ import annotations

from fastapi.testclient import TestClient

from services.inference import app as inference_app
from services.inference.app import ModelArtifacts
from services.monitoring.app import app as monitoring_app
from services.preprocessing.app import app as preprocessing_app


class DummyChurnModel:
    def predict_proba(self, frame):
        return [[0.2, 0.8]]


class DummyOfferModel:
    def predict(self, frame):
        return ["remise_tarifaire"]


def test_preprocessing_endpoint() -> None:
    client = TestClient(preprocessing_app)
    response = client.post("/preprocess", json={"CustomerID": "abc", "Tenure Months": "3"})

    assert response.status_code == 200
    assert response.json()["features"] == {"Tenure Months": 3}


def test_inference_predict_contract(monkeypatch) -> None:
    monkeypatch.setattr(inference_app, "PREPROCESSING_URL", "")
    monkeypatch.setattr(inference_app, "MONITORING_URL", "")
    monkeypatch.setattr(
        inference_app,
        "_artifacts",
        ModelArtifacts(
            churn_model=DummyChurnModel(),
            offer_model=DummyOfferModel(),
            feature_columns=["Tenure Months", "Contract"],
        ),
    )
    client = TestClient(inference_app.app)

    response = client.post("/predict", json={"Tenure Months": "10", "Contract": "Month-to-month"})

    assert response.status_code == 200
    assert response.json() == {"churn_probability": 0.8, "recommended_offer": "remise_tarifaire"}


def test_monitoring_summary() -> None:
    client = TestClient(monitoring_app)
    client.post("/events", json={"status_code": 200, "latency_ms": 25, "recommended_offer": "offre_standard"})
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.json()["total_requests"] >= 1
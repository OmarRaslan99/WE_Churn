from __future__ import annotations

from fastapi.testclient import TestClient

from services.frontend import app as frontend_app


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


def test_frontend_health() -> None:
    client = TestClient(frontend_app.app)
    assert client.get("/health").json() == {"status": "ok"}


def test_frontend_serves_index() -> None:
    client = TestClient(frontend_app.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "WE Churn" in response.text


def test_frontend_sample_drops_target_columns() -> None:
    client = TestClient(frontend_app.app)
    body = client.get("/api/sample").json()

    assert "profile" in body
    profile = body["profile"]
    assert len(profile) > 0
    for forbidden in ("CustomerID", "Churn Value", "Churn Label", "Churn Reason"):
        assert forbidden not in profile
    # Aucune cle ne doit contenir un identifiant/cible, meme prefixe d'un BOM (utf-8-sig).
    for key in profile:
        assert "CustomerID" not in key
        assert "Churn" not in key


def test_frontend_predict_proxies_inference(monkeypatch) -> None:
    def fake_post(url, json=None, timeout=None):
        assert url.endswith("/predict")
        assert json == {"Tenure Months": "3"}
        return _FakeResponse({"churn_probability": 0.8, "recommended_offer": "remise_tarifaire"})

    monkeypatch.setattr(frontend_app.requests, "post", fake_post)
    client = TestClient(frontend_app.app)

    response = client.post("/api/predict", json={"Tenure Months": "3"})
    assert response.status_code == 200
    assert response.json()["recommended_offer"] == "remise_tarifaire"


def test_frontend_metrics_proxies_monitoring(monkeypatch) -> None:
    def fake_get(url, timeout=None):
        assert url.endswith("/metrics")
        return _FakeResponse({"total_requests": 5, "success_rate_pct": 100.0})

    monkeypatch.setattr(frontend_app.requests, "get", fake_get)
    client = TestClient(frontend_app.app)

    body = client.get("/api/metrics").json()
    assert body["total_requests"] == 5


def test_frontend_predict_handles_backend_down(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise frontend_app.requests.RequestException("connection refused")

    monkeypatch.setattr(frontend_app.requests, "post", boom)
    client = TestClient(frontend_app.app)

    response = client.post("/api/predict", json={})
    assert response.status_code == 502


def test_frontend_metrics_handles_backend_down(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise frontend_app.requests.RequestException("connection refused")

    monkeypatch.setattr(frontend_app.requests, "get", boom)
    client = TestClient(frontend_app.app)

    response = client.get("/api/metrics")
    assert response.status_code == 502

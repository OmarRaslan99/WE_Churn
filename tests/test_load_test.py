from __future__ import annotations

import json

from scripts import load_test


def test_save_results_writes_json(tmp_path) -> None:
    results = {
        "case": "churn",
        "level": "nominal",
        "rate_configured": 10,
        "duration_s": 1,
        "total_requests": 1,
        "success_200": 1,
        "failure": 0,
        "success_rate_pct": 100.0,
        "latency_avg_s": 0.1,
        "latency_p95_s": 0.1,
        "latency_max_s": 0.1,
        "status_counts": {"200": 1},
        "started_at_utc": "2026-05-29T00:00:00+00:00",
        "ended_at_utc": "2026-05-29T00:00:01+00:00",
        "url": "http://localhost:8000/predict",
    }

    output_path = load_test.save_results(results, tmp_path)
    archived = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.exists()
    assert archived["case"] == "churn"
    assert archived["success_rate_pct"] == 100.0
    assert "archived_at_utc" in archived
    assert "hostname" in archived


def test_enforce_thresholds_accepts_valid_results() -> None:
    load_test.enforce_thresholds(
        {"success_rate_pct": 100.0, "latency_p95_s": 0.2},
        min_success_rate=95.0,
        max_p95_s=1.0,
    )


def test_enforce_thresholds_rejects_invalid_results() -> None:
    try:
        load_test.enforce_thresholds(
            {"success_rate_pct": 80.0, "latency_p95_s": 3.0},
            min_success_rate=95.0,
            max_p95_s=1.0,
        )
    except SystemExit as exc:
        assert "Seuils de charge" in str(exc)
    else:
        raise AssertionError("Expected SystemExit for invalid load-test thresholds")
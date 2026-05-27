from __future__ import annotations

from collections import Counter
from threading import Lock
from typing import Any


class MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._events: list[dict[str, Any]] = []

    def add(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._events.append(event)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)

        total = len(events)
        errors = sum(1 for event in events if event.get("status_code", 200) >= 400)
        latencies = [float(event.get("latency_ms", 0.0)) for event in events]
        offers = Counter(str(event.get("recommended_offer", "unknown")) for event in events)
        return {
            "total_requests": total,
            "errors": errors,
            "success_rate_pct": round(((total - errors) / total) * 100, 2) if total else 0.0,
            "latency_avg_ms": round(sum(latencies) / total, 2) if total else 0.0,
            "latency_max_ms": round(max(latencies), 2) if latencies else 0.0,
            "offers": dict(offers),
        }
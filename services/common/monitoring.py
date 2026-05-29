from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from threading import Lock
import time
from typing import Any


class MetricsStore:
    def __init__(self, max_events: int = 10000) -> None:
        self._lock = Lock()
        self._events: list[dict[str, Any]] = []
        self._max_events = max_events
        self._started_at = datetime.now(timezone.utc)

    def add(self, event: dict[str, Any]) -> None:
        recorded_at = datetime.now(timezone.utc)
        enriched = {
            **event,
            "timestamp_unix": time.time(),
            "timestamp_utc": recorded_at.isoformat(),
        }
        with self._lock:
            self._events.append(enriched)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def events(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, self._max_events))
        with self._lock:
            return list(self._events[-limit:])

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._started_at = datetime.now(timezone.utc)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)
            started_at = self._started_at

        total = len(events)
        success_count = sum(1 for event in events if event.get("status_code", 200) == 200)
        errors = total - success_count
        latencies = [float(event.get("latency_ms", 0.0)) for event in events]
        sorted_latencies = sorted(latencies)
        offers = Counter(str(event.get("recommended_offer", "unknown")) for event in events)
        status_codes = Counter(str(event.get("status_code", "unknown")) for event in events)
        now = datetime.now(timezone.utc)
        return {
            "collected_at_utc": now.isoformat(),
            "started_at_utc": started_at.isoformat(),
            "uptime_s": round((now - started_at).total_seconds(), 2),
            "total_requests": total,
            "success_count": success_count,
            "errors": errors,
            "success_rate_pct": round((success_count / total) * 100, 2) if total else 0.0,
            "latency_avg_ms": round(sum(latencies) / total, 2) if total else 0.0,
            "latency_p95_ms": round(percentile(sorted_latencies, 0.95), 2) if sorted_latencies else 0.0,
            "latency_max_ms": round(max(latencies), 2) if latencies else 0.0,
            "status_codes": dict(status_codes),
            "offers": dict(offers),
        }


def percentile(sorted_values: list[float], rank: float) -> float:
    if not sorted_values:
        return 0.0
    index = max(0, min(len(sorted_values) - 1, int(rank * len(sorted_values)) - 1))
    return sorted_values[index]
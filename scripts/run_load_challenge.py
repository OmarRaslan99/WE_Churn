#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import load_test


DEFAULT_NAMESPACE = "projet-we"
DEFAULT_OUTPUT_DIR = Path("results/seance4")


def run_command(command: list[str], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        output_path.write_text(f"Command failed to start: {exc}\n", encoding="utf-8")
        return 127

    output_path.write_text(
        f"$ {' '.join(command)}\n\nSTDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}\n",
        encoding="utf-8",
    )
    return completed.returncode


def collect_top_samples(namespace: str, interval_s: int, stop_event: threading.Event, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"# kubectl top pods -n {namespace}\n")
        while not stop_event.is_set():
            handle.write(f"\n=== {datetime.now(timezone.utc).isoformat()} ===\n")
            try:
                completed = subprocess.run(
                    ["kubectl", "top", "pods", "-n", namespace],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                handle.write(completed.stdout)
                if completed.stderr:
                    handle.write("\nSTDERR:\n" + completed.stderr)
            except OSError as exc:
                handle.write(f"kubectl unavailable: {exc}\n")
            handle.flush()
            stop_event.wait(interval_s)


def monitoring_base_url(predict_url: str, explicit_url: str | None) -> str | None:
    if explicit_url:
        return explicit_url.rstrip("/")
    if "localhost:8000" in predict_url:
        return "http://localhost:8002"
    return None


def call_monitoring(method: str, base_url: str | None, path: str, output_path: Path | None = None) -> dict[str, Any] | None:
    if not base_url:
        return None
    try:
        response = requests.request(method, f"{base_url.rstrip('/')}{path}", timeout=5)
        response.raise_for_status()
        body = response.json()
    except requests.RequestException as exc:
        body = {"error": str(exc)}
    if output_path is not None:
        output_path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return body


def capture_kubernetes_snapshot(namespace: str, output_dir: Path, label: str) -> None:
    snapshot_dir = output_dir / label
    commands = {
        "pods.txt": ["kubectl", "get", "pods", "-n", namespace, "-o", "wide"],
        "all.txt": ["kubectl", "get", "all", "-n", namespace],
        "events.txt": ["kubectl", "get", "events", "-n", namespace, "--sort-by=.lastTimestamp"],
        "resourcequota.txt": ["kubectl", "describe", "resourcequota", "-n", namespace],
        "describe_pods.txt": ["kubectl", "describe", "pods", "-n", namespace],
    }
    for filename, command in commands.items():
        run_command(command, snapshot_dir / filename)

    for service in ("preprocessing", "inference", "monitoring"):
        run_command(
            ["kubectl", "logs", "-n", namespace, "-l", f"app={service}", "--tail=200", "--timestamps=true"],
            snapshot_dir / f"{service}_logs.txt",
        )
        run_command(
            ["kubectl", "logs", "-n", namespace, "-l", f"app={service}", "--previous", "--tail=200"],
            snapshot_dir / f"{service}_previous_logs.txt",
        )


def run_challenge(args: argparse.Namespace) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_dir) / f"{timestamp}_{args.level}"
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "level": args.level,
        "case": args.case,
        "rate": args.rate,
        "duration_s": args.duration,
        "url": args.url,
        "namespace": args.namespace,
        "top_interval_s": args.top_interval,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    monitoring_url = monitoring_base_url(args.url, args.monitoring_url)
    if args.reset_monitoring:
        call_monitoring("POST", monitoring_url, "/reset", run_dir / "monitoring_reset.json")

    capture_kubernetes_snapshot(args.namespace, run_dir, "before")
    call_monitoring("GET", monitoring_url, "/metrics", run_dir / "monitoring_before.json")

    stop_event = threading.Event()
    sampler = threading.Thread(
        target=collect_top_samples,
        args=(args.namespace, args.top_interval, stop_event, run_dir / "kubectl_top_pods.log"),
        daemon=True,
    )
    sampler.start()
    try:
        level_config = load_test.LEVELS[args.level]
        rate = args.rate if args.level == "extreme" else level_config["rate"]
        if args.level == "extreme" and rate is None:
            raise SystemExit("[ERREUR] --level extreme requiert --rate N")
        results = load_test.run_test(args.case, rate, args.duration, args.url)
        load_test.print_results(results)
        result_path = load_test.save_results(results, run_dir)
    finally:
        stop_event.set()
        sampler.join(timeout=args.top_interval + 5)

    call_monitoring("GET", monitoring_url, "/metrics", run_dir / "monitoring_after.json")
    call_monitoring("GET", monitoring_url, "/events?limit=500", run_dir / "monitoring_events.json")
    capture_kubernetes_snapshot(args.namespace, run_dir, "after")

    summary = {
        **metadata,
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "load_result_file": str(result_path),
        "success_rate_pct": results["success_rate_pct"],
        "latency_avg_s": results["latency_avg_s"],
        "latency_p95_s": results["latency_p95_s"],
        "latency_max_s": results["latency_max_s"],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[ARCHIVE] Dossier challenge : {run_dir}")
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orchestration du challenge de charge seance 4")
    parser.add_argument("--case", choices=["images", "text", "churn"], default="churn")
    parser.add_argument("--level", choices=["nominal", "charge", "stress", "extreme"], required=True)
    parser.add_argument("--rate", type=int, default=None, help="Requetes/minute pour le mode extreme")
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--url", required=True, help="URL complete du endpoint /predict")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--top-interval", type=int, default=30)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--monitoring-url", default=None, help="URL externe du monitoring, si disponible")
    parser.add_argument("--reset-monitoring", action="store_true")
    return parser.parse_args()


def main() -> None:
    run_challenge(parse_args())


if __name__ == "__main__":
    sys.exit(main())
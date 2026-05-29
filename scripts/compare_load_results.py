#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


METRICS = [
    ("success_rate_pct", "Taux succes", "%", True),
    ("latency_avg_s", "Latence moyenne", "s", False),
    ("latency_p95_s", "Latence P95", "s", False),
    ("latency_max_s", "Latence max", "s", False),
    ("failure", "Echecs", "", False),
    ("total_requests", "Requetes", "", True),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_value(value: Any, unit: str) -> str:
    if isinstance(value, float):
        rendered = f"{value:.3f}".rstrip("0").rstrip(".")
    else:
        rendered = str(value)
    return f"{rendered}{unit}" if unit else rendered


def delta(before: Any, after: Any, unit: str, higher_is_better: bool) -> str:
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return "n/a"
    raw_delta = after - before
    if before:
        percent = (raw_delta / before) * 100
        percent_text = f" ({percent:+.1f}%)"
    else:
        percent_text = ""
    direction = "amelioration" if (raw_delta >= 0) == higher_is_better else "degradation"
    return f"{format_value(raw_delta, unit)}{percent_text} - {direction}"


def build_markdown(before: dict[str, Any], after: dict[str, Any]) -> str:
    lines = [
        f"# Comparaison charge - {before.get('level', 'avant')} -> {after.get('level', 'apres')}",
        "",
        f"Avant : `{before.get('started_at_utc', before.get('archived_at_utc', 'n/a'))}`",
        f"Apres : `{after.get('started_at_utc', after.get('archived_at_utc', 'n/a'))}`",
        "",
        "| Metrique | Avant | Apres | Changement |",
        "| --- | ---: | ---: | --- |",
    ]
    for key, label, unit, higher_is_better in METRICS:
        before_value = before.get(key, 0)
        after_value = after.get(key, 0)
        lines.append(
            f"| {label} | {format_value(before_value, unit)} | {format_value(after_value, unit)} | "
            f"{delta(before_value, after_value, unit, higher_is_better)} |"
        )
    lines.extend([
        "",
        "## Analyse a completer",
        "",
        "- Correction appliquee :",
        "- Indices Kubernetes observes avant correction :",
        "- Justification de l'effet mesure :",
    ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare deux resultats JSON de charge")
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    markdown = build_markdown(load_json(args.before), load_json(args.after))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        print(f"[ARCHIVE] Comparaison Markdown : {args.output}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
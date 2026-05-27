from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests


IGNORED_COLUMNS = {
    "CustomerID",
    "customerID",
    "Churn",
    "Churn Label",
    "Churn Value",
    "Churn Score",
    "Churn Reason",
}


def build_payload(csv_path: Path) -> dict[str, Any]:
    data = pd.read_csv(csv_path)
    if data.empty:
        raise SystemExit(f"No rows found in {csv_path}")
    row = data.iloc[0].to_dict()
    return {key: value for key, value in row.items() if key not in IGNORED_COLUMNS}


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test for the churn inference API")
    parser.add_argument("--url", default="http://localhost:8000/predict", help="Full /predict URL")
    parser.add_argument("--csv", default="data/churn.csv", help="Path to churn.csv")
    args = parser.parse_args()

    payload = build_payload(Path(args.csv))
    response = requests.post(args.url, json=payload, timeout=10)
    response.raise_for_status()
    body = response.json()
    if "churn_probability" not in body or "recommended_offer" not in body:
        raise SystemExit(f"Unexpected response body: {json.dumps(body, indent=2)}")
    print(json.dumps(body, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
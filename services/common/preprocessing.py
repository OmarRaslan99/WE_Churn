from __future__ import annotations

from typing import Any

import pandas as pd


IGNORED_COLUMNS = {
    "CustomerID",
    "customerID",
    "Churn",
    "Churn Label",
    "Churn Value",
    "Churn Score",
    "Churn Reason",
}

NUMERIC_COLUMNS = {
    "Count",
    "Zip Code",
    "Latitude",
    "Longitude",
    "Tenure Months",
    "Monthly Charges",
    "Total Charges",
    "CLTV",
}


def clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key in IGNORED_COLUMNS:
            continue
        if value == "":
            cleaned[key] = None
        elif key in NUMERIC_COLUMNS:
            cleaned[key] = _to_number(value)
        else:
            cleaned[key] = value
    return cleaned


def build_feature_frame(payloads: list[dict[str, Any]], feature_columns: list[str] | None = None) -> pd.DataFrame:
    rows = [clean_payload(payload) for payload in payloads]
    frame = pd.DataFrame(rows)
    frame = frame.replace({"": pd.NA})

    for column in NUMERIC_COLUMNS.intersection(frame.columns):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if feature_columns is not None:
        for column in feature_columns:
            if column not in frame.columns:
                frame[column] = pd.NA
        frame = frame[feature_columns]

    return frame


def split_features_target(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    if "Churn Value" in data.columns:
        target = pd.to_numeric(data["Churn Value"], errors="coerce").fillna(0).astype(int)
    elif "Churn Label" in data.columns:
        target = data["Churn Label"].map({"Yes": 1, "No": 0}).fillna(0).astype(int)
    elif "Churn" in data.columns:
        target = data["Churn"].map({"Yes": 1, "No": 0, "1": 1, "0": 0}).fillna(0).astype(int)
    else:
        raise ValueError("No churn target column found. Expected 'Churn Value', 'Churn Label' or 'Churn'.")

    features = data.drop(columns=[column for column in IGNORED_COLUMNS if column in data.columns], errors="ignore")
    features = features.replace({"": pd.NA})
    for column in NUMERIC_COLUMNS.intersection(features.columns):
        features[column] = pd.to_numeric(features[column], errors="coerce")
    return features, target


def _to_number(value: Any) -> float | int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number
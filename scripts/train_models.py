from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.common.preprocessing import split_features_target


DATA_PATH = ROOT / "data" / "churn.csv"
MODEL_DIR = ROOT / "models"
OFFER_LABELS = [
    "remise_tarifaire",
    "engagement_avantageux",
    "upgrade_data",
    "support_prioritaire",
    "offre_famille",
]


def main() -> None:
    MODEL_DIR.mkdir(exist_ok=True)
    data = pd.read_csv(DATA_PATH)
    features, target = split_features_target(data)
    feature_columns = list(features.columns)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=42,
        stratify=target,
    )

    churn_pipeline = build_classifier(features)
    churn_pipeline.fit(x_train, y_train)
    churn_metrics = evaluate_churn(churn_pipeline, x_test, y_test)

    synthetic_features, offer_target = build_offer_dataset(features, rows=5000)
    x_offer_train, x_offer_test, y_offer_train, y_offer_test = train_test_split(
        synthetic_features,
        offer_target,
        test_size=0.2,
        random_state=42,
        stratify=offer_target,
    )
    offer_pipeline = build_classifier(synthetic_features)
    offer_pipeline.fit(x_offer_train, y_offer_train)
    offer_predictions = offer_pipeline.predict(x_offer_test)
    offer_metrics = {"accuracy": round(float(accuracy_score(y_offer_test, offer_predictions)), 4)}

    inference_time_ms = measure_inference_time(churn_pipeline, offer_pipeline, x_test.head(200))

    joblib.dump(churn_pipeline, MODEL_DIR / "churn_pipeline.pkl")
    joblib.dump(offer_pipeline, MODEL_DIR / "offer_pipeline.pkl")
    metadata = {
        "dataset": "Telco Customer Churn IBM",
        "source": "Kaggle / UCI ML Repository / GitHub public mirrors",
        "license": "Public dataset for educational use",
        "feature_columns": feature_columns,
        "churn_metrics": churn_metrics,
        "offer_metrics": offer_metrics,
        "inference_time_ms_avg_local": inference_time_ms,
        "artifact_sizes_bytes": {
            "churn_pipeline.pkl": (MODEL_DIR / "churn_pipeline.pkl").stat().st_size,
            "offer_pipeline.pkl": (MODEL_DIR / "offer_pipeline.pkl").stat().st_size,
        },
    }
    (MODEL_DIR / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_model_readme(metadata)
    print(json.dumps(metadata, indent=2))


def build_classifier(features: pd.DataFrame) -> Pipeline:
    numeric_features = list(features.select_dtypes(include=["number", "bool"]).columns)
    categorical_features = [column for column in features.columns if column not in numeric_features]
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", SimpleImputer(strategy="median"), numeric_features),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical_features,
            ),
        ]
    )
    classifier = RandomForestClassifier(
        n_estimators=120,
        max_depth=12,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    return Pipeline(steps=[("preprocessor", preprocessor), ("classifier", classifier)])


def evaluate_churn(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]
    return {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "f1": round(float(f1_score(y_test, predictions)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
    }


def build_offer_dataset(features: pd.DataFrame, rows: int) -> tuple[pd.DataFrame, pd.Series]:
    synthetic = features.sample(n=rows, replace=True, random_state=42).reset_index(drop=True).copy()
    monthly = pd.to_numeric(synthetic.get("Monthly Charges", 0), errors="coerce").fillna(0)
    tenure = pd.to_numeric(synthetic.get("Tenure Months", 0), errors="coerce").fillna(0)
    dependents = synthetic.get("Dependents", "No").fillna("No").astype(str)
    contract = synthetic.get("Contract", "Month-to-month").fillna("Month-to-month").astype(str)
    tech_support = synthetic.get("Tech Support", "No").fillna("No").astype(str)
    internet = synthetic.get("Internet Service", "No").fillna("No").astype(str)

    labels: list[str] = []
    for index in range(len(synthetic)):
        if monthly.iloc[index] >= 85 and contract.iloc[index] == "Month-to-month":
            labels.append("remise_tarifaire")
        elif tenure.iloc[index] < 12:
            labels.append("engagement_avantageux")
        elif internet.iloc[index] == "Fiber optic":
            labels.append("upgrade_data")
        elif tech_support.iloc[index] == "No":
            labels.append("support_prioritaire")
        elif dependents.iloc[index] == "Yes":
            labels.append("offre_famille")
        else:
            labels.append(OFFER_LABELS[index % len(OFFER_LABELS)])
    return synthetic, pd.Series(labels, name="recommended_offer")


def measure_inference_time(churn_model: Pipeline, offer_model: Pipeline, frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    started_at = time.perf_counter()
    churn_model.predict_proba(frame)
    offer_model.predict(frame)
    elapsed = time.perf_counter() - started_at
    return round((elapsed / len(frame)) * 1000, 4)


def write_model_readme(metadata: dict) -> None:
    readme = f"""# Model validation

## Dataset

- Source: {metadata['dataset']} ({metadata['source']})
- Licence: {metadata['license']}
- Local file: `data/churn.csv`

## Churn model

- Algorithm: RandomForestClassifier with a scikit-learn preprocessing pipeline
- Metrics: accuracy={metadata['churn_metrics']['accuracy']}, f1={metadata['churn_metrics']['f1']}, roc_auc={metadata['churn_metrics']['roc_auc']}
- Artifact: `models/churn_pipeline.pkl`
- Size: {metadata['artifact_sizes_bytes']['churn_pipeline.pkl']} bytes

## Offer recommendation model

- Algorithm: RandomForestClassifier trained on 5000 synthetic rows and 5 offer categories
- Metrics: accuracy={metadata['offer_metrics']['accuracy']}
- Artifact: `models/offer_pipeline.pkl`
- Size: {metadata['artifact_sizes_bytes']['offer_pipeline.pkl']} bytes

## Local inference benchmark

- Average inference time: {metadata['inference_time_ms_avg_local']} ms per row on the local training environment

## Reproduce

```powershell
uv run python scripts/train_models.py
```
"""
    (MODEL_DIR / "README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()
# Model validation

## Dataset

- Source: Telco Customer Churn IBM (Kaggle / UCI ML Repository / GitHub public mirrors)
- Licence: Public dataset for educational use
- Local file: `data/churn.csv`

## Churn model

- Algorithm: RandomForestClassifier with a scikit-learn preprocessing pipeline
- Metrics: accuracy=0.748, f1=0.6235, roc_auc=0.8383
- Artifact: `models/churn_pipeline.pkl`
- Size: 2536571 bytes

## Offer recommendation model

- Algorithm: RandomForestClassifier trained on 5000 synthetic rows and 5 offer categories
- Metrics: accuracy=0.814
- Artifact: `models/offer_pipeline.pkl`
- Size: 3840483 bytes

## Local inference benchmark

- Average inference time: 0.576 ms per row on the local training environment

## Reproduce

```powershell
uv run python scripts/train_models.py
```

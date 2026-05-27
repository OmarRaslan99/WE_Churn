# WE Churn - TP Orchestration ML

## Deploiement

Prerequis locaux : Docker Desktop, Minikube et `uv`.

```powershell
uv sync
uv run python scripts/train_models.py
uv run pytest --cov
docker compose up --build
```

Les memes commandes sont regroupees dans le `Makefile` :

```powershell
make setup
make train
make test
make run
```

L'API d'inference est exposee localement sur `http://localhost:8000`.

Tester une prediction avec PowerShell :

```powershell
$row = Import-Csv .\data\churn.csv | Select-Object -First 1
$payload = $row | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/predict -Body $payload -ContentType "application/json"
```

Consulter le monitoring :

```powershell
Invoke-RestMethod http://localhost:8002/metrics
```

Lancer un test de charge court contre Docker Compose :

```powershell
uv run python scripts/load_test.py --case churn --level nominal --duration 30 --url http://localhost:8000/predict
```

Equivalent via le `Makefile` :

```powershell
make smoke
make load-test
```

## Entrainement

Les modeles sont entraines hors Minikube a partir de `data/churn.csv`. Les artefacts sont generes dans `models/` :

- `churn_pipeline.pkl`
- `offer_pipeline.pkl`
- `model_metadata.json`
- `README.md`

## Services

- `services/preprocessing` : validation et nettoyage des profils clients.
- `services/inference` : endpoint `POST /predict`, prediction churn et recommandation.
- `services/monitoring` : collecte des evenements, volume, latence et erreurs.

## Docker Hub

Pour tagger et pousser les images apres connexion Docker Hub :

```powershell
docker tag we-churn-preprocessing:0.1.0 <dockerhub-user>/we-churn-preprocessing:v0.1.0-seance2
docker tag we-churn-inference:0.1.0 <dockerhub-user>/we-churn-inference:v0.1.0-seance2
docker tag we-churn-monitoring:0.1.0 <dockerhub-user>/we-churn-monitoring:v0.1.0-seance2
docker push <dockerhub-user>/we-churn-preprocessing:v0.1.0-seance2
docker push <dockerhub-user>/we-churn-inference:v0.1.0-seance2
docker push <dockerhub-user>/we-churn-monitoring:v0.1.0-seance2
```

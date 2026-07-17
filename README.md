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

Les resultats sont archives automatiquement en JSON dans `results/load_tests/`. Pour imposer un seuil lors d'une verification locale ou CI :

```powershell
uv run python scripts/load_test.py --case churn --level nominal --duration 30 --url http://localhost:8000/predict --min-success-rate 95 --max-p95-s 2
```

Equivalent via le `Makefile` :

```powershell
make smoke
make load-test
```

## Deploiement Kubernetes

Les manifests Kubernetes sont dans `k8s/`. Par defaut, ils referencent les images Docker Hub `omarraslan99/we-churn-*:v0.1.0-seance3`. Si votre identifiant Docker Hub est different, remplacez `omarraslan99` dans les manifests `k8s/*.yaml` et lancez `make docker-push DOCKER_USER=<dockerhub-user>` avec le meme nom.

Demarrage Minikube et deploiement complet :

```powershell
make minikube-start
make k8s-deploy
make k8s-rollout
make k8s-status
```

Equivalent manuel :

```powershell
minikube start --cpus=4 --memory=6144 --driver=docker
minikube addons enable metrics-server
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/ -n projet-we
kubectl get all -n projet-we
```

Recuperer l'URL du service d'inference :

```powershell
make k8s-url
```

Tester l'API Kubernetes :

```powershell
make smoke URL=<URL_MINIKUBE>/predict
make load-test URL=<URL_MINIKUBE>/predict DURATION=60
```

Mesurer les ressources pour justifier `requests` et `limits` :

```powershell
make k8s-top
make k8s-quota
```

Les mesures et la justification sont a reporter dans [k8s/RESOURCE_MEASUREMENTS.md](k8s/RESOURCE_MEASUREMENTS.md).

## Seance 4 - Challenge de charge

Le protocole complet doit etre execute sur Minikube, car il depend de `kubectl top pods`, du namespace `projet-we` et du quota Kubernetes. Avant de lancer les paliers, verifier que les services sont disponibles :

```powershell
make minikube-start
make k8s-deploy
make k8s-rollout
make k8s-status
$url = "<URL_MINIKUBE>/predict"
make smoke URL=$url
```

Lancer ensuite les trois niveaux imposes, chacun avec collecte `kubectl top pods` toutes les 30 secondes et archivage des diagnostics :

```powershell
make challenge-nominal URL=$url
make challenge-charge URL=$url
make challenge-stress URL=$url
```

Chaque execution cree un dossier `results/seance4/<timestamp>_<niveau>/` avec le JSON du test, les echantillons CPU/memoire, les events Kubernetes, les logs et les metriques monitoring. Apres identification du palier critique, appliquer une seule correction, redeployer, puis relancer uniquement ce palier.

Pour generer le tableau avant/apres :

```powershell
make challenge-compare BEFORE=<avant.json> AFTER=<apres.json> COMPARE_OUTPUT=results/seance4/comparison.md
```

Les conclusions finales doivent etre reportees dans [k8s/RESOURCE_MEASUREMENTS.md](k8s/RESOURCE_MEASUREMENTS.md) et dans [ADR/ADR.md](ADR/ADR.md).

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
- `services/frontend` : front web de demonstration (passerelle). Sert une page unique et fait proxy vers `inference-svc` et `monitoring-svc` via le DNS interne (`/api/predict`, `/api/metrics`, `/api/sample`).

## Demo - front web

Le service `frontend` expose une interface de demonstration en `NodePort`. Il tire un client au hasard dans le dataset, permet d'editer quelques champs (contrat, anciennete, charges, Internet), lance une prediction en direct et affiche les metriques du monitoring rafraichies en continu.

En local avec Docker Compose, le front est disponible sur `http://localhost:8080`.

Sur Kubernetes, recuperer son URL :

```powershell
make k8s-url-front
```

## Docker Hub

Pour tagger et pousser les images apres connexion Docker Hub :

```powershell
make build
make docker-push DOCKER_USER=<dockerhub-user>
```

## CI/CD GitHub Actions

Le workflow `.github/workflows/ci.yml` execute les tests avec couverture 80 %, entraine les modeles pour verifier la reproductibilite, puis construit et pousse les trois images Docker Hub uniquement sur `main` si les tests passent.

La CI lance aussi un test de charge court avec Docker Compose : demarrage des trois services, smoke test, puis `scripts/load_test.py` pendant 30 secondes avec seuils `success_rate_pct >= 95` et `latency_p95_s <= 2`. Ce test detecte les regressions d'API ou d'image Docker, mais ne remplace pas le challenge Minikube complet de la seance 4.

Secrets GitHub requis :

- `DOCKER_USERNAME`
- `DOCKER_TOKEN`

Le push Docker est conditionne a la reussite du job de tests, ce qui evite de publier une image si la couverture ou les tests echouent.

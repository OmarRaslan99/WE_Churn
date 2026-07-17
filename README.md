# WE Churn - TP Orchestration ML

Pipeline ML multi-services deploye sous contrainte de ressources (Cas 3 : **prediction de churn et recommandation d'offre** pour un operateur telecom). L'objectif n'est pas le meilleur modele, mais un systeme qui **tient sous charge**, **respecte un quota Kubernetes fixe** (2500m CPU / 1,5 Gi) et se **deploie depuis un simple `git clone`**.

## Deploiement

Prerequis : Docker Desktop, Minikube, `kubectl` et `uv`. Le systeme se deploie sur Minikube a partir des images publiques Docker Hub, **multi-arch (amd64 / arm64), donc compatibles Mac Intel et Apple Silicon** (aucune construction requise) :

```bash
minikube start --cpus=4 --memory=6144 --driver=docker
minikube addons enable metrics-server
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/ -n projet-we
kubectl get pods -n projet-we
```

Recuperer l'URL du front de demonstration (a laisser ouvert) :

```bash
minikube service frontend-svc -n projet-we --url
```

> **Guide pas-a-pas complet (macOS) - installation des prerequis, verification en local via Docker Compose, tests, script de charge aux trois niveaux, depannage : voir [SETUP.md](SETUP.md).**

## Architecture

Quatre services containerises dans le namespace `projet-we` :

| Service         | Role                                                                   | Expose      |
| --------------- | ---------------------------------------------------------------------- | ----------- |
| `preprocessing` | Valide et normalise le profil client (`POST /preprocess`)              | ClusterIP   |
| `inference`     | Porte les **deux modeles**, orchestre la prediction (`POST /predict`)  | NodePort    |
| `monitoring`    | Volume, latence, taux d'erreur, P95 (`POST /events`, `GET /metrics`)   | ClusterIP   |
| `frontend`      | Console de demo (passerelle) : proxy vers inference et monitoring      | NodePort    |

Le client attaque `inference` (ou le `frontend`) ; l'inference appelle `preprocessing` puis `monitoring` via le **DNS interne Kubernetes** (ClusterIP). Le namespace est encadre par un `ResourceQuota` et un `LimitRange`.

## Modeles

Deux modeles **RandomForest** legers, entraines hors Minikube a partir de `data/churn.csv`, versionnes dans `models/` :

- **Churn** : score de resiliation 0-1. ROC-AUC 0,838, F1 0,624, accuracy 0,748 (~2,5 Mo).
- **Offre** : recommandation parmi 5 categories, sur donnees synthetiques. Accuracy 0,814 (~3,8 Mo).
- **Routage** : si le score de churn depasse le seuil `CHURN_THRESHOLD` (0,5), le second modele est appele ; sinon `offre_standard`.

Fiche de validation detaillee : [models/README.md](models/README.md).

## Quota et dimensionnement

La somme des `requests` et des `limits` des quatre services reste sous le quota du Cas 3 (2500m CPU / 1536Mi). Total mesure : **1050m / 960Mi** en requests, **2000m / 1344Mi** en limits. Le tableau de dimensionnement complet et la justification (strategie `Recreate`, mesures `kubectl top pods`) sont dans la synthese de l'[ADR](ADR/ADR.md) et dans [k8s/RESOURCE_MEASUREMENTS.md](k8s/RESOURCE_MEASUREMENTS.md).

## CI/CD

`.github/workflows/ci.yml` (GitHub Actions) : lance les tests avec un seuil de **couverture 80 %**, puis construit et pousse les **quatre images** Docker Hub **multi-arch (amd64 / arm64)** (tag immuable `v1.0-seance5`) **uniquement sur `main` et uniquement si les tests passent** (`docker` depend de `test`). Secrets requis : `DOCKER_USERNAME`, `DOCKER_TOKEN`.

## Structure du depot

```
services/        preprocessing, inference, monitoring, frontend (code + Dockerfile)
k8s/             manifests Kubernetes (quota, limitrange, deployments, services) + RESOURCE_MEASUREMENTS.md
models/          artefacts .pkl + metadata + fiche de validation
scripts/         train_models, load_test, smoke_predict, run_load_challenge, validate_k8s_yaml
tests/           tests preprocessing, services, frontend, load_test
data/            churn.csv
results/         preuves du challenge de charge (seance 4)
ADR/ADR.md       Architecture Decision Record (document vivant)
SETUP.md         guide d'installation et de test pas-a-pas (macOS)
docker-compose.yml, Makefile, pyproject.toml
```

## Documentation

- [SETUP.md](SETUP.md) - installation et tests pas-a-pas (macOS).
- [ADR/ADR.md](ADR/ADR.md) - decisions d'architecture, dimensionnement, journal des evolutions.
- [k8s/RESOURCE_MEASUREMENTS.md](k8s/RESOURCE_MEASUREMENTS.md) - mesures de ressources et challenge de charge.
- [models/README.md](models/README.md) - fiche de validation des modeles.
- `results/` - resultats bruts du challenge de charge de la seance 4.

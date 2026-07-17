# Guide d'installation et de test - macOS

Ce guide part d'un Mac vierge et amene le systeme jusqu'a un deploiement complet et teste. Il propose deux chemins :

- **Chemin A - Docker Compose** : verification rapide en local, qui **construit les images sur votre Mac** (donc compatible Intel comme Apple Silicon).
- **Chemin B - Kubernetes / Minikube** : le deploiement complet sous contrainte de quota, avec le script de charge aux trois niveaux (c'est le scenario de correction).

Duree indicative : ~10 min pour le chemin A, ~15 min pour le chemin B (surtout les pulls d'images).

---

## 1. Prerequis (via Homebrew)

```bash
brew install --cask docker
brew install minikube kubectl uv
```

Lancer Docker Desktop et attendre qu'il soit demarre :

```bash
open -a Docker
```

Verifier que tout repond :

```bash
docker version
minikube version
kubectl version --client
uv --version
```

---

## 2. Cloner le projet

```bash
git clone <URL_DU_DEPOT>
cd WE_Churn
```

Les artefacts de modeles (`models/*.pkl`) et le dataset (`data/churn.csv`) sont **versionnes dans le depot** : aucun entrainement n'est necessaire pour deployer et tester.

---

## 3. Chemin A - Verification rapide en local (Docker Compose)

Le plus simple pour voir tout le systeme fonctionner. Les quatre images sont construites localement, puis lancees :

```bash
docker compose up --build
```

Quand les quatre services sont "healthy", ouvrir dans le navigateur :

- **Front de demonstration** : http://localhost:8080 (tirer un client au hasard, editer quelques champs, lancer une prediction, observer le monitoring en direct).
- API d'inference : http://localhost:8000 - Monitoring : http://localhost:8002/metrics

Tests en ligne de commande :

```bash
curl http://localhost:8000/health
curl http://localhost:8002/metrics
```

Test scripte (prediction et charge courte) - installe d'abord les dependances Python :

```bash
uv sync
uv run python scripts/smoke_predict.py --url http://localhost:8000/predict
uv run python scripts/load_test.py --case churn --level nominal --duration 30 --url http://localhost:8000/predict
```

Arreter la stack :

```bash
docker compose down
```

---

## 4. Chemin B - Deploiement complet sur Kubernetes (Minikube)

Deploiement de reference. Il utilise les images publiques Docker Hub (`omarraslan99/we-churn-*:v1.0-seance5`), donc **aucune construction n'est requise**. Les images sont **multi-arch (amd64 + arm64)**, donc compatibles Mac Intel comme Apple Silicon.

```bash
minikube start --cpus=4 --memory=6144 --driver=docker
minikube addons enable metrics-server
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/ -n projet-we
```

Attendre que les quatre deploiements soient prets :

```bash
kubectl rollout status deployment/preprocessing -n projet-we
kubectl rollout status deployment/monitoring -n projet-we
kubectl rollout status deployment/inference -n projet-we
kubectl rollout status deployment/frontend -n projet-we
kubectl get pods -n projet-we
```

Les quatre pods doivent etre en `STATUS Running`.

---

## 5. Tester le systeme deploye

### 5.1 Front de demonstration

```bash
minikube service frontend-svc -n projet-we --url
```

Laisser ce terminal **ouvert** (avec le driver Docker, le tunnel ne vit que tant que la commande tourne). Ouvrir l'URL affichee (type `http://127.0.0.1:xxxxx`) dans le navigateur.

### 5.2 Script de charge - les trois niveaux imposes

Dans un **autre** terminal, recuperer l'URL de l'inference :

```bash
minikube service inference-svc -n projet-we --url
```

Noter l'URL, installer les dependances une fois, puis lancer les trois paliers (remplacer `<INF_URL>` par l'URL notee) :

```bash
uv sync
uv run python scripts/load_test.py --case churn --level nominal --url <INF_URL>/predict
uv run python scripts/load_test.py --case churn --level charge  --url <INF_URL>/predict
uv run python scripts/load_test.py --case churn --level stress  --url <INF_URL>/predict
```

Chaque palier dure 5 minutes par defaut ; ajouter `--duration 60` pour raccourcir. Les resultats sont archives en JSON dans `results/load_tests/`.

### 5.3 Verifier le quota et la consommation reelle

```bash
kubectl describe resourcequota projet-quota -n projet-we
kubectl top pods -n projet-we
```

`kubectl top` peut mettre ~30 s a fournir des valeurs, le temps que metrics-server demarre.

---

## 6. Depannage (macOS)

- **Docker Desktop doit tourner** : `open -a Docker`, attendre l'icone stable dans la barre de menu.
- **`kubectl top` vide** : attendre ~30 s, ou re-verifier l'addon : `minikube addons enable metrics-server`.
- **Ports deja utilises** (8000 / 8002 / 8080) : arreter les autres services ou `docker compose down`.
- **Mac Apple Silicon (M1 / M2 / M3)** : les images Docker Hub sont **multi-arch (amd64 + arm64)**, donc le pull fonctionne nativement sur Apple Silicon comme sur Intel - aucune action particuliere. Si toutefois un probleme d'architecture survenait, deux solutions de repli :
  - **Le plus simple** : utiliser le **Chemin A (Docker Compose)**, qui construit les images pour l'architecture de votre Mac.
  - **Pour Kubernetes** : construire les images arm64 directement dans Minikube avec le tag des manifests, puis deployer (`IfNotPresent` les utilisera sans pull) :

    ```bash
    eval $(minikube docker-env)
    docker build -t omarraslan99/we-churn-preprocessing:v1.0-seance5 -f services/preprocessing/Dockerfile .
    docker build -t omarraslan99/we-churn-inference:v1.0-seance5     -f services/inference/Dockerfile .
    docker build -t omarraslan99/we-churn-monitoring:v1.0-seance5    -f services/monitoring/Dockerfile .
    docker build -t omarraslan99/we-churn-frontend:v1.0-seance5      -f services/frontend/Dockerfile .
    kubectl apply -f k8s/ -n projet-we
    ```

---

## 7. Nettoyage

```bash
kubectl delete -f k8s/ -n projet-we --ignore-not-found=true
minikube stop        # ou: minikube delete  (reinitialisation complete)
docker compose down
```

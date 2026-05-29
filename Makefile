.PHONY: help setup train test test-preprocessing test-services all ci-local run build stop logs smoke load-test load-test-nominal load-test-charge load-test-stress load-test-extreme challenge-nominal challenge-charge challenge-stress challenge-extreme challenge-full challenge-diagnostics challenge-compare monitoring-reset minikube-version minikube-start k8s-dry-run k8s-server-dry-run k8s-namespace k8s-deploy k8s-status k8s-rollout k8s-url k8s-top k8s-quota k8s-logs k8s-delete docker-push clean

UV ?= uv
PYTHON := $(UV) run python
URL ?= http://localhost:8000/predict
CASE ?= churn
LEVEL ?= nominal
DURATION ?= 30
CHALLENGE_DURATION ?= 300
RATE ?= 300
OUTPUT_DIR ?= results/load_tests
BEFORE ?=
AFTER ?=
COMPARE_OUTPUT ?= results/seance4/comparison.md
MONITORING_URL ?= http://localhost:8002
DOCKER_USER ?= omarraslan99
TAG ?= v0.1.0-seance3
NAMESPACE ?= projet-we
K8S_DIR ?= k8s

help:
	@echo "WE Churn - commandes disponibles"
	@echo ""
	@echo "  make setup              Installer les dependances avec uv"
	@echo "  make train              Entrainer les modeles et generer models/README.md"
	@echo "  make test               Lancer tous les tests avec couverture 80%"
	@echo "  make test-preprocessing Lancer uniquement les tests de preprocessing"
	@echo "  make test-services      Lancer uniquement les tests des services"
	@echo "  make all                setup + train + test"
	@echo "  make ci-local           Simuler la CI en local"
	@echo "  make build              Construire les images Docker Compose"
	@echo "  make run                Lancer les trois services avec Docker Compose"
	@echo "  make stop               Arreter les services Docker Compose"
	@echo "  make logs               Afficher les logs Docker Compose"
	@echo "  make smoke              Tester POST /predict sur URL=$(URL)"
	@echo "  make load-test          Lancer le script de charge court"
	@echo "  make load-test-nominal  Lancer 10 req/min avec archivage JSON"
	@echo "  make load-test-charge   Lancer 50 req/min avec archivage JSON"
	@echo "  make load-test-stress   Lancer le stress test churn 150 req/min"
	@echo "  make challenge-full     Lancer nominal + charge + stress avec collecte kubectl"
	@echo "  make challenge-compare  Generer un tableau avant/apres"
	@echo "  make monitoring-reset   Remettre a zero le monitoring local"
	@echo "  make minikube-version   Verifier Minikube"
	@echo "  make minikube-start     Demarrer Minikube avec les ressources recommandees"
	@echo "  make k8s-dry-run        Valider les YAML Kubernetes et le quota hors-ligne"
	@echo "  make k8s-server-dry-run Valider les manifests avec kubectl quand Minikube tourne"
	@echo "  make k8s-deploy         Deployer les manifests Kubernetes"
	@echo "  make k8s-status         Afficher kubectl get all"
	@echo "  make k8s-url            Recuperer l'URL Minikube de inference-svc"
	@echo "  make k8s-top            Afficher kubectl top pods"
	@echo "  make docker-push DOCKER_USER=<user>  Tagger et pousser les images"

setup:
	$(UV) sync

train:
	$(PYTHON) scripts/train_models.py

test:
	$(UV) run pytest --cov

test-preprocessing:
	$(UV) run pytest tests/test_preprocessing.py -q --no-cov

test-services:
	$(UV) run pytest tests/test_services.py -q --no-cov

all: setup train test

ci-local: setup train test build

build:
	docker compose build

run:
	docker compose up --build

stop:
	docker compose down

logs:
	docker compose logs -f

smoke:
	$(PYTHON) scripts/smoke_predict.py --url $(URL)

load-test:
	$(PYTHON) scripts/load_test.py --case $(CASE) --level $(LEVEL) --duration $(DURATION) --url $(URL) --output-dir $(OUTPUT_DIR)

load-test-nominal:
	$(PYTHON) scripts/load_test.py --case churn --level nominal --duration $(DURATION) --url $(URL) --output-dir $(OUTPUT_DIR)

load-test-charge:
	$(PYTHON) scripts/load_test.py --case churn --level charge --duration $(DURATION) --url $(URL) --output-dir $(OUTPUT_DIR)

load-test-stress:
	$(PYTHON) scripts/load_test.py --case churn --level stress --duration $(DURATION) --url $(URL) --output-dir $(OUTPUT_DIR)

load-test-extreme:
	$(PYTHON) scripts/load_test.py --case churn --level extreme --rate $(RATE) --duration $(DURATION) --url $(URL) --output-dir $(OUTPUT_DIR)

challenge-nominal:
	$(PYTHON) scripts/run_load_challenge.py --level nominal --duration $(CHALLENGE_DURATION) --url $(URL) --namespace $(NAMESPACE) --reset-monitoring

challenge-charge:
	$(PYTHON) scripts/run_load_challenge.py --level charge --duration $(CHALLENGE_DURATION) --url $(URL) --namespace $(NAMESPACE) --reset-monitoring

challenge-stress:
	$(PYTHON) scripts/run_load_challenge.py --level stress --duration $(CHALLENGE_DURATION) --url $(URL) --namespace $(NAMESPACE) --reset-monitoring

challenge-extreme:
	$(PYTHON) scripts/run_load_challenge.py --level extreme --rate $(RATE) --duration $(CHALLENGE_DURATION) --url $(URL) --namespace $(NAMESPACE) --reset-monitoring

challenge-full: challenge-nominal challenge-charge challenge-stress

challenge-diagnostics:
	$(PYTHON) scripts/run_load_challenge.py --level $(LEVEL) --duration 1 --url $(URL) --namespace $(NAMESPACE)

challenge-compare:
	$(PYTHON) scripts/compare_load_results.py --before $(BEFORE) --after $(AFTER) --output $(COMPARE_OUTPUT)

monitoring-reset:
	$(PYTHON) -c "import requests; print(requests.post('$(MONITORING_URL)/reset', timeout=5).json())"

minikube-version:
	minikube version

minikube-start:
	minikube start --cpus=4 --memory=6144 --driver=docker
	minikube addons enable metrics-server

k8s-dry-run:
	$(PYTHON) scripts/validate_k8s_yaml.py

k8s-server-dry-run:
	kubectl apply --dry-run=client -f $(K8S_DIR)/ -n $(NAMESPACE)

k8s-namespace:
	kubectl apply -f $(K8S_DIR)/00-namespace.yaml

k8s-deploy: k8s-namespace
	kubectl apply -f $(K8S_DIR)/ -n $(NAMESPACE)

k8s-status:
	kubectl get all -n $(NAMESPACE)

k8s-rollout:
	kubectl rollout status deployment/preprocessing -n $(NAMESPACE)
	kubectl rollout status deployment/monitoring -n $(NAMESPACE)
	kubectl rollout status deployment/inference -n $(NAMESPACE)

k8s-url:
	minikube service inference-svc -n $(NAMESPACE) --url

k8s-top:
	kubectl top pods -n $(NAMESPACE)

k8s-quota:
	kubectl describe resourcequota -n $(NAMESPACE)

k8s-logs:
	kubectl logs -n $(NAMESPACE) -l app=inference --tail=100

k8s-delete:
	kubectl delete -f $(K8S_DIR)/ -n $(NAMESPACE) --ignore-not-found=true

docker-push:
	docker tag we-churn-preprocessing:0.1.0 $(DOCKER_USER)/we-churn-preprocessing:$(TAG)
	docker tag we-churn-inference:0.1.0 $(DOCKER_USER)/we-churn-inference:$(TAG)
	docker tag we-churn-monitoring:0.1.0 $(DOCKER_USER)/we-churn-monitoring:$(TAG)
	docker push $(DOCKER_USER)/we-churn-preprocessing:$(TAG)
	docker push $(DOCKER_USER)/we-churn-inference:$(TAG)
	docker push $(DOCKER_USER)/we-churn-monitoring:$(TAG)

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(path, ignore_errors=True) for path in ['.pytest_cache', 'htmlcov']]; [p.unlink() for p in pathlib.Path('.').glob('.coverage*') if p.is_file()]"
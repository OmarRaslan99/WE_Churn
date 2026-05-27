.PHONY: help setup train test test-preprocessing test-services all run build stop logs smoke load-test load-test-stress minikube-version minikube-start docker-push clean

UV ?= uv
PYTHON := $(UV) run python
URL ?= http://localhost:8000/predict
CASE ?= churn
LEVEL ?= nominal
DURATION ?= 30
DOCKER_USER ?=
TAG ?= v0.1.0-seance2

help:
	@echo "WE Churn - commandes disponibles"
	@echo ""
	@echo "  make setup              Installer les dependances avec uv"
	@echo "  make train              Entrainer les modeles et generer models/README.md"
	@echo "  make test               Lancer tous les tests avec couverture 80%"
	@echo "  make test-preprocessing Lancer uniquement les tests de preprocessing"
	@echo "  make test-services      Lancer uniquement les tests des services"
	@echo "  make all                setup + train + test"
	@echo "  make build              Construire les images Docker Compose"
	@echo "  make run                Lancer les trois services avec Docker Compose"
	@echo "  make stop               Arreter les services Docker Compose"
	@echo "  make logs               Afficher les logs Docker Compose"
	@echo "  make smoke              Tester POST /predict sur URL=$(URL)"
	@echo "  make load-test          Lancer le script de charge court"
	@echo "  make load-test-stress   Lancer le stress test churn 150 req/min"
	@echo "  make minikube-version   Verifier Minikube"
	@echo "  make minikube-start     Demarrer Minikube avec les ressources recommandees"
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
	$(PYTHON) scripts/load_test.py --case $(CASE) --level $(LEVEL) --duration $(DURATION) --url $(URL)

load-test-stress:
	$(PYTHON) scripts/load_test.py --case churn --level stress --url $(URL)

minikube-version:
	minikube version

minikube-start:
	minikube start --cpus=4 --memory=6144 --driver=docker

docker-push:
	$(PYTHON) -c "import sys; sys.exit(0 if '$(DOCKER_USER)' else 'Set DOCKER_USER=<dockerhub-user>')"
	docker tag we-churn-preprocessing:0.1.0 $(DOCKER_USER)/we-churn-preprocessing:$(TAG)
	docker tag we-churn-inference:0.1.0 $(DOCKER_USER)/we-churn-inference:$(TAG)
	docker tag we-churn-monitoring:0.1.0 $(DOCKER_USER)/we-churn-monitoring:$(TAG)
	docker push $(DOCKER_USER)/we-churn-preprocessing:$(TAG)
	docker push $(DOCKER_USER)/we-churn-inference:$(TAG)
	docker push $(DOCKER_USER)/we-churn-monitoring:$(TAG)

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(path, ignore_errors=True) for path in ['.pytest_cache', 'htmlcov']]; [p.unlink() for p in pathlib.Path('.').glob('.coverage*') if p.is_file()]"
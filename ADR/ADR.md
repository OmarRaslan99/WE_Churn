# Architecture Decision Record vivant - Cas 3 : Prediction de churn et recommandation d'offre

**Statut :** vivant, a mettre a jour a chaque evolution structurante du projet  
**Derniere mise a jour :** 2026-05-29 (Seance 4 - challenge de charge execute et correction deployee)  
**Portee :** choix d'architecture, decisions remplacees, implementation, validation locale, Kubernetes et CI/CD

## Contexte et choix du cas d'usage

Nous avons choisi le **cas 3 : prediction de churn et recommandation d'offre**. Ce choix est adapte au quota impose de **2500m CPU** et **1.5 Gi de memoire**, car il repose sur des donnees tabulaires legeres et sur des modeles peu volumineux. Le dataset principal sera **Telco Customer Churn IBM**, compose d'environ 7043 clients et 21 variables dans un CSV d'environ 1 Mo, disponible publiquement sur Kaggle, UCI ou GitHub. Pour le modele de recommandation, nous genererons un dataset synthetique de 5000 lignes avec 5 categories d'offres fictives a partir des caracteristiques du dataset initial.

Le besoin metier est d'identifier les clients a risque de resiliation et de proposer une offre en moins de 200 ms. Le risque principal n'est donc pas la taille des donnees, mais la tenue en charge, notamment au niveau **stress** du script fourni, soit **150 req/min**. Un service Flask mono-threade pouvant saturer a ce debit, le service d'inference devra etre lance avec plusieurs workers et ajuste apres mesure.

## Architecture retenue

L'architecture respectera les trois services imposes : **preprocessing**, **inference** et **monitoring**, tous containerises et deployes dans le namespace `projet-we`. Le script de charge appellera le service expose `inference-svc` via `minikube service inference-svc -n projet-we --url`. L'endpoint public sera `POST /predict`; il recevra un JSON contenant les colonnes du dataset Telco sans `Churn` ni `customerID`, puis retournera une reponse de type `{"churn_probability": 0.74, "recommended_offer": "remise_tarifaire"}`.

Le service d'inference recevra la requete externe, appellera le service `preprocessing-svc` via le DNS interne Kubernetes pour valider et normaliser les donnees, puis executera la prediction de churn et la recommandation d'offre. Les services communiqueront via des objets `Service` de type `ClusterIP`, afin d'eviter toute dependance a `localhost` ou aux adresses IP ephemeres des pods. Le service de monitoring enregistrera au minimum le volume de requetes, les latences, les erreurs et les predictions principales, afin de rester exploitable pendant les tests de charge.

Le premier modele est un modele tabulaire leger. L'option initiale etait **XGBoost ou Random Forest** ; la V1 implemente finalement **RandomForestClassifier avec scikit-learn**, car cette solution est simple a containeriser, suffisante pour le TP, compatible avec les tests et plus prudente pour la taille des images. Le deuxieme modele est un classifieur multi-classes pour recommander une offre parmi 5 categories. Nous choisissons de charger ces deux modeles dans le meme service d'inference. Cette decision evite un quatrieme service Kubernetes, economise un environnement Python supplementaire, reduit les `requests` CPU/memoire et supprime un appel HTTP interne entre deux modeles. Le compromis est un couplage plus fort : les deux modeles seront redeployes et scales ensemble. Sous un quota de 1.5 Gi, ce compromis est acceptable.

## Dimensionnement initial et quota

Le dimensionnement ci-dessous est une estimation de seance 1. Il sera ajuste apres les premieres mesures avec `kubectl top pods`, mais il montre que la somme des `requests` reste sous le quota du cas 3.

| Service         |    Requests CPU | Requests memoire | Justification                             |
| --------------- | --------------: | ---------------: | ----------------------------------------- |
| Preprocessing   |            300m |            192Mi | Transformations tabulaires legeres        |
| Inference       |           1200m |            512Mi | Deux modeles legers et 2 a 4 workers HTTP |
| Monitoring      |            150m |            128Mi | Agregation de metriques                   |
| **Total** | **1650m** |  **832Mi** | Sous le quota                             |
| **Marge** |  **850m** |  **704Mi** | Quota restant sur 2500m / 1536Mi          |

Cette repartition laisse environ 34 % de marge CPU et 46 % de marge memoire sur les `requests`. Les `limits` seront fixees apres mesure, en visant environ 120 a 130 % du pic observe sous charge normale, tout en restant compatibles avec le `ResourceQuota`. Si le niveau stress montre du throttling CPU sur l'inference, la correction prioritaire sera d'ajuster le nombre de workers ou de redistribuer les ressources depuis les services moins consommateurs.

## Strategie de deploiement et CI/CD

Nous retenons une strategie **Recreate** pour la premiere version. Un `RollingUpdate` avec `maxSurge: 1` sur le service d'inference demanderait temporairement un pod supplementaire de 1200m CPU et 512Mi. La marge memoire de 704Mi serait suffisante, mais la marge CPU de 850m ne couvrirait pas les 1200m requis. Le nouveau pod risquerait donc de rester en `Pending`. `Recreate` evite ce blocage au prix d'un court downtime, acceptable dans ce TP et plus robuste sur une machine inconnue lors de la correction.

Le pipeline CI/CD sera implemente avec **GitHub Actions**. Ce choix est justifie par son integration native au depot GitHub et par la gestion securisee des secrets Docker Hub. Le pipeline executera les tests avec un seuil de couverture de 80 %, bloquera le build si les tests echouent, puis construira et poussera les images Docker uniquement en cas de succes.

## Validation prevue

Les modeles seront entraines hors Minikube, puis documentes dans `models/README.md` avec le dataset utilise, la metrique principale, la taille de l'artefact et le temps d'inference local. Les seances suivantes valideront l'architecture avec `docker-compose up --build`, puis avec `kubectl apply -f k8s/ -n projet-we`. Les tests nominal, charge et stress mesureront le taux de succes HTTP 200, la latence moyenne, le P95, les erreurs et la consommation des pods. Si nous tentons le mode extreme, le point de rupture et la recuperation du systeme seront documentes dans `STRESS_TEST.md`.

## Journal des evolutions et decisions remplacees

Cette section transforme l'ADR en document vivant. Toute nouvelle tache structurante doit ajouter une entree ici : ce qui a ete fait, pourquoi, ce qui a ete remplace, et comment la decision sera verifiee.

### 2026-05-26 - ADR initial et fusion avec la version du binome

L'ADR initial a ete construit a partir de `Docs/TP.md`, `Docs/Cours.md`, `Docs/Grille de notation.md`, `Docs/Challenge stress test.md` et du script de charge. Une version alternative fournie par le binome proposait un `RollingUpdate` valide sur la seule marge memoire. Ce raisonnement a ete remplace par un calcul CPU + memoire : avec `1200m` CPU demandes par l'inference et seulement `850m` de marge CPU estimee, un `maxSurge: 1` peut bloquer le nouveau pod en `Pending`. La decision finale retient donc `Recreate` pour l'inference tant que des mesures reelles ne prouvent pas que `RollingUpdate` tient dans le quota.

Le deuxieme modele a ete maintenu dans le service d'inference principal. L'alternative d'un quatrieme service reste plus decouplee, mais elle ajoute un environnement Python, des `requests` supplementaires et un appel reseau interne. Sous `1.5 Gi`, le couplage est accepte.

### 2026-05-27 - Seance 2 : entrainement, services, Docker Compose et tests

L'environnement projet a ete standardise avec `uv` via `pyproject.toml` et `uv.lock`, afin de rendre l'installation reproductible. Le dataset IBM telecharge utilise le schema enrichi avec `CustomerID`, `Churn Label`, `Churn Value`, `Churn Score` et `Churn Reason`, alors que le script fourni mentionne plutot `customerID` et `Churn`. Le preprocessing a donc ete concu pour ignorer les deux familles de colonnes identifiantes/cibles et eviter toute fuite de cible vers le modele.

FastAPI a ete retenu pour les trois services au lieu d'un service Flask generique, car il facilite les endpoints `/health`, les tests avec `TestClient` et la validation du contrat HTTP. Trois services ont ete implementes : `preprocessing` expose `POST /preprocess`, `inference` expose `POST /predict`, et `monitoring` expose `POST /events` ainsi que `/metrics` et `/summary`. Le monitoring est volontairement en memoire pour la V1 : c'est suffisant pour la seance 2 et le stress test local, mais il pourra etre remplace par un stockage plus robuste si le besoin apparait.

Les artefacts generes sont `models/churn_pipeline.pkl`, `models/offer_pipeline.pkl` et `models/model_metadata.json`. Les resultats locaux actuels sont : churn accuracy `0.748`, F1 `0.6235`, ROC-AUC `0.8383`; recommandation accuracy `0.814`; temps d'inference local moyen `0.576 ms` par ligne. Ces valeurs remplacent l'estimation abstraite de la seance 1 et sont documentees dans `models/README.md`.

Docker Compose a ete ajoute pour lancer les trois services localement. La validation locale a confirme que `/predict` renvoie HTTP 200 avec `churn_probability` et `recommended_offer`, que le monitoring recoit les evenements, et qu'un test de charge court du script fourni obtient 100 % de succes. Un blocage externe a ete observe pendant `docker compose up --build` : Docker Hub a renvoye `429 Too Many Requests` lors du pull de `python:3.12-slim`. Ce n'est pas une decision d'architecture ; la mitigation est `docker login` ou relance apres expiration de la limite.

Les tests sont executes avec `pytest` et `pytest-cov`. La couverture actuelle est `80.35 %`, donc le seuil TP de `80 %` est atteint. Les cibles partielles `make test-preprocessing` et `make test-services` ont ete corrigees pour ne pas appliquer le seuil global de couverture lorsqu'on lance seulement un sous-ensemble.

### 2026-05-27 - Makefile comme point d'entree reproductible

Un `Makefile` a ete ajoute pour regrouper les commandes de travail et de correction : `make setup`, `make train`, `make test`, `make run`, `make smoke`, `make load-test`, `make docker-push`. Cette decision remplace les commandes eparses du README par une interface unique, plus simple pour le binome et pour l'enseignant apres un `git clone`. Le README conserve les commandes detaillees, mais le Makefile devient le point d'entree privilegie.

### 2026-05-28 - Seance 3 : Kubernetes, quota et CI/CD

Les manifests Kubernetes ont ete ajoutes dans `k8s/`. Le namespace cible est `projet-we`. Le quota du cas 3 est encode dans `k8s/quota.yaml` : `2500m` CPU et `1536Mi` memoire pour requests et limits. `k8s/limitrange.yaml` ajoute des valeurs par defaut et des bornes par conteneur pour eviter des pods sans ressources explicites.

Les services internes `preprocessing-svc` et `monitoring-svc` restent en `ClusterIP`. `inference-svc` est en `NodePort` afin que `minikube service inference-svc -n projet-we --url` retourne directement une URL utilisable par `scripts/load_test.py`. Les variables Kubernetes de l'inference sont alignees avec Docker Compose : `PREPROCESSING_URL=http://preprocessing-svc:8001`, `MONITORING_URL=http://monitoring-svc:8002`, `MODEL_DIR=/app/models`, `CHURN_THRESHOLD=0.5`.

Les valeurs Kubernetes initiales sont maintenant plus completes que l'estimation ADR de seance 1, car elles incluent aussi les limits : preprocessing `300m/192Mi` requests et `500m/256Mi` limits, inference `1200m/512Mi` requests et `1500m/640Mi` limits, monitoring `150m/128Mi` requests et `250m/192Mi` limits. Le total est `1650m CPU` et `832Mi` en requests, `2250m CPU` et `1088Mi` en limits. La marge restante est donc `850m/704Mi` sur requests et `250m/448Mi` sur limits. Ces valeurs restent provisoires jusqu'aux vraies mesures `kubectl top pods`.

Un validateur hors-ligne `scripts/validate_k8s_yaml.py` a ete ajoute, car `kubectl apply --dry-run=client` tente tout de meme de joindre le cluster pour reconnaitre les types Kubernetes. La cible `make k8s-dry-run` verifie donc la syntaxe YAML, les champs obligatoires et la somme des ressources sans cluster actif. La cible `make k8s-server-dry-run` reste disponible quand Minikube tourne.

Le workflow `.github/workflows/ci.yml` a ete ajoute. Il execute `uv sync --frozen`, regenere les modeles, lance `uv run pytest --cov`, puis construit et pousse les images Docker Hub uniquement sur `main` et uniquement si les tests passent. Les secrets requis sont `DOCKER_USERNAME` et `DOCKER_TOKEN`. Les avertissements VS Code sur ces secrets ne bloquent pas le projet : ils disparaitront lorsque les secrets seront definis dans GitHub Actions.

### 2026-05-29 - Seance 4 : instrumentation du challenge de charge

La seance 4 exige des preuves exploitables sous charge : resultats du script enseignant, releves `kubectl top pods` toutes les 30 secondes, events Kubernetes, logs, restarts et tableau avant/apres correction. Le script `scripts/load_test.py` conserve donc son usage initial, mais archive maintenant chaque execution en JSON dans `results/load_tests/` avec timestamps, codes HTTP, latences moyenne/P95/max et metadata d'execution. Les colonnes cible/id du dataset churn enrichi sont aussi ignorees pendant le test de charge, comme dans le preprocessing et le smoke test.

Le monitoring a ete enrichi sans ajouter de nouveau service : les evenements recoivent un timestamp UTC, les metriques exposent P95, codes HTTP, succes, erreurs, uptime et un export limite des evenements recents. Un endpoint de reset permet d'isoler chaque palier nominal, charge ou stress. L'alternative d'ajouter Prometheus/Grafana ou une base persistante a ete rejetee pour cette V1, car elle augmenterait le nombre de pods et la consommation sous le quota `2500m CPU / 1536Mi`.

Un orchestrateur `scripts/run_load_challenge.py` automatise le protocole Minikube : lancement d'un palier, collecte parallele `kubectl top pods`, snapshots Kubernetes avant/apres, logs et metriques monitoring. Le vrai challenge reste local sur Minikube, car GitHub Actions standard ne donne pas les mesures `kubectl top pods` du namespace du TP. La pipeline integre toutefois un test de charge court via Docker Compose afin de detecter les regressions API/Docker : smoke test puis charge nominale courte avec seuils de succes et P95, et upload des resultats comme artifacts.

La correction de performance n'est pas encore figee dans l'ADR, car elle doit etre choisie apres les vraies mesures. La regle retenue est d'appliquer une seule correction mesurable au palier critique, par exemple ajuster les workers Gunicorn, redistribuer les ressources entre services ou limiter un comportement monitoring couteux, puis de verifier a nouveau le quota et de relancer uniquement le niveau problematique.

### 2026-05-29 - Seance 4 : correction de performance apres mesures reelles

Les trois paliers ont ete executes sur Minikube (Docker driver, namespace `projet-we`) avec `kubectl port-forward`. Resultats avant correction :

- Nominal (10 req/min, 300s) : 50/50 req, 100%, avg 0.181s, P95 0.297s, CPU inference pic 40m.
- Charge (50 req/min, 300s) : 250/250 req, 100%, avg 0.200s, P95 0.375s, CPU inference pic 187m.
- Stress (150 req/min, 300s) : 748/748 req, 100%, avg 0.202s, P95 0.375s, CPU inference pic **417m**.

Goulot identifie : sous stress, l'inference consommait 417m CPU alors que le `request` etait surdimensionne a 1200m. Avec seulement 2 workers Gunicorn, les bursts creaient une file d'attente causant une latence max de 1.609s. La memoire restait stable (275Mi max), donc le goulot etait CPU/concurrence.

Correction choisie (une seule, conformement au protocole) : augmenter les workers Gunicorn de 2 a **4** via override `command` dans `k8s/inference.yaml`, et right-sizer les ressources inference a `request 500m / limit 1000m`. Le scaling horizontal (replicas=2) a ete rejete car il aurait depasse le quota CPU.

Resultats apres correction - palier stress (150 req/min, 300s) : 748/748 req, 100%, avg **0.158s** (-22%), P95 **0.313s** (-17%), CPU pic 408m. La quota check confirme 950m/1750m (< 2500m). La correction est validee et conservee en production Minikube.

### Points resolus en Seance 4

Les images Docker Hub `omarraslan99/we-churn-*:v0.1.0-seance3` sont utilisees avec `imagePullPolicy: IfNotPresent`. Le challenge de charge complet a ete execute sur Minikube le 2026-05-29. Les mesures `kubectl top pods` sont reportees dans `k8s/RESOURCE_MEASUREMENTS.md`. Les ressources inference ont ete ajustees apres mesures reelles (request 500m, limit 1000m, 4 workers). Le quota final utilise 950m/1750m CPU requests/limits, bien sous les 2500m autorises. Le tableau avant/apres est dans `results/seance4/comparison_stress.md`.

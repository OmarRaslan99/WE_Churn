# Architecture Decision Record - Cas 3 : Prediction de churn et recommandation d'offre

## Contexte et choix du cas d'usage

Nous avons choisi le **cas 3 : prediction de churn et recommandation d'offre**. Ce choix est adapte au quota impose de **2500m CPU** et **1.5 Gi de memoire**, car il repose sur des donnees tabulaires legeres et sur des modeles peu volumineux. Le dataset principal sera **Telco Customer Churn IBM**, compose d'environ 7043 clients et 21 variables dans un CSV d'environ 1 Mo, disponible publiquement sur Kaggle, UCI ou GitHub. Pour le modele de recommandation, nous genererons un dataset synthetique de 5000 lignes avec 5 categories d'offres fictives a partir des caracteristiques du dataset initial.

Le besoin metier est d'identifier les clients a risque de resiliation et de proposer une offre en moins de 200 ms. Le risque principal n'est donc pas la taille des donnees, mais la tenue en charge, notamment au niveau **stress** du script fourni, soit **150 req/min**. Un service Flask mono-threade pouvant saturer a ce debit, le service d'inference devra etre lance avec plusieurs workers et ajuste apres mesure.

## Architecture retenue

L'architecture respectera les trois services imposes : **preprocessing**, **inference** et **monitoring**, tous containerises et deployes dans le namespace `projet-TRIGRAMME`. Le script de charge appellera le service expose `inference-svc` via `minikube service inference-svc -n projet-TRIGRAMME --url`. L'endpoint public sera `POST /predict`; il recevra un JSON contenant les colonnes du dataset Telco sans `Churn` ni `customerID`, puis retournera une reponse de type `{"churn_probability": 0.74, "recommended_offer": "remise_tarifaire"}`.

Le service d'inference recevra la requete externe, appellera le service `preprocessing-svc` via le DNS interne Kubernetes pour valider et normaliser les donnees, puis executera la prediction de churn et la recommandation d'offre. Les services communiqueront via des objets `Service` de type `ClusterIP`, afin d'eviter toute dependance a `localhost` ou aux adresses IP ephemeres des pods. Le service de monitoring enregistrera au minimum le volume de requetes, les latences, les erreurs et les predictions principales, afin de rester exploitable pendant les tests de charge.

Le premier modele sera un modele tabulaire leger, **XGBoost ou Random Forest**, entraine hors Minikube et versionne dans `models/`. Le deuxieme modele sera un classifieur multi-classes pour recommander une offre parmi 5 categories. Nous choisissons de charger ces deux modeles dans le meme service d'inference. Cette decision evite un quatrieme service Kubernetes, economise un environnement Python supplementaire, reduit les `requests` CPU/memoire et supprime un appel HTTP interne entre deux modeles. Le compromis est un couplage plus fort : les deux modeles seront redeployes et scales ensemble. Sous un quota de 1.5 Gi, ce compromis est acceptable.

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

Les modeles seront entraines hors Minikube, puis documentes dans `models/README.md` avec le dataset utilise, la metrique principale, la taille de l'artefact et le temps d'inference local. Les seances suivantes valideront l'architecture avec `docker-compose up --build`, puis avec `kubectl apply -f k8s/ -n projet-TRIGRAMME`. Les tests nominal, charge et stress mesureront le taux de succes HTTP 200, la latence moyenne, le P95, les erreurs et la consommation des pods. Si nous tentons le mode extreme, le point de rupture et la recuperation du systeme seront documentes dans `STRESS_TEST.md`.

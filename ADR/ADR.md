# Architecture Decision Record - Cas 3 : Prediction de churn et recommandation d'offre

**Statut :** propose pour la seance 1  
**Date :** 2026-05-26  
**Contexte :** TP orchestration machine learning sur Minikube sous contrainte de ressources

## Contexte

Nous choisissons le cas 3, prediction de churn et recommandation d'offre, car il correspond le mieux au quota impose de **2500m CPU** et **1.5 Gi de memoire**. Le dataset Telco Customer Churn IBM contient environ 7043 clients et 21 variables dans un CSV d'environ 1 Mo, ce qui rend le preprocessing et le chargement des donnees compatibles avec un cluster Minikube contraint. Le besoin metier est d'identifier les clients a risque de resiliation et de proposer une offre en moins de 200 ms. Le risque principal n'est donc pas la taille des donnees, mais la latence sous charge et le dimensionnement du service d'inference a 150 requetes par minute.

Le systeme respectera l'architecture minimale imposee : un service de preprocessing, un service d'inference principal et un service de monitoring, tous containerises et deployes dans le namespace `projet-TRIGRAMME`. Le script de charge appellera le service d'inference expose par Kubernetes via `minikube service inference-svc -n projet-TRIGRAMME --url`, puis enverra des requetes `POST /predict` avec les colonnes du dataset Telco sans `Churn` ni `customerID`. La reponse attendue sera un JSON de la forme `{"churn_probability": 0.74, "recommended_offer": "remise_tarifaire"}`.

## Decision

Le modele principal sera un modele tabulaire leger, XGBoost ou Random Forest, entraine hors Minikube et versionne dans `models/`. Il produira un score de churn entre 0 et 1. Le modele de recommandation sera un classifieur multi-classes entraine sur 5000 lignes synthetiques generees a partir du dataset Telco, avec 5 categories d'offres fictives. Les deux modeles seront charges dans le meme service d'inference. Cette decision evite un quatrieme service Kubernetes, reduit les communications inter-services, economise des `requests` CPU et memoire, et diminue la latence ajoutee par un appel HTTP interne. La contrepartie est un couplage plus fort : les deux modeles seront redeployes ensemble et ne pourront pas scaler independamment. Dans le cadre de ce TP et du quota de 1.5 Gi, ce compromis est acceptable.

Le service de preprocessing sera separe afin de respecter l'architecture imposee. Il recevra les donnees brutes, validera les champs, appliquera les transformations necessaires et transmettra un payload normalise au service d'inference via le DNS interne Kubernetes, par exemple `http://inference-svc`. Le service de monitoring enregistrera le volume de requetes, les latences, le taux d'erreur et les predictions principales. Il devra rester lisible pendant les tests de charge, car un monitoring muet ferait perdre les points associes.

Le pipeline CI/CD sera implemente avec GitHub Actions. Ce choix est coherent avec le depot GitHub, permet de stocker les identifiants Docker Hub dans les secrets du depot et permet de bloquer explicitement le build et le push des images si les tests echouent. Le pipeline executera les tests avec un seuil de couverture de 80 %, construira les images Docker uniquement si les tests passent, puis poussera les images versionnees sur Docker Hub.

## Dimensionnement initial

Le dimensionnement ci-dessous est une estimation de seance 1. Il sera verifie puis ajuste avec `kubectl top pods` pendant les seances suivantes. Les valeurs sont volontairement inferieures au quota afin de conserver une marge pour les pics, les redemarrages et les tests de charge.

| Service | Requests CPU | Requests memoire | Justification |
| --- | ---: | ---: | --- |
| Preprocessing | 300m | 192Mi | Transformations tabulaires legeres, surtout CPU |
| Inference | 1200m | 512Mi | Deux modeles legers, workers HTTP, objectif 150 req/min |
| Monitoring | 150m | 128Mi | Agregation de metriques et exposition simple |
| **Total** | **1650m** | **832Mi** | Sous le quota cas 3 |
| **Marge** | **850m** | **704Mi** | Quota restant : 2500m CPU et 1536Mi memoire |

Cette repartition laisse environ 34 % de marge CPU et 46 % de marge memoire sur les `requests`. Les `limits` seront fixes apres mesure, en visant environ 120 a 130 % du pic observe sous charge normale, tout en garantissant que la somme des limites reste compatible avec le `ResourceQuota`. Si les mesures montrent un throttling CPU sur l'inference, la premiere correction sera de reduire la reservation du preprocessing ou du monitoring avant d'augmenter le nombre de workers.

## Strategie de deploiement

La strategie retenue pour la premiere version est **Recreate**. Avec l'estimation ci-dessus, un `RollingUpdate` de l'inference avec `maxSurge: 1` ajouterait temporairement un pod d'inference de 1200m CPU et 512Mi. La marge memoire de 704Mi permettrait ce surge, mais la marge CPU de 850m ne le permettrait pas. Le nouveau pod risquerait donc de rester en `Pending` a cause du quota. `Recreate` evite ce blocage en supprimant l'ancien pod avant de creer le nouveau. Le cout est un court downtime, acceptable pour ce TP, et ce choix est plus robuste sur une machine inconnue clonee par l'enseignant.

## Consequences et validation

Cette architecture privilegie la reproductibilite et le respect du quota plutot qu'une scalabilite maximale. Elle est adaptee au cas churn car les modeles sont legers et parce que le point critique est le debit HTTP a 150 req/min. Le service d'inference sera lance avec plusieurs workers, par exemple 2 a 4 au depart, afin d'eviter un comportement Flask mono-threade. Le nombre exact sera ajuste pendant les tests de charge a partir de la latence moyenne, du P95, du taux de succes HTTP 200 et de la consommation observee avec `kubectl top pods`.

La validation suivra le protocole du TP. En seance 2, les modeles seront entraines hors Minikube, les artefacts seront places dans `models/` et documentes dans `models/README.md` avec dataset, metrique, taille et temps d'inference local. En seance 3, les manifests `k8s/quota.yaml`, `k8s/limitrange.yaml`, `preprocessing.yaml`, `inference.yaml` et `monitoring.yaml` devront permettre un deploiement complet avec une seule commande. En seance 4, les niveaux nominal, charge et stress seront mesures avec le script fourni, puis la correction la plus impactante sera appliquee et mesuree avant/apres. Le stress test extreme restera optionnel ; si nous le tentons, nous documenterons le dernier palier avec plus de 80 % de succes, le point de rupture et la recuperation du systeme dans `STRESS_TEST.md`.
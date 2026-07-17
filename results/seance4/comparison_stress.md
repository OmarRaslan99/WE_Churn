# Comparaison charge - palier stress avant / apres correction

**Cas 3 - Prediction de churn** | Namespace `projet-we` | Hote `DESKTOP-L584EQM`
Palier compare : **stress (150 req/min, 300s)**, releve avant puis apres la correction unique de la seance 4.

- Avant : `2026-05-29T16:33:40Z` (run `20260529_183338_stress`, inference `649d9975cb`, 2 workers)
- Apres : `2026-05-29T16:45:12Z` (run `20260529_184508_stress`, inference `8675649fbc`, 4 workers)

## Tableau comparatif

| Metrique                         |  Avant |  Apres | Changement          | Lecture                          |
| -------------------------------- | -----: | -----: | ------------------- | -------------------------------- |
| Requetes envoyees                |    748 |    748 | =                   | Meme charge injectee             |
| Succes HTTP 200                  |    748 |    748 | =                   | Aucun echec avant/apres          |
| Taux de succes                   |   100% |   100% | =                   | Stable                           |
| Latence **moyenne**              | 0.202s | 0.158s | **-0.044s (-21.8%)** | Amelioration (metrique de fond)  |
| Latence **P95**                  | 0.375s | 0.313s | **-0.062s (-16.5%)** | Amelioration (metrique de fond)  |
| Latence max (client)             | 1.609s |  8.0s  | +6.39s              | Outlier unique - voir analyse    |
| Latence max (monitoring serveur) | 1.349s | 7.892s | +6.54s              | Confirme cote serveur            |
| Restarts / OOMKill / throttle    |  0/0/0 |  0/0/0 | =                   | Aucun incident ressource         |

La correction ameliore la **distribution** de la latence (moyenne -21.8 %, P95 -16.5 %), qui reflete le
comportement en regime etabli. La seule degradation apparente est la **latence max**, portee par un
**unique evenement de queue** (1 requete sur 748, soit le 99.87e centile) analyse plus bas ; elle n'est pas
representative du comportement du service sous charge.

## Analyse

### Correction appliquee

Une seule correction, conformement au protocole. Le service d'inference passe de **2 a 4 workers Gunicorn**
(override `command` dans `k8s/inference.yaml`) et ses ressources sont right-sizees apres mesure :
`requests.cpu` de **1200m a 500m**, `limits.cpu` de **1500m a 1000m**. Le scaling horizontal (`replicas: 2`)
a ete rejete car il aurait double les `requests` CPU de l'inference et depasse le quota de 2500m du cas 3.

### Indices Kubernetes observes avant correction

Avant correction, sous stress (150 req/min), les releves `kubectl top pods` toutes les 30 s montrent un pic
inference a **417m CPU** (memoire stable a 275Mi), soit seulement ~35 % du `request` de 1200m alors surdimensionne.
Le pod ne subit ni restart, ni OOMKill, ni event de throttling : le goulot n'est donc pas une penurie de
ressources allouees mais la **concurrence applicative**. Avec 2 workers Gunicorn, les rafales de requetes
creent une file d'attente qui se traduit par des pointes de latence (max client 1.609s, max serveur 1.349s)
alors que la moyenne reste basse. Le diagnostic est donc CPU/concurrence, pas memoire.

### Justification mecanique de l'effet mesure

Doubler le nombre de workers (2 -> 4) double la capacite de traitement concurrent du service. A debit constant
(150 req/min), la profondeur moyenne de la file par worker diminue, donc le temps d'attente d'une requete avant
d'etre servie baisse. C'est exactement ce qu'on observe : la moyenne passe de 0.202s a 0.158s (-21.8 %) et le
P95, plus sensible aux pics de file, de 0.375s a 0.313s (-16.5 %). Le right-sizing CPU (request 1200m -> 500m)
n'a pas degrade la performance car le pic reel (408m apres correction) reste sous la nouvelle `limit` de 1000m :
la place liberee dans le quota est recuperee sans perte, ce qui rend le systeme plus honnete vis-a-vis du
`ResourceQuota` (total 950m/1750m requests/limits, bien sous 2500m).

### Explication de la latence max de 8s (outlier)

La latence max grimpe a 8.0s cote client **et 7.892s cote monitoring serveur**. Comme la latence serveur est
mesuree a l'interieur du worker (autour de `predict_payload`), cet outlier correspond a **du temps de traitement
reel dans un worker**, et non a de l'attente dans le tunnel `kubectl port-forward` ni a la file Gunicorn (qui ne
seraient pas comptabilises cote serveur).

Cause identifiee : **chargement a froid des modeles par worker (cold start)**. Le service charge les artefacts de
maniere paresseuse et par processus (`get_artifacts()` peuple un global `_artifacts` initialise a `None` dans
chaque worker), et Gunicorn est lance **sans `--preload`**. Les 4 workers sont donc des processus independants ;
un worker qui n'a jamais recu de sonde `/health` reste froid jusqu'a sa premiere requete `/predict`, ou il doit
alors depickler les deux `RandomForest` (`churn_pipeline.pkl` 2.5 Mo + `offer_pipeline.pkl` 3.8 Mo) au sein meme
de l'appel. Cette premiere requete paie donc l'integralite du cout de chargement (~8s).

Preuve directe dans `results/seance4/20260529_184508_stress/after/events.txt` :

```
Warning  Unhealthy  pod/inference-8675649fbc-l9j9w
Readiness probe failed: Get "http://10.244.0.8:8000/health": context deadline exceeded
```

La sonde `/health` (timeout 5s) a elle-meme expire pendant que `get_artifacts()` chargeait les modeles : cela
confirme qu'un chargement a froid depasse plusieurs secondes. L'outlier de 8s sur `/predict` est le meme
phenomene, sur un worker reste froid jusqu'a sa premiere requete de charge.

Ce cout est **paye une seule fois par worker** : il apparait donc uniquement sur la latence max (99.87e centile,
1 requete sur 748) et n'affecte ni la moyenne ni le P95, qui s'ameliorent tous deux. Il n'est pas non plus
attribuable a la correction : celle-ci n'a modifie que le nombre de workers et les ressources CPU, ce qui ne peut
pas creer un stall de 8s sur une requete tout en abaissant simultanement moyenne et P95. Le run "avant" a suivi
le meme tunnel `localhost` mais n'a, par chance de routage, pas exhibe de worker froid pendant la fenetre de mesure.

### Conclusion et point de rupture

Au palier stress, le systeme ne casse pas : 100 % de HTTP 200, aucun restart, aucun OOMKill, CPU inference
408m sous une `limit` de 1000m et memoire stable a ~529Mi. Le point de rupture n'est donc pas atteint a
150 req/min ; il devra etre recherche au niveau `extreme` (bonus, `STRESS_TEST.md`). La correction est validee
sur les metriques de fond (moyenne -21.8 %, P95 -16.5 %) et conservee en production Minikube.

### Amelioration identifiee (documentee, non appliquee pour respecter la regle "une seule correction")

Le cold-start peut etre elimine en lancant Gunicorn avec **`--preload`** : les modeles sont alors charges une
seule fois dans le processus maitre avant le fork, et partages par les 4 workers via copy-on-write. Double
benefice : plus aucune requete ne paie le chargement (disparition de l'outlier de 8s) et l'empreinte memoire
n'est plus dupliquee 4 fois, ce qui est directement pertinent sous le quota memoire de 1.5 Gi du cas 3. Une
alternative complementaire est un warm-up explicite au demarrage (appel interne de `get_artifacts()` avant
d'accepter du trafic) ou l'usage d'un `startupProbe` couvrant la duree de chargement.

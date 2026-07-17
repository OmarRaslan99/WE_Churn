# Seance 3 - Mesures Kubernetes et justification des ressources

Ce document sert a conserver les mesures `kubectl top pods` demandees pour la seance 3. Les valeurs initiales ci-dessous proviennent de l'ADR et doivent etre ajustees apres une mesure reelle sur Minikube.

## Quota cas 3

| Ressource | Quota |
| --- | ---: |
| requests.cpu | 2500m |
| requests.memory | 1536Mi |
| limits.cpu | 2500m |
| limits.memory | 1536Mi |

## Valeurs initiales declarees

| Service | Requests CPU | Requests memoire | Limits CPU | Limits memoire |
| --- | ---: | ---: | ---: | ---: |
| preprocessing | 300m | 192Mi | 500m | 256Mi |
| inference | 1200m | 512Mi | 1500m | 640Mi |
| monitoring | 150m | 128Mi | 250m | 192Mi |
| **Total** | **1650m** | **832Mi** | **2250m** | **1088Mi** |
| **Marge restante** | **850m** | **704Mi** | **250m** | **448Mi** |

Les sommes restent sous le quota du cas 3. La strategie `Recreate` est conservee pour l'inference afin d'eviter un surge CPU temporaire pendant un RollingUpdate.

## Commandes de mesure

```powershell
make minikube-start
make k8s-deploy
make k8s-rollout
make k8s-status
make k8s-top
make k8s-quota
```

Recuperer ensuite l'URL de l'API :

```powershell
make k8s-url
```

Puis lancer une charge nominale de 5 minutes :

```powershell
uv run python scripts/load_test.py --case churn --level nominal --url <URL_MINIKUBE>/predict
```

Pendant le test, relever les pics toutes les 30 secondes :

```powershell
kubectl top pods -n projet-we
```

## Mesures observees

| Date | Niveau | Pod | CPU observe | Memoire observee | Commentaire |
| --- | --- | --- | ---: | ---: | --- |
| 2026-05-29 | repos | preprocessing | 3m | 62Mi | idle avant charge |
| 2026-05-29 | repos | inference | 9m | 272Mi | idle avant charge |
| 2026-05-29 | repos | monitoring | 3m | 33Mi | idle avant charge |
| 2026-05-29 | nominal (10 req/min) | preprocessing | 4m | 62Mi | pic nominal |
| 2026-05-29 | nominal (10 req/min) | inference | 40m | 273Mi | pic nominal |
| 2026-05-29 | nominal (10 req/min) | monitoring | 4m | 33Mi | pic nominal |
| 2026-05-29 | charge (50 req/min) | preprocessing | 7m | 62Mi | pic charge |
| 2026-05-29 | charge (50 req/min) | inference | 187m | 273Mi | pic charge |
| 2026-05-29 | charge (50 req/min) | monitoring | 6m | 33Mi | pic charge |
| 2026-05-29 | stress (150 req/min) | preprocessing | 11m | 62Mi | pic stress avant correction |
| 2026-05-29 | stress (150 req/min) | inference | 417m | 275Mi | pic stress avant correction |
| 2026-05-29 | stress (150 req/min) | monitoring | 10m | 33Mi | pic stress avant correction |

## Regle d'ajustement

Apres mesure, fixer approximativement :

- `requests` a 70-80 % du pic observe sous charge nominale.
- `limits` a 120-130 % du pic observe.
- La somme finale doit rester sous 2500m CPU et 1536Mi memoire pour requests et limits.

## Seance 4 - Protocole de charge

Les tests seance 4 doivent etre lances contre l'URL Minikube de `inference-svc` :

```powershell
$url = "<URL_MINIKUBE>/predict"
make challenge-nominal URL=$url
make challenge-charge URL=$url
make challenge-stress URL=$url
```

Chaque execution cree un dossier `results/seance4/<timestamp>_<niveau>/` contenant :

- le resultat JSON du test de charge ;
- les echantillons `kubectl top pods` toutes les 30 secondes ;
- les sorties `kubectl get`, `describe`, `events`, `resourcequota` ;
- les logs recents des services ;
- les metriques monitoring avant/apres.

## Seance 4 - Mesures avant correction

| Date | Niveau | Success rate | Latence avg | Latence P95 | Pod critique | CPU max | Memoire max | Restarts | Observation |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| 2026-05-29 | nominal (10 req/min) | 100% | 0.181s | 0.297s | inference | 40m | 273Mi | 0 | Aucune saturation |
| 2026-05-29 | charge (50 req/min) | 100% | 0.200s | 0.375s | inference | 187m | 273Mi | 0 | CPU monte, latence stable |
| 2026-05-29 | stress (150 req/min) | 100% | 0.202s | 0.375s | inference | 417m | 275Mi | 0 | CPU pic 417m, max 1.609s - goulot identifie |

## Seance 4 - Correction appliquee

- Symptome principal observe : sous stress (150 req/min), inference CPU pic a 417m (35% du request de 1200m). Avec 2 workers Gunicorn, les bursts creent une file d'attente, causant des pointes de latence (max 1.609s).
- Correction choisie : augmentation de 2 a **4 workers Gunicorn** (via `command` override dans `k8s/inference.yaml`) + right-sizing CPU request de 1200m a **500m** et limit de 1500m a **1000m**.
- Alternative rejetee : scaling horizontal (replicas=2) - impossible dans le quota actuel (depasserait 2500m CPU requests).
- Verification quota : `uv run python scripts/validate_k8s_yaml.py` => 950m requests / 1750m limits (OK < 2500m).

## Seance 4 - Mesures apres correction

| Niveau relance | Success rate avant | Success rate apres | P95 avant | P95 apres | CPU max avant | CPU max apres | Conclusion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| stress (150 req/min) | 100% | 100% | 0.375s | 0.313s | 417m | 408m | P95 -16.5%, avg -21.8% : amelioration confirmee |

## Seance 5 - Ajout du service frontend (demo)

Un 4e service `frontend` (passerelle FastAPI servant la page de demo et faisant proxy vers `inference-svc` et `monitoring-svc`) a ete ajoute a la demande de l'enseignant. Dimensionne au plus juste, il reste largement dans le quota.

| Service | Requests CPU | Requests memoire | Limits CPU | Limits memoire |
| --- | ---: | ---: | ---: | ---: |
| preprocessing | 300m | 192Mi | 500m | 256Mi |
| inference | 500m | 512Mi | 1000m | 704Mi |
| monitoring | 150m | 128Mi | 250m | 192Mi |
| **frontend** | **100m** | **128Mi** | **250m** | **192Mi** |
| **Total** | **1050m** | **960Mi** | **2000m** | **1344Mi** |
| **Quota** | **2500m** | **1536Mi** | **2500m** | **1536Mi** |
| **Marge restante** | **1450m** | **576Mi** | **500m** | **192Mi** |

Verification : `uv run python scripts/validate_k8s_yaml.py` => Requests 1050m / 960Mi, Limits 2000m / 1344Mi, quota OK. Point d'attention a mentionner a l'oral : la marge sur les **limits memoire** descend a 192Mi (le poste le plus contraint apres cet ajout).
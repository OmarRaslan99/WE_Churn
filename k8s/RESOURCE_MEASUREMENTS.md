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
kubectl top pods -n projet-TRIGRAMME
```

## Mesures observees

| Date | Niveau | Pod | CPU observe | Memoire observee | Commentaire |
| --- | --- | --- | ---: | ---: | --- |
| A completer | repos | preprocessing |  |  |  |
| A completer | repos | inference |  |  |  |
| A completer | repos | monitoring |  |  |  |
| A completer | nominal | preprocessing |  |  |  |
| A completer | nominal | inference |  |  |  |
| A completer | nominal | monitoring |  |  |  |

## Regle d'ajustement

Apres mesure, fixer approximativement :

- `requests` a 70-80 % du pic observe sous charge nominale.
- `limits` a 120-130 % du pic observe.
- La somme finale doit rester sous 2500m CPU et 1536Mi memoire pour requests et limits.
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
K8S_DIR = ROOT / "k8s"
QUOTA_CPU_M = 2500
QUOTA_MEMORY_MI = 1536


def main() -> None:
    documents = load_documents()
    validate_required_fields(documents)
    totals = sum_deployment_resources(documents)
    print("Kubernetes YAML syntax: OK")
    print(
        "Requests total: "
        f"{totals['requests_cpu_m']}m CPU, {totals['requests_memory_mi']}Mi memory"
    )
    print(
        "Limits total: "
        f"{totals['limits_cpu_m']}m CPU, {totals['limits_memory_mi']}Mi memory"
    )
    if totals["requests_cpu_m"] > QUOTA_CPU_M or totals["limits_cpu_m"] > QUOTA_CPU_M:
        raise SystemExit("CPU quota exceeded in k8s manifests")
    if totals["requests_memory_mi"] > QUOTA_MEMORY_MI or totals["limits_memory_mi"] > QUOTA_MEMORY_MI:
        raise SystemExit("Memory quota exceeded in k8s manifests")
    print("Resource quota check: OK")


def load_documents() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in sorted(K8S_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as file:
            for document in yaml.safe_load_all(file):
                if document:
                    document["__file"] = str(path.relative_to(ROOT))
                    documents.append(document)
    if not documents:
        raise SystemExit("No Kubernetes YAML documents found")
    return documents


def validate_required_fields(documents: list[dict[str, Any]]) -> None:
    for document in documents:
        for field in ("apiVersion", "kind", "metadata"):
            if field not in document:
                raise SystemExit(f"Missing {field} in {document.get('__file', 'unknown file')}")
        if "name" not in document["metadata"]:
            raise SystemExit(f"Missing metadata.name in {document['__file']}")


def sum_deployment_resources(documents: list[dict[str, Any]]) -> dict[str, int]:
    totals = {
        "requests_cpu_m": 0,
        "requests_memory_mi": 0,
        "limits_cpu_m": 0,
        "limits_memory_mi": 0,
    }
    for document in documents:
        if document.get("kind") != "Deployment":
            continue
        containers = document["spec"]["template"]["spec"].get("containers", [])
        for container in containers:
            resources = container.get("resources", {})
            requests = resources.get("requests", {})
            limits = resources.get("limits", {})
            totals["requests_cpu_m"] += parse_cpu_m(requests.get("cpu", "0"))
            totals["requests_memory_mi"] += parse_memory_mi(requests.get("memory", "0Mi"))
            totals["limits_cpu_m"] += parse_cpu_m(limits.get("cpu", "0"))
            totals["limits_memory_mi"] += parse_memory_mi(limits.get("memory", "0Mi"))
    return totals


def parse_cpu_m(value: str) -> int:
    value = str(value)
    if value.endswith("m"):
        return int(value[:-1])
    return int(float(value) * 1000)


def parse_memory_mi(value: str) -> int:
    value = str(value)
    if value.endswith("Mi"):
        return int(value[:-2])
    if value.endswith("Gi"):
        return int(float(value[:-2]) * 1024)
    return int(int(value) / (1024 * 1024))


if __name__ == "__main__":
    main()
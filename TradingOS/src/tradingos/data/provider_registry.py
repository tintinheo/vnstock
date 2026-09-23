"""Read and validate the versioned provider-governance registry."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).parents[3] / "config" / "providers.v1.json"
ADMISSION_STATUSES = {"CANDIDATE", "ADMITTED", "SUSPENDED", "REFERENCE_ONLY", "REJECTED"}


def load_provider_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Load the registry, rejecting incomplete or ambiguous provider records."""
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("schema_version") != 1 or not registry.get("registry_version"):
        raise ValueError("unsupported or missing provider registry version")
    providers = registry.get("providers")
    if not isinstance(providers, list) or not providers:
        raise ValueError("provider registry must contain providers")
    seen: set[str] = set()
    required = {"id", "version", "role", "capabilities", "admission_status", "evidence_ref"}
    for provider in providers:
        missing = required - provider.keys()
        if missing:
            raise ValueError(f"provider record missing: {sorted(missing)}")
        if provider["id"] in seen:
            raise ValueError(f"duplicate provider id: {provider['id']}")
        seen.add(provider["id"])
        if provider["admission_status"] not in ADMISSION_STATUSES:
            raise ValueError(f"invalid admission status for {provider['id']}")
        if not isinstance(provider["capabilities"], list) or not provider["capabilities"]:
            raise ValueError(f"provider {provider['id']} has no capabilities")
    return registry


def admitted_providers(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return only explicitly admitted providers; candidates never auto-promote."""
    source = registry or load_provider_registry()
    return [item for item in source["providers"] if item["admission_status"] == "ADMITTED"]

"""Validated, deterministic models for configuration state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


class StateValidationError(ValueError):
    """Raised when an environment state document is invalid."""


def canonical_json(value: Any) -> str:
    """Return stable JSON for hashing, plans, and drift comparison."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True, slots=True)
class Resource:
    """A portable configuration resource and its dependency references."""

    resource_id: str
    kind: str
    name: str
    depends_on: tuple[str, ...] = ()
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Resource":
        required = ("id", "kind", "name")
        missing = [key for key in required if not value.get(key)]
        if missing:
            raise StateValidationError(
                f"Resource is missing required fields: {', '.join(missing)}"
            )

        dependencies = tuple(dict.fromkeys(value.get("depends_on", [])))
        if value["id"] in dependencies:
            raise StateValidationError(
                f"Resource {value['id']} cannot depend on itself."
            )

        config = value.get("config", {})
        if not isinstance(config, dict):
            raise StateValidationError(
                f"Resource {value['id']} config must be an object."
            )

        return cls(
            resource_id=str(value["id"]),
            kind=str(value["kind"]),
            name=str(value["name"]),
            depends_on=dependencies,
            config=config,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.resource_id,
            "kind": self.kind,
            "name": self.name,
            "depends_on": list(self.depends_on),
            "config": self.config,
        }

    @property
    def digest(self) -> str:
        payload = canonical_json(self.to_dict()).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class EnvironmentState:
    """A named snapshot of resources exported from one environment."""

    environment: str
    resources: dict[str, Resource]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EnvironmentState":
        environment = str(value.get("environment", "")).strip()
        if not environment:
            raise StateValidationError("Environment name is required.")

        raw_resources = value.get("resources")
        if not isinstance(raw_resources, list):
            raise StateValidationError("Resources must be a list.")

        resources: dict[str, Resource] = {}
        for item in raw_resources:
            if not isinstance(item, dict):
                raise StateValidationError("Every resource must be an object.")
            resource = Resource.from_dict(item)
            if resource.resource_id in resources:
                raise StateValidationError(
                    f"Duplicate resource id: {resource.resource_id}"
                )
            resources[resource.resource_id] = resource

        return cls(environment=environment, resources=resources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "resources": [
                self.resources[key].to_dict() for key in sorted(self.resources)
            ],
        }


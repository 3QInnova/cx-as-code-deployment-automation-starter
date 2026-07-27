"""Post-promotion verification and drift reporting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cxdeploy.graph import DependencyGraph
from cxdeploy.models import EnvironmentState


class DriftStatus(StrEnum):
    MATCH = "match"
    MISSING = "missing"
    DIFFERENT = "different"


@dataclass(frozen=True, slots=True)
class DriftResult:
    resource_id: str
    status: DriftStatus
    expected_digest: str
    actual_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "status": self.status.value,
            "expected_digest": self.expected_digest,
            "actual_digest": self.actual_digest,
        }


def verify_state(
    expected: EnvironmentState,
    actual: EnvironmentState,
    selected: list[str] | None = None,
) -> list[DriftResult]:
    """Compare live/exported state with the dependency-complete expectation."""

    graph = DependencyGraph(expected.resources)
    ordered_ids = graph.topological_order(selected)
    results: list[DriftResult] = []

    for resource_id in ordered_ids:
        expected_resource = expected.resources[resource_id]
        actual_resource = actual.resources.get(resource_id)
        if actual_resource is None:
            status = DriftStatus.MISSING
            actual_digest = None
        elif actual_resource.digest != expected_resource.digest:
            status = DriftStatus.DIFFERENT
            actual_digest = actual_resource.digest
        else:
            status = DriftStatus.MATCH
            actual_digest = actual_resource.digest

        results.append(
            DriftResult(
                resource_id=resource_id,
                status=status,
                expected_digest=expected_resource.digest,
                actual_digest=actual_digest,
            )
        )

    return results


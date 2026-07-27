"""Safe promotion planning, rollback capture, and in-memory application."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cxdeploy.graph import DependencyGraph
from cxdeploy.models import EnvironmentState, Resource


class OperationType(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    NO_CHANGE = "no_change"


@dataclass(frozen=True, slots=True)
class PlanOperation:
    sequence: int
    operation: OperationType
    resource: Resource
    previous_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "operation": self.operation.value,
            "resource": self.resource.to_dict(),
            "source_digest": self.resource.digest,
            "previous_digest": self.previous_digest,
        }


@dataclass(frozen=True, slots=True)
class PromotionPlan:
    source_environment: str
    target_environment: str
    operations: tuple[PlanOperation, ...]
    rollback_snapshot: dict[str, dict[str, Any] | None]

    @property
    def changes(self) -> tuple[PlanOperation, ...]:
        return tuple(
            operation
            for operation in self.operations
            if operation.operation is not OperationType.NO_CHANGE
        )

    def to_dict(self) -> dict[str, Any]:
        counts = {
            operation.value: sum(
                1 for item in self.operations if item.operation is operation
            )
            for operation in OperationType
        }
        return {
            "source_environment": self.source_environment,
            "target_environment": self.target_environment,
            "summary": counts,
            "operations": [item.to_dict() for item in self.operations],
            "rollback_snapshot": self.rollback_snapshot,
        }


class PromotionPlanner:
    """Build a deterministic promotion plan without implicit deletion."""

    def __init__(
        self,
        source: EnvironmentState,
        target: EnvironmentState,
    ) -> None:
        self.source = source
        self.target = target
        self.graph = DependencyGraph(source.resources)

    def build(self, selected: list[str] | None = None) -> PromotionPlan:
        ordered_ids = self.graph.topological_order(selected)
        operations: list[PlanOperation] = []
        rollback: dict[str, dict[str, Any] | None] = {}

        for sequence, resource_id in enumerate(ordered_ids, start=1):
            source_resource = self.source.resources[resource_id]
            target_resource = self.target.resources.get(resource_id)

            if target_resource is None:
                operation = OperationType.CREATE
                previous_digest = None
                rollback[resource_id] = None
            elif target_resource.digest != source_resource.digest:
                operation = OperationType.UPDATE
                previous_digest = target_resource.digest
                rollback[resource_id] = target_resource.to_dict()
            else:
                operation = OperationType.NO_CHANGE
                previous_digest = target_resource.digest

            operations.append(
                PlanOperation(
                    sequence=sequence,
                    operation=operation,
                    resource=source_resource,
                    previous_digest=previous_digest,
                )
            )

        return PromotionPlan(
            source_environment=self.source.environment,
            target_environment=self.target.environment,
            operations=tuple(operations),
            rollback_snapshot=rollback,
        )


def apply_in_memory(
    target: EnvironmentState,
    plan: PromotionPlan,
) -> EnvironmentState:
    """Apply a plan to an immutable snapshot for tests and dry runs."""

    resources = dict(target.resources)
    for operation in plan.changes:
        resources[operation.resource.resource_id] = operation.resource
    return EnvironmentState(environment=target.environment, resources=resources)


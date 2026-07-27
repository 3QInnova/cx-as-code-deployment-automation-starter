from __future__ import annotations

import unittest

from cxdeploy.graph import (
    DependencyCycleError,
    DependencyGraph,
    MissingDependencyError,
)
from cxdeploy.models import EnvironmentState, Resource
from cxdeploy.planner import OperationType, PromotionPlanner, apply_in_memory
from cxdeploy.verify import DriftStatus, verify_state


def resource(
    resource_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    version: int = 1,
) -> Resource:
    return Resource(
        resource_id=resource_id,
        kind="synthetic",
        name=resource_id,
        depends_on=depends_on,
        config={"version": version},
    )


class DependencyGraphTests(unittest.TestCase):
    def test_discovers_recursive_dependencies_in_order(self) -> None:
        resources = {
            "a": resource("a"),
            "b": resource("b", depends_on=("a",)),
            "c": resource("c", depends_on=("b",)),
            "unrelated": resource("unrelated"),
        }

        order = DependencyGraph(resources).topological_order(["c"])

        self.assertEqual(order, ["a", "b", "c"])

    def test_rejects_missing_dependency(self) -> None:
        with self.assertRaises(MissingDependencyError):
            DependencyGraph(
                {"flow": resource("flow", depends_on=("missing",))}
            )

    def test_rejects_dependency_cycle(self) -> None:
        graph = DependencyGraph(
            {
                "a": resource("a", depends_on=("b",)),
                "b": resource("b", depends_on=("a",)),
            }
        )

        with self.assertRaises(DependencyCycleError):
            graph.topological_order()


class PromotionPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = EnvironmentState(
            environment="development",
            resources={
                "shared": resource("shared"),
                "updated": resource("updated", version=2),
                "created": resource(
                    "created",
                    depends_on=("shared", "updated"),
                ),
            },
        )
        self.target = EnvironmentState(
            environment="production",
            resources={
                "shared": resource("shared"),
                "updated": resource("updated", version=1),
                "target-only": resource("target-only"),
            },
        )

    def test_plan_classifies_create_update_and_no_change(self) -> None:
        plan = PromotionPlanner(self.source, self.target).build()
        operations = {
            item.resource.resource_id: item.operation for item in plan.operations
        }

        self.assertEqual(operations["shared"], OperationType.NO_CHANGE)
        self.assertEqual(operations["updated"], OperationType.UPDATE)
        self.assertEqual(operations["created"], OperationType.CREATE)
        self.assertNotIn("target-only", operations)

    def test_plan_captures_rollback_state(self) -> None:
        plan = PromotionPlanner(self.source, self.target).build()

        self.assertIsNone(plan.rollback_snapshot["created"])
        self.assertEqual(
            plan.rollback_snapshot["updated"]["config"]["version"],
            1,
        )

    def test_selected_resource_includes_dependencies(self) -> None:
        plan = PromotionPlanner(self.source, self.target).build(["created"])
        ids = [item.resource.resource_id for item in plan.operations]

        self.assertEqual(ids, ["shared", "updated", "created"])

    def test_in_memory_apply_preserves_unselected_target_resources(self) -> None:
        plan = PromotionPlanner(self.source, self.target).build(["created"])
        applied = apply_in_memory(self.target, plan)

        self.assertIn("target-only", applied.resources)
        self.assertEqual(applied.resources["updated"].config["version"], 2)

    def test_post_apply_verification_matches(self) -> None:
        plan = PromotionPlanner(self.source, self.target).build(["created"])
        applied = apply_in_memory(self.target, plan)

        results = verify_state(self.source, applied, ["created"])

        self.assertTrue(all(item.status is DriftStatus.MATCH for item in results))

    def test_verification_detects_drift(self) -> None:
        results = verify_state(self.source, self.target, ["updated"])

        self.assertEqual(results[0].status, DriftStatus.DIFFERENT)


if __name__ == "__main__":
    unittest.main()


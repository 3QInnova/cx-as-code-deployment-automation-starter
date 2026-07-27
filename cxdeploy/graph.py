"""Recursive dependency discovery and deterministic ordering."""

from __future__ import annotations

from collections.abc import Iterable

from cxdeploy.models import Resource


class DependencyError(ValueError):
    """Base class for dependency graph failures."""


class MissingDependencyError(DependencyError):
    """Raised when a resource references an unavailable dependency."""


class DependencyCycleError(DependencyError):
    """Raised when resources contain a circular dependency."""


class DependencyGraph:
    """Dependency graph for portable configuration resources."""

    def __init__(self, resources: dict[str, Resource]) -> None:
        self.resources = resources
        self._validate_references()

    def _validate_references(self) -> None:
        for resource in self.resources.values():
            for dependency in resource.depends_on:
                if dependency not in self.resources:
                    raise MissingDependencyError(
                        f"{resource.resource_id} depends on missing {dependency}."
                    )

    def closure(self, selected: Iterable[str] | None = None) -> set[str]:
        """Return selected resources plus all recursive dependencies."""

        roots = set(selected or self.resources)
        unknown = roots.difference(self.resources)
        if unknown:
            raise MissingDependencyError(
                f"Selected resources do not exist: {', '.join(sorted(unknown))}"
            )

        discovered: set[str] = set()

        def visit(resource_id: str) -> None:
            if resource_id in discovered:
                return
            discovered.add(resource_id)
            for dependency in self.resources[resource_id].depends_on:
                visit(dependency)

        for root in sorted(roots):
            visit(root)
        return discovered

    def topological_order(
        self,
        selected: Iterable[str] | None = None,
    ) -> list[str]:
        """Return dependencies before consumers, rejecting cycles."""

        included = self.closure(selected)
        temporary: set[str] = set()
        permanent: set[str] = set()
        ordered: list[str] = []
        path: list[str] = []

        def visit(resource_id: str) -> None:
            if resource_id in permanent:
                return
            if resource_id in temporary:
                start = path.index(resource_id)
                cycle = path[start:] + [resource_id]
                raise DependencyCycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}"
                )

            temporary.add(resource_id)
            path.append(resource_id)
            for dependency in sorted(self.resources[resource_id].depends_on):
                if dependency in included:
                    visit(dependency)
            path.pop()
            temporary.remove(resource_id)
            permanent.add(resource_id)
            ordered.append(resource_id)

        for resource_id in sorted(included):
            visit(resource_id)
        return ordered


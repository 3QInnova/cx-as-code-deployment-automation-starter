"""Command-line interface for planning, exporting, and verifying promotions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cxdeploy.io import load_state, write_json
from cxdeploy.planner import PromotionPlanner
from cxdeploy.verify import DriftStatus, verify_state


def _selected(values: list[str] | None) -> list[str] | None:
    return values or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cxdeploy",
        description="Plan and verify dependency-aware configuration promotions.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Create a promotion plan.")
    plan.add_argument("--source", required=True)
    plan.add_argument("--target", required=True)
    plan.add_argument("--select", action="append")
    plan.add_argument("--out")

    export = subparsers.add_parser(
        "export-manifest",
        help="Export an ordered manifest for an API or Terraform adapter.",
    )
    export.add_argument("--source", required=True)
    export.add_argument("--select", action="append")
    export.add_argument("--out", required=True)

    verify = subparsers.add_parser("verify", help="Detect post-promotion drift.")
    verify.add_argument("--expected", required=True)
    verify.add_argument("--actual", required=True)
    verify.add_argument("--select", action="append")
    verify.add_argument("--out")
    return parser


def _emit(value: object, output: str | None) -> None:
    if output:
        write_json(output, value)
    else:
        print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "plan":
        source = load_state(args.source)
        target = load_state(args.target)
        plan = PromotionPlanner(source, target).build(_selected(args.select))
        _emit(plan.to_dict(), args.out)
        return 0

    if args.command == "export-manifest":
        source = load_state(args.source)
        planner = PromotionPlanner(
            source,
            type(source)(environment="empty-target", resources={}),
        )
        plan = planner.build(_selected(args.select))
        manifest = {
            "environment": source.environment,
            "ordered_resources": [
                {
                    "sequence": item.sequence,
                    "id": item.resource.resource_id,
                    "kind": item.resource.kind,
                    "digest": item.resource.digest,
                    "depends_on": list(item.resource.depends_on),
                    "config": item.resource.config,
                }
                for item in plan.operations
            ],
        }
        _emit(manifest, args.out)
        return 0

    if args.command == "verify":
        expected = load_state(args.expected)
        actual = load_state(args.actual)
        results = verify_state(expected, actual, _selected(args.select))
        payload = {
            "expected_environment": expected.environment,
            "actual_environment": actual.environment,
            "verified": all(item.status is DriftStatus.MATCH for item in results),
            "results": [item.to_dict() for item in results],
        }
        _emit(payload, args.out)
        return 0 if payload["verified"] else 2

    raise AssertionError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())


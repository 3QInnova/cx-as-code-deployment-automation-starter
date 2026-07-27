"""JSON document loading and atomic artifact writing."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from cxdeploy.models import EnvironmentState


def load_state(path: str | Path) -> EnvironmentState:
    with Path(path).open(encoding="utf-8") as handle:
        return EnvironmentState.from_dict(json.load(handle))


def write_json(path: str | Path, value: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


"""Connector #1: the demo source.

Reads a normalized snapshot straight from a JSON file (a realistic fake
practice). It needs no network, no credentials, no real tenant -- so Perikrone
runs end-to-end and produces a full report the moment it's cloned. It's also the
reference implementation every future connector (M365, Google Workspace, the
manual intake) is modeled on: do your system-specific work, return the
normalized shape.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import Connector, validate_snapshot

# Repo-root/data/demo_practice.json, resolved relative to this file.
_DEFAULT_DATA = (
    Path(__file__).resolve().parents[2] / "data" / "demo_practice.json"
)


class DemoConnector(Connector):
    name = "demo"

    def __init__(self, data_path: str | Path | None = None):
        self.data_path = Path(data_path) if data_path else _DEFAULT_DATA

    def collect(self) -> dict:
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"demo data not found at {self.data_path}"
            )
        snapshot = json.loads(self.data_path.read_text(encoding="utf-8"))
        snapshot.setdefault("source", self.name)
        validate_snapshot(snapshot)
        return snapshot

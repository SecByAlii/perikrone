"""Connector registry. New data sources register here; the CLI selects one by
its ``--source`` name. Everything below the registry is a swappable plug -- the
engine and checks never import from here."""

from __future__ import annotations

from .base import Connector, validate_snapshot
from .demo import DemoConnector
from .manual import ManualConnector
from .m365 import M365Connector

# name -> connector class. Add Google Workspace here as it lands.
REGISTRY: dict[str, type[Connector]] = {
    DemoConnector.name: DemoConnector,
    ManualConnector.name: ManualConnector,
    M365Connector.name: M365Connector,
}


def available_sources() -> list[str]:
    return sorted(REGISTRY)


def get_connector(name: str, **kwargs) -> Connector:
    try:
        cls = REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"unknown source '{name}'. Available: {', '.join(available_sources())}"
        ) from None
    return cls(**kwargs)


__all__ = [
    "Connector",
    "validate_snapshot",
    "DemoConnector",
    "ManualConnector",
    "M365Connector",
    "REGISTRY",
    "available_sources",
    "get_connector",
]

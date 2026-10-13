"""The connector contract.

A connector's only job: reach into one specific system, pull the relevant facts,
and return them in the single normalized shape the engine understands. The engine
never knows which connector produced the snapshot -- so adding Microsoft 365,
Google Workspace, or a guided manual intake is just a new subclass here. The
engine and the checks never change.

Normalized snapshot shape
-------------------------
{
    "practice_name": str,
    "source": str,                 # connector name, e.g. "demo"
    "collected_at": str,           # ISO-8601 timestamp (used for staleness)
    "security_defaults_enabled": bool | None,
    "legacy_auth_allowed": bool | None,
    "users": [
        {
            "id": str,
            "display_name": str,
            "email": str,
            "enabled": bool,                       # default True if absent
            "mfa_enabled": bool,
            "is_admin": bool,                      # holds full admin rights
            "account_type": "member" | "guest",   # default "member"
            "last_sign_in": str | None,            # ISO-8601, or None if never
        },
        ...
    ],
}

A field set to None means "this connector could not determine it," and checks
that depend on it will skip rather than guess.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

REQUIRED_SNAPSHOT_KEYS = {"practice_name", "source", "collected_at", "users"}


class Connector(ABC):
    """Base class for every data source."""

    #: short, stable identifier used on the command line (e.g. "demo", "m365").
    name: str = "connector"

    @abstractmethod
    def collect(self) -> dict:
        """Return a normalized snapshot (shape documented above)."""
        raise NotImplementedError


def validate_snapshot(snapshot: dict) -> None:
    """Fail loudly and early if a connector returns something malformed -- far
    better than a confusing error deep inside a check."""
    missing = REQUIRED_SNAPSHOT_KEYS - snapshot.keys()
    if missing:
        raise ValueError(
            f"snapshot is missing required key(s): {', '.join(sorted(missing))}"
        )
    if not isinstance(snapshot["users"], list):
        raise ValueError("snapshot 'users' must be a list")

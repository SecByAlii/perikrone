"""The common language every part of Perikrone speaks.

The engine evaluates *normalized facts* and emits `Finding` objects. Connectors
produce the facts; the report renders the findings. Nothing here knows or cares
which system (Microsoft 365, Google Workspace, a manual intake) the facts came
from -- that separation is what makes Perikrone adaptable to whatever a practice
runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    """Ranked worst-first. Higher value = more urgent, so sorting descending by
    severity puts the things that'll get a practice breached at the top."""

    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    INFO = 0

    @property
    def label(self) -> str:
        return self.name.capitalize()


@dataclass(frozen=True)
class HipaaControl:
    """A specific HIPAA Security Rule citation a finding maps to. This is the
    thing that turns 'you have a problem' into 'you are out of compliance with
    this exact rule,' which is what a practice actually needs to hear."""

    code: str   # e.g. "45 CFR 164.312(d)"
    name: str   # e.g. "Person or Entity Authentication"

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


@dataclass
class Finding:
    """One security gap, explained the way a non-technical practice manager can
    act on it."""

    check_id: str                      # stable id of the check that raised it
    title: str                         # short headline
    severity: Severity
    summary: str                       # one line: what was found
    detail: str                        # plain-English: why it's dangerous
    affected: list[str] = field(default_factory=list)   # accounts/items involved
    hipaa: list[HipaaControl] = field(default_factory=list)
    fix: list[str] = field(default_factory=list)        # ordered remediation steps
    fix_links: list[tuple[str, str]] = field(default_factory=list)  # (label, url)

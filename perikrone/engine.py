"""The brain. Runs every check against a normalized snapshot and collects the
findings. Knows nothing about data sources -- it's handed normalized facts and
reasons about them. That's the whole point of the engine/connector split."""

from __future__ import annotations

from dataclasses import dataclass, field

from .checks import ALL_CHECKS, CHECK_STEPS
from .findings import Finding, Severity


@dataclass
class AssessmentResult:
    practice_name: str
    source: str
    collected_at: str
    user_count: int
    findings: list[Finding] = field(default_factory=list)
    # Which admin console the practice uses, so fixes link to the right place.
    platform: str = "microsoft"          # "microsoft" | "google" | "other"
    admin_url: str | None = None          # used when platform == "other"

    def ranked(self) -> list[Finding]:
        """Findings worst-first -- the order they belong in a report."""
        return sorted(self.findings, key=lambda f: f.severity, reverse=True)

    def counts_by_severity(self) -> dict[Severity, int]:
        counts = {s: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity] += 1
        return counts

    @property
    def clean(self) -> bool:
        return not self.findings

    def score(self) -> int:
        """A 0-100 posture score. Starts at 100; each finding subtracts weight by
        severity. Blunt on purpose -- a practice that's wide open should see a
        number that makes them sit up."""
        penalty = sum(_SEVERITY_WEIGHT[f.severity] for f in self.findings)
        return max(0, 100 - penalty)

    def grade(self) -> str:
        s = self.score()
        for cutoff, letter in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
            if s >= cutoff:
                return letter
        return "F"


_SEVERITY_WEIGHT = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 12,
    Severity.MEDIUM: 6,
    Severity.LOW: 2,
    Severity.INFO: 0,
}


def assess(snapshot: dict) -> AssessmentResult:
    """Run the full check suite over one normalized snapshot."""
    result, _steps = assess_by_step(snapshot)
    return result


def assess_by_step(snapshot: dict) -> tuple[AssessmentResult, list[tuple[str, list[Finding]]]]:
    """Like assess(), but also returns per-check results in order -- what the live
    scan screen animates through, one step at a time."""
    steps: list[tuple[str, list[Finding]]] = []
    findings: list[Finding] = []
    for label, check in CHECK_STEPS:
        found = check(snapshot)
        steps.append((label, found))
        findings.extend(found)

    result = AssessmentResult(
        practice_name=snapshot.get("practice_name", "Unknown practice"),
        source=snapshot.get("source", "unknown"),
        collected_at=snapshot.get("collected_at", ""),
        user_count=len(snapshot.get("users", [])),
        findings=findings,
        platform=snapshot.get("platform") or "microsoft",
        admin_url=snapshot.get("admin_url"),
    )
    return result, steps

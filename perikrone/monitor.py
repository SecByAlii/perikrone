"""Monitoring + alerts — the final rung.

Compares a fresh scan against the previous one and raises alerts when posture
DEGRADES: a new gap appears, an existing one gets worse, or the score drops. This
is the engine behind scheduled "pings" — leave `run.py --watch` running (or
schedule it) and Perikrone tells you the moment a practice's security slips,
which is the whole point of continuous monitoring.

On a live connector these alerts are real. For the demo (static data), the
--simulate-drift switch introduces a realistic change so an alert can be shown.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .engine import AssessmentResult

_ALERT_LOG = Path(__file__).resolve().parent.parent / "reports" / "alerts.log"


@dataclass
class Alert:
    kind: str        # new | worsened | improved | resolved | score
    message: str
    degraded: bool   # True when this represents posture getting worse


def diff_results(prev: AssessmentResult, curr: AssessmentResult) -> list[Alert]:
    """What changed between two scans, as alerts."""
    alerts: list[Alert] = []
    prev_by = {f.check_id: f for f in prev.findings}
    curr_by = {f.check_id: f for f in curr.findings}

    for cid, f in curr_by.items():
        if cid not in prev_by:
            alerts.append(Alert(
                "new", f"NEW [{f.severity.label}] {f.title} — {f.summary}", True))
        else:
            was, now = len(prev_by[cid].affected), len(f.affected)
            if now > was:
                alerts.append(Alert(
                    "worsened", f"WORSENED — {f.title}: {was} -> {now} affected", True))
            elif now < was:
                alerts.append(Alert(
                    "improved", f"improved — {f.title}: {was} -> {now} affected", False))

    for cid, f in prev_by.items():
        if cid not in curr_by:
            alerts.append(Alert("resolved", f"resolved — {f.title}", False))

    delta = curr.score() - prev.score()
    if delta < 0:
        alerts.append(Alert(
            "score", f"Score dropped {abs(delta)} ({prev.score()} -> {curr.score()})", True))
    elif delta > 0:
        alerts.append(Alert(
            "score", f"score rose {delta} ({prev.score()} -> {curr.score()})", False))
    return alerts


def is_degradation(alerts: list[Alert]) -> bool:
    return any(a.degraded for a in alerts)


def summary_line(alerts: list[Alert]) -> str:
    degraded = [a.message for a in alerts if a.degraded]
    return "; ".join(degraded) if degraded else "posture changed"


def desktop_notify(title: str, message: str) -> None:
    """Best-effort macOS desktop notification; silently no-ops elsewhere."""
    if sys.platform != "darwin":
        return
    # ensure_ascii=False keeps real UTF-8 (e.g. the em-dash) instead of \uXXXX,
    # which AppleScript can't parse.
    msg = json.dumps(message, ensure_ascii=False)
    ttl = json.dumps(title, ensure_ascii=False)
    try:
        subprocess.run(
            ["osascript", "-e", f"display notification {msg} with title {ttl}"],
            check=False, timeout=5,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def log_alerts(result: AssessmentResult, alerts: list[Alert], path=None) -> None:
    path = Path(path) if path else _ALERT_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("a", encoding="utf-8") as fh:
        for a in alerts:
            if a.degraded:
                fh.write(f"{stamp}\t{result.practice_name}\t{a.message}\n")


def apply_demo_drift(snapshot: dict) -> dict:
    """DEMO ONLY: introduce a realistic posture drop so monitoring/alerts can be
    demonstrated against the static demo data -- an admin loses MFA and a new
    admin account with no MFA appears."""
    s = copy.deepcopy(snapshot)
    for u in s.get("users", []):
        if u.get("is_admin") and u.get("mfa_enabled"):
            u["mfa_enabled"] = False
            break
    s.setdefault("users", []).append({
        "id": "drift-admin",
        "display_name": "New IT Admin (just added)",
        "email": "newadmin@cypresseye.example",
        "enabled": True,
        "mfa_enabled": False,
        "is_admin": True,
        "account_type": "member",
        "last_sign_in": None,
    })
    return s

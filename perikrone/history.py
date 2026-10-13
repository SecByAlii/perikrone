"""Scan history + trend.

Records each assessment's score so the dashboard can show posture improving (or
slipping) over time -- the foundation the monitoring add-on will build on later.

Stored as JSON at data/scan_history.json (git-ignored). Per practice, a short
chronological list of lightweight entries: score, grade, finding count, and the
set of check ids that fired. Never any patient data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .engine import AssessmentResult

_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "scan_history.json"
_MAX = 50  # keep the most recent N entries per practice


def record(result: AssessmentResult, path=None) -> None:
    path = Path(path) if path else _DEFAULT
    store = _load(path)
    entries = store.setdefault(result.practice_name, [])
    entries.append({
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "score": result.score(),
        "grade": result.grade(),
        "total": len(result.findings),
        "checks": sorted({f.check_id for f in result.findings}),
    })
    del entries[:-_MAX]
    _save(path, store)


def history_for(practice_name: str, path=None) -> list:
    return _load(Path(path) if path else _DEFAULT).get(practice_name, [])


def clear(practice_name: str, path=None) -> None:
    path = Path(path) if path else _DEFAULT
    store = _load(path)
    if practice_name in store:
        del store[practice_name]
        _save(path, store)


def trend_for(practice_name: str, path=None) -> dict | None:
    """Points for the sparkline plus a delta vs. the previous scan. None if
    nothing has been recorded for this practice yet."""
    entries = history_for(practice_name, path)
    if not entries:
        return None
    points = [{"at": e["at"], "score": e["score"], "grade": e["grade"]}
              for e in entries]
    delta = None
    if len(entries) >= 2:
        prev, curr = entries[-2], entries[-1]
        prev_checks, curr_checks = set(prev["checks"]), set(curr["checks"])
        delta = {
            "score": curr["score"] - prev["score"],
            "resolved": len(prev_checks - curr_checks),
            "new": len(curr_checks - prev_checks),
        }
    return {"points": points, "delta": delta}


def _load(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

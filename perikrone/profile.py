"""The saved practice profile.

Remembers a practice's guided-assessment inputs — name, platform, admin URL,
system settings, and the account roster — so Perikrone pre-fills them every time
and the practice just edits the roster as staff come and go, then re-scans.

Stored as JSON at data/profile.json (git-ignored; it's real practice data, never
committed). One profile per install for now.
"""

from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "profile.json"


def load_profile(path=None):
    """Return the saved profile dict, or None if there isn't one yet."""
    p = Path(path) if path else _PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_profile(data: dict, path=None) -> None:
    p = Path(path) if path else _PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")

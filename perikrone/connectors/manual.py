"""Connector #2: the guided / manual source -- the universal fallback.

When a practice runs a system Perikrone has no automated plug for (a legacy EHR,
an odd email host, anything), this connector still assesses it: it walks the
assessor through plain-language questions and builds the same normalized snapshot
the engine expects. No API, no credentials, no file-format knowledge required --
so *any* system is assessable today.

It saves what you enter to a JSON snapshot in data/, so a re-run needs no
re-typing (and that saved file also works with the demo connector's --data).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .base import Connector, validate_snapshot

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class ManualConnector(Connector):
    name = "manual"

    def __init__(self, save_dir: str | Path | None = None):
        self.save_dir = Path(save_dir) if save_dir else _DATA_DIR

    def collect(self) -> dict:
        if not sys.stdin or not sys.stdin.isatty():
            # Allow piped input for testing, but warn when there's no real terminal.
            pass

        _say("")
        _say("  Perikrone — guided assessment")
        _say("  Answer a few plain questions. Press Enter to accept a [default].")
        _say("  " + "-" * 52)

        practice = _ask("Practice name", "My Practice")
        _say("")
        _say("  A couple of system-wide settings (answer y / n / u for unknown):")
        sec_def = _ask_ynu("  Are baseline security protections / 'security defaults' ON?")
        legacy = _ask_ynu("  Are old sign-in methods (legacy authentication) allowed?")

        _say("")
        _say("  Now each account. Enter a name to add one, or 'done' to finish.")
        users = []
        while True:
            _say("")
            name = _ask(f"  Account #{len(users) + 1} name (or 'done')", "done")
            if name.strip().lower() == "done":
                break
            email = _ask("    Email (optional)", "")
            enabled = _ask_ynu("    Is the account currently enabled/active?", default=True)
            mfa = _ask_ynu("    Does it have multi-factor authentication (MFA) on?")
            admin = _ask_ynu("    Does it have full administrator rights?", default=False)
            guest = _ask_ynu("    Is this an outside / guest account (not staff)?", default=False)
            last = _ask_usage("    When was it last used?")

            users.append({
                "id": f"manual-{len(users) + 1:03d}",
                "display_name": name.strip(),
                "email": email.strip(),
                "enabled": True if enabled is None else enabled,
                "mfa_enabled": bool(mfa),
                "is_admin": bool(admin),
                "account_type": "guest" if guest else "member",
                "last_sign_in": last,
            })

        snapshot = {
            "practice_name": practice.strip() or "My Practice",
            "source": self.name,
            "collected_at": _now_iso(),
            # y/n/unknown -> True/False/None. 'security_defaults_enabled' stores
            # whether defaults are ON; checks only fire on an explicit False.
            "security_defaults_enabled": sec_def,
            "legacy_auth_allowed": legacy,
            "users": users,
        }
        validate_snapshot(snapshot)
        self._save(snapshot)
        return snapshot

    def _save(self, snapshot: dict) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        slug = _slug(snapshot["practice_name"])
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.save_dir / f"{slug}-{date}.json"
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        _say("")
        _say(f"  Saved your answers to {path}")
        _say(f"  (re-run anytime with:  python3 run.py --source demo --data {path})")


# ---- prompt helpers ----------------------------------------------------------

def _say(msg: str) -> None:
    print(msg, file=sys.stderr)


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        resp = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        resp = ""
    return resp or default


def _ask_ynu(prompt: str, default: bool | None = None):
    """Yes / no / unknown -> True / False / None."""
    hint = {True: "Y/n/u", False: "y/N/u", None: "y/n/U"}[default]
    while True:
        resp = _ask(f"{prompt} ({hint})").strip().lower()
        if not resp:
            return default
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        if resp in ("u", "unknown", "?"):
            return None
        _say("    Please answer y, n, or u.")


def _ask_usage(prompt: str):
    """Map plain usage answers to a last_sign_in value the engine understands.
    recent -> now (not stale); old -> 180 days ago (stale); never -> null
    (never signed in); unknown -> now (we can't tell, so we don't flag it)."""
    while True:
        resp = _ask(
            f"{prompt} (r=recently / o=a long time ago / x=never / u=unknown)",
            "r",
        ).strip().lower()
        if resp in ("r", "recent", "recently"):
            return _now_iso()
        if resp in ("o", "old"):
            return _days_ago_iso(180)
        if resp in ("x", "never"):
            return None
        if resp in ("u", "unknown", "?"):
            return _now_iso()
        _say("    Please answer r, o, x, or u.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_ago_iso(days: int) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _slug(name: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "-" for c in name)
    return "-".join(filter(None, s.split("-"))) or "practice"

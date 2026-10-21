"""Connector: Google Workspace (read-only).

Reads a Workspace tenant's identity posture through the Google Admin SDK
Directory API, read-only, and normalizes it into the engine's snapshot shape.
It never writes to or changes the tenant.

Auth uses an OAuth2 refresh token, which keeps the connector pure-stdlib (no JWT
signing or Google client libraries): it exchanges a refresh token for a
short-lived access token, then reads the directory. Credentials come from
environment variables, never hard-coded:
    PERIKRONE_GOOGLE_CLIENT_ID
    PERIKRONE_GOOGLE_CLIENT_SECRET
    PERIKRONE_GOOGLE_REFRESH_TOKEN
    PERIKRONE_GOOGLE_CUSTOMER   (optional; defaults to "my_customer")

See docs/google-setup.md to create read-only OAuth credentials and a refresh
token. Pure standard library (urllib). Fetch (network) and normalize (pure
transform) are split so the mapping is testable against captured sample data.

Scope note: Google Workspace has no single "security defaults" or "legacy auth"
toggle like Entra, so those two checks don't apply here and are left unset rather
than guessed. The checks that do apply map directly: missing 2-Step Verification
(no MFA), stale accounts, administrator sprawl, and guest/external accounts (via
the Directory's `isGuestUser` flag).
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
from datetime import datetime, timezone

from ._http import get_json, post_form
from .base import Connector, validate_snapshot

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_DIRECTORY = "https://admin.googleapis.com/admin/directory/v1/users"
# Google returns this sentinel lastLoginTime for accounts that have never signed in.
_NEVER_LOGIN = "1970-01-01T00:00:00.000Z"

_ENV = (
    "PERIKRONE_GOOGLE_CLIENT_ID",
    "PERIKRONE_GOOGLE_CLIENT_SECRET",
    "PERIKRONE_GOOGLE_REFRESH_TOKEN",
)


class GoogleWorkspaceConnector(Connector):
    name = "google"

    def __init__(self, client_id=None, client_secret=None, refresh_token=None,
                 customer=None):
        self.client_id = client_id or os.environ.get("PERIKRONE_GOOGLE_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("PERIKRONE_GOOGLE_CLIENT_SECRET")
        self.refresh_token = refresh_token or os.environ.get("PERIKRONE_GOOGLE_REFRESH_TOKEN")
        self.customer = customer or os.environ.get("PERIKRONE_GOOGLE_CUSTOMER") or "my_customer"

    def collect(self) -> dict:
        missing = [name for name, val in zip(_ENV, (
            self.client_id, self.client_secret, self.refresh_token)) if not val]
        if missing:
            raise ValueError(
                "Google Workspace credentials not set: " + ", ".join(missing) +
                ". See docs/google-setup.md to create read-only OAuth credentials "
                "and a refresh token.")
        token = self._token()
        bundle = self._fetch(token)
        snapshot = normalize(bundle)
        validate_snapshot(snapshot)
        return snapshot

    def _token(self) -> str:
        try:
            return post_form(_TOKEN_URL, {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            })["access_token"]
        except urllib.error.HTTPError as exc:
            raise ValueError(
                f"Google sign-in failed (HTTP {exc.code}). Check the client id, "
                "client secret, and refresh token.") from None

    def _fetch(self, token: str) -> dict:
        users: list = []
        page_token = None
        while True:
            url = (f"{_DIRECTORY}?customer={self.customer}&maxResults=500"
                   "&projection=full&orderBy=email")
            if page_token:
                url += f"&pageToken={urllib.parse.quote(page_token, safe='')}"
            page = get_json(url, token)
            users.extend(page.get("users", []))
            page_token = page.get("nextPageToken")
            if not page_token:
                break
        return {"organization_name": _org_name(users), "users": users}


def normalize(bundle: dict) -> dict:
    """Pure transform: raw Directory API users -> the engine's normalized snapshot."""
    users = []
    for u in bundle.get("users", []):
        last = u.get("lastLoginTime")
        if last == _NEVER_LOGIN:
            last = None  # never signed in -> let the stale check report it as such
        email = u.get("primaryEmail", "")
        name = (u.get("name") or {}).get("fullName")
        users.append({
            "id": u.get("id"),
            "display_name": name or email or u.get("id"),
            "email": email,
            "enabled": not bool(u.get("suspended", False)),
            "mfa_enabled": bool(u.get("isEnrolledIn2Sv", False)),
            "is_admin": bool(u.get("isAdmin", False)),  # super administrator
            "account_type": "guest" if u.get("isGuestUser") else "member",
            "last_sign_in": last,
        })

    return {
        "practice_name": bundle.get("organization_name", "Google Workspace"),
        "source": "google",
        "platform": "google",
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "security_defaults_enabled": None,  # no Entra-style toggle in Google
        "legacy_auth_allowed": None,
        "users": users,
    }


def _org_name(users: list) -> str:
    for u in users:
        email = u.get("primaryEmail", "")
        if "@" in email:
            return f"{email.split('@', 1)[1]} (Google Workspace)"
    return "Google Workspace"

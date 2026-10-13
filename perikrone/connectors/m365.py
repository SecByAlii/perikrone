"""Connector: Microsoft 365 / Entra ID (read-only).

Reads a tenant's identity posture through Microsoft Graph using app-only,
least-privilege, READ-ONLY permissions, and normalizes it into the engine's
snapshot shape. It never writes to or changes the tenant.

Credentials come from environment variables -- never hard-coded, never written to
a file:
    PERIKRONE_M365_TENANT_ID
    PERIKRONE_M365_CLIENT_ID
    PERIKRONE_M365_CLIENT_SECRET

See docs/m365-setup.md to create a free tenant and a read-only app registration.

Pure standard library (urllib) -- no dependencies. The fetch (network) and the
normalize (pure transform) are deliberately separated so the mapping can be
tested against captured real-shape Graph data without a live tenant.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .base import Connector, validate_snapshot

_LOGIN = "https://login.microsoftonline.com"
_GRAPH = "https://graph.microsoft.com/v1.0"
# Well-known, fixed template id for the Global Administrator directory role.
_GLOBAL_ADMIN_ROLE_TEMPLATE = "62e90394-69f5-4237-9190-012177145e10"

_ENV = (
    "PERIKRONE_M365_TENANT_ID",
    "PERIKRONE_M365_CLIENT_ID",
    "PERIKRONE_M365_CLIENT_SECRET",
)


class M365Connector(Connector):
    name = "m365"

    def __init__(self, tenant_id=None, client_id=None, client_secret=None):
        self.tenant_id = tenant_id or os.environ.get("PERIKRONE_M365_TENANT_ID")
        self.client_id = client_id or os.environ.get("PERIKRONE_M365_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("PERIKRONE_M365_CLIENT_SECRET")

    def collect(self) -> dict:
        missing = [name for name, val in zip(_ENV, (
            self.tenant_id, self.client_id, self.client_secret)) if not val]
        if missing:
            raise ValueError(
                "Microsoft 365 credentials not set: " + ", ".join(missing) +
                ". See docs/m365-setup.md to create a free tenant and a "
                "read-only app registration."
            )
        token = self._token()
        bundle = self._fetch(token)
        snapshot = normalize(bundle)
        validate_snapshot(snapshot)
        return snapshot

    def _token(self) -> str:
        data = urllib.parse.urlencode({
            "client_id": self.client_id,
            "scope": "https://graph.microsoft.com/.default",
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }).encode()
        url = f"{_LOGIN}/{self.tenant_id}/oauth2/v2.0/token"
        try:
            return _post_form(url, data)["access_token"]
        except urllib.error.HTTPError as exc:
            raise ValueError(
                f"Microsoft sign-in failed (HTTP {exc.code}). Check the tenant id, "
                "client id, and client secret."
            ) from None

    def _fetch(self, token: str) -> dict:
        """Pull the read-only signals the checks need. Each optional signal fails
        soft (-> None / empty) so a missing premium feature never crashes a scan."""
        users = _graph_all(
            f"{_GRAPH}/users?$select=id,displayName,userPrincipalName,"
            f"accountEnabled,userType,signInActivity&$top=999", token)

        try:
            reg = _graph_all(
                f"{_GRAPH}/reports/authenticationMethods/userRegistrationDetails"
                f"?$top=999", token)
            mfa_ids = [r.get("id") for r in reg if r.get("isMfaRegistered")]
        except urllib.error.HTTPError:
            mfa_ids = None  # couldn't determine MFA -> normalize won't false-flag

        try:
            sd = _get(f"{_GRAPH}/policies/identitySecurityDefaultsEnforcementPolicy",
                      token)
            security_defaults = sd.get("isEnabled")
        except urllib.error.HTTPError:
            security_defaults = None

        try:
            org = _graph_all(f"{_GRAPH}/organization?$select=displayName", token)
            org_name = org[0]["displayName"] if org else "Microsoft 365 tenant"
        except (urllib.error.HTTPError, KeyError, IndexError):
            org_name = "Microsoft 365 tenant"

        return {
            "organization_name": org_name,
            "users": users,
            "mfa_registered_ids": mfa_ids,
            "global_admin_ids": _global_admin_ids(token),
            "security_defaults_enabled": security_defaults,
        }


def normalize(bundle: dict) -> dict:
    """Pure transform: raw Graph data -> the engine's normalized snapshot. No
    network, so it's fully testable against a captured sample."""
    mfa_ids = bundle.get("mfa_registered_ids")
    mfa_set = None if mfa_ids is None else set(mfa_ids)
    admin_set = set(bundle.get("global_admin_ids") or [])

    users = []
    for u in bundle.get("users", []):
        uid = u.get("id")
        sign_in = u.get("signInActivity") or {}
        users.append({
            "id": uid,
            "display_name": u.get("displayName") or u.get("userPrincipalName") or uid,
            "email": u.get("userPrincipalName", ""),
            "enabled": bool(u.get("accountEnabled", True)),
            # If MFA registration is unknown (report unavailable), don't false-flag.
            "mfa_enabled": True if mfa_set is None else (uid in mfa_set),
            "is_admin": uid in admin_set,
            "account_type": "guest" if u.get("userType") == "Guest" else "member",
            "last_sign_in": sign_in.get("lastSignInDateTime"),
        })

    return {
        "practice_name": bundle.get("organization_name", "Microsoft 365 tenant"),
        "source": "m365",
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "security_defaults_enabled": bundle.get("security_defaults_enabled"),
        # Legacy-auth state has no single clean Graph flag; left for a later
        # conditional-access review rather than guessed at.
        "legacy_auth_allowed": None,
        "users": users,
    }


# ---- Graph HTTP helpers (stdlib only) ----------------------------------------

def _post_form(url: str, data: bytes) -> dict:
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _graph_all(url: str, token: str) -> list:
    """GET a collection, following @odata.nextLink paging."""
    items: list = []
    while url:
        page = _get(url, token)
        items.extend(page.get("value", []))
        url = page.get("@odata.nextLink")
    return items


def _global_admin_ids(token: str) -> list:
    roles = _graph_all(f"{_GRAPH}/directoryRoles", token)
    role_id = next(
        (r.get("id") for r in roles
         if r.get("roleTemplateId") == _GLOBAL_ADMIN_ROLE_TEMPLATE), None)
    if not role_id:
        return []
    members = _graph_all(f"{_GRAPH}/directoryRoles/{role_id}/members?$select=id", token)
    return [m.get("id") for m in members if m.get("id")]

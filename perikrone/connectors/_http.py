"""Tiny shared HTTP helpers for connectors -- standard library only, no deps.

Both the Microsoft 365 and Google Workspace connectors authenticate with an
OAuth2 token endpoint (form POST) and then read JSON from an API with a bearer
token, so those two calls live here instead of being duplicated per connector.
Pagination differs per API and stays in each connector.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request


def post_form(url: str, params: dict) -> dict:
    """POST application/x-www-form-urlencoded params, return parsed JSON."""
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str, token: str) -> dict:
    """GET with a bearer token, return parsed JSON."""
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

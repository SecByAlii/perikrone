"""The five v1 checks -- the real IP.

Each check is a plain function that takes a normalized snapshot (a dict, shape
documented in connectors/base.py) and returns a list of Findings. They know
nothing about Microsoft, Google, or any specific system; they only reason about
normalized facts. Add a new data source and these checks keep working unchanged.

The five gaps are the exact Phase-1 findings from the HIPAA risk assessment,
turned into code.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .findings import Finding, HipaaControl, Severity


# ---- HIPAA Security Rule controls, cited once and reused ---------------------

AUTHN = HipaaControl("45 CFR 164.312(d)", "Person or Entity Authentication")
ACCESS_CONTROL = HipaaControl("45 CFR 164.312(a)(1)", "Access Control")
TERMINATION = HipaaControl(
    "45 CFR 164.308(a)(3)(ii)(C)", "Termination Procedures"
)
ACCESS_MGMT = HipaaControl(
    "45 CFR 164.308(a)(4)", "Information Access Management"
)
ACCESS_AUTHZ = HipaaControl(
    "45 CFR 164.308(a)(4)(ii)(B)", "Access Authorization"
)
RISK_MGMT = HipaaControl("45 CFR 164.308(a)(1)(ii)(B)", "Risk Management")
TRANSMISSION = HipaaControl("45 CFR 164.312(e)(1)", "Transmission Security")
BAA = HipaaControl(
    "45 CFR 164.308(b)(1)", "Business Associate Contracts and Other Arrangements"
)

# Thresholds -- conservative defaults tuned for a small practice.
STALE_DAYS = 90            # no sign-in in this many days = stale
MAX_GLOBAL_ADMINS = 2      # more than this = over-privileged for a small office


def _reference_time(snapshot: dict) -> datetime:
    """The 'now' a check measures staleness against. Uses the snapshot's
    collected_at so results are deterministic and reproducible."""
    raw = snapshot.get("collected_at")
    if raw:
        try:
            return _parse_dt(raw)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _parse_dt(raw: str) -> datetime:
    """Parse an ISO-8601 timestamp, tolerating a trailing 'Z', and always return
    an aware UTC datetime."""
    cleaned = raw.replace("Z", "+00:00")
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _count(n: int, singular: str, plural: str | None = None) -> str:
    """'1 account' / '5 accounts' -- clean counts, no 'account(s)'."""
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _enabled_members(snapshot: dict) -> list[dict]:
    return [
        u for u in snapshot.get("users", [])
        if u.get("enabled", True) and u.get("account_type", "member") == "member"
    ]


# ---- Check 1: accounts with no MFA -------------------------------------------

def check_no_mfa(snapshot: dict) -> list[Finding]:
    offenders = [u for u in _enabled_members(snapshot) if not u.get("mfa_enabled")]
    if not offenders:
        return []

    admins = [u for u in offenders if u.get("is_admin")]
    # An admin without MFA is the worst case on the board: one phished password
    # owns the whole tenant.
    severity = Severity.CRITICAL if admins else Severity.HIGH

    affected = [_label(u) for u in offenders]
    detail = (
        "These accounts can be signed into with a password alone. A single "
        "phished, guessed, or reused password is all an attacker needs -- no "
        "second factor stands in the way. This is the single most common way "
        "small practices get breached, and multi-factor authentication would "
        "stop nearly all of it at the front door."
    )
    if admins:
        n = len(admins)
        is_are = "is" if n == 1 else "are"
        noun = "an administrator account" if n == 1 else "administrator accounts"
        detail += (
            f" Worse, {n} of these {is_are} {noun} "
            "(" + ", ".join(_label(u) for u in admins) + "), so compromising "
            "one hands an attacker control of the entire environment."
        )

    have = "has" if len(offenders) == 1 else "have"
    return [Finding(
        check_id="no-mfa",
        title="Accounts without multi-factor authentication",
        severity=severity,
        summary=f"{_count(len(offenders), 'active account')} {have} no MFA enabled.",
        detail=detail,
        affected=affected,
        hipaa=[AUTHN, ACCESS_CONTROL],
        fix=[
            "Require MFA for every user, administrators first.",
            "Prefer an authenticator app or hardware key over SMS codes.",
            "Enforce it with a conditional-access policy (or security defaults) "
            "so new accounts get it automatically.",
        ],
        fix_links=[
            ("Microsoft 365: set up multi-factor authentication",
             "https://learn.microsoft.com/en-us/microsoft-365/admin/security-and-compliance/set-up-multi-factor-authentication"),
            ("Google Workspace: turn on 2-step verification",
             "https://support.google.com/a/answer/175197"),
        ],
    )]


# ---- Check 2: stale accounts -------------------------------------------------

def check_stale_accounts(snapshot: dict) -> list[Finding]:
    now = _reference_time(snapshot)
    stale: list[tuple[dict, str]] = []

    for u in _enabled_members(snapshot):
        last = u.get("last_sign_in")
        if not last:
            stale.append((u, "has never signed in"))
            continue
        try:
            days = (now - _parse_dt(last)).days
        except ValueError:
            continue
        if days >= STALE_DAYS:
            stale.append((u, f"last signed in {days} days ago"))

    if not stale:
        return []

    affected = [f"{_label(u)} ({why})" for u, why in stale]
    looks = "looks" if len(stale) == 1 else "look"
    return [Finding(
        check_id="stale-accounts",
        title="Stale / orphaned active accounts",
        severity=Severity.HIGH,
        summary=(
            f"{_count(len(stale), 'active account')} {looks} abandoned but "
            "still enabled."
        ),
        detail=(
            "Each of these accounts is still enabled but shows no recent use -- "
            "the classic signature of a staff member who left without their "
            "access being turned off. Every one is a standing door into the "
            "practice that nobody is watching: it can be taken over quietly, and "
            "because no one uses it, the misuse goes unnoticed for months."
        ),
        affected=affected,
        hipaa=[TERMINATION, ACCESS_MGMT],
        fix=[
            "Confirm whether each account belongs to someone who still works here.",
            "Disable (don't delete) departed-staff accounts immediately, then "
            "remove them after any required retention period.",
            "Put a written termination checklist in place so access is revoked "
            "the day someone leaves.",
        ],
        fix_links=[
            ("Microsoft 365: remove a former employee's access",
             "https://learn.microsoft.com/en-us/microsoft-365/admin/add-users/remove-former-employee"),
        ],
    )]


# ---- Check 3: too many global admins -----------------------------------------

def check_admin_sprawl(snapshot: dict) -> list[Finding]:
    admins = [u for u in _enabled_members(snapshot) if u.get("is_admin")]
    if len(admins) <= MAX_GLOBAL_ADMINS:
        return []

    affected = [_label(u) for u in admins]
    return [Finding(
        check_id="admin-sprawl",
        title="Too many administrator accounts",
        severity=Severity.HIGH,
        summary=(
            f"{len(admins)} accounts have full administrator rights "
            f"(recommended maximum for a practice this size is {MAX_GLOBAL_ADMINS})."
        ),
        detail=(
            "Full administrator rights should be rare -- an admin account can "
            "change security settings, read anyone's mail, and reset passwords. "
            "The more accounts hold that power, the bigger the target: an "
            "attacker only has to phish one of them to own everything. Day-to-day "
            "work almost never needs admin rights."
        ),
        affected=affected,
        hipaa=[ACCESS_AUTHZ, ACCESS_CONTROL],
        fix=[
            "Keep two administrator accounts (one primary, one break-glass backup) "
            "and remove admin rights from everyone else.",
            "Give staff only the specific permissions their job needs "
            "(least privilege).",
            "Require admins to do everyday work from a normal, non-admin account.",
        ],
        fix_links=[
            ("Microsoft 365: about admin roles (least privilege)",
             "https://learn.microsoft.com/en-us/microsoft-365/admin/add-users/about-admin-roles"),
        ],
    )]


# ---- Check 4: basic protections switched off ---------------------------------

def check_baseline_protections(snapshot: dict) -> list[Finding]:
    findings: list[Finding] = []

    if snapshot.get("security_defaults_enabled") is False:
        findings.append(Finding(
            check_id="security-defaults-off",
            title="Baseline security protections are turned off",
            severity=Severity.HIGH,
            summary="Security defaults (the free baseline protections) are disabled.",
            detail=(
                "The platform's built-in baseline -- which enforces MFA, blocks "
                "the weakest legacy sign-in methods, and protects admin actions -- "
                "is switched off. With it off, the practice is relying on "
                "protections that have to be configured by hand, and the gaps "
                "found in this report are the predictable result."
            ),
            affected=["Tenant-wide setting"],
            hipaa=[ACCESS_CONTROL, RISK_MGMT],
            fix=[
                "Turn on security defaults (or, if you've outgrown them, replace "
                "them with equivalent conditional-access policies).",
                "Confirm MFA is enforced for all users afterward.",
            ],
            fix_links=[
                ("Microsoft Entra: security defaults",
                 "https://learn.microsoft.com/en-us/entra/fundamentals/security-defaults"),
            ],
        ))

    if snapshot.get("legacy_auth_allowed") is True:
        findings.append(Finding(
            check_id="legacy-auth-allowed",
            title="Outdated sign-in methods are still allowed",
            severity=Severity.MEDIUM,
            summary="Legacy authentication protocols are still permitted.",
            detail=(
                "Old sign-in methods (legacy authentication) can't do "
                "multi-factor authentication, so attackers use them as a side "
                "door to bypass MFA entirely. They're a favorite target of "
                "automated password-spray attacks and are almost never needed by "
                "a modern practice."
            ),
            affected=["Tenant-wide setting"],
            hipaa=[TRANSMISSION, ACCESS_CONTROL],
            fix=[
                "Block legacy authentication tenant-wide.",
                "Move any old device or app that depended on it to a modern, "
                "MFA-capable sign-in method first.",
            ],
            fix_links=[
                ("Microsoft Entra: block legacy authentication",
                 "https://learn.microsoft.com/en-us/entra/identity/conditional-access/policy-block-legacy-authentication"),
            ],
        ))

    return findings


# ---- Check 5: guest / external accounts --------------------------------------

def check_external_access(snapshot: dict) -> list[Finding]:
    guests = [
        u for u in snapshot.get("users", [])
        if u.get("enabled", True) and u.get("account_type") == "guest"
    ]
    if not guests:
        return []

    affected = [_label(u) for u in guests]
    have = "has" if len(guests) == 1 else "have"
    return [Finding(
        check_id="external-access",
        title="External / guest accounts with standing access",
        severity=Severity.MEDIUM,
        summary=(
            f"{_count(len(guests), 'external guest account')} {have} access to "
            "the environment."
        ),
        detail=(
            "These accounts belong to people outside the practice -- a billing "
            "contractor, a former vendor, an outside consultant. Outside access "
            "is sometimes legitimate, but each account is a door you don't fully "
            "control, and standing access that outlives its purpose is a common "
            "blind spot. If any of these people handle patient data, a signed "
            "business associate agreement is legally required."
        ),
        affected=affected,
        hipaa=[BAA, ACCESS_MGMT],
        fix=[
            "Review each guest: confirm who they are and whether they still need "
            "access.",
            "Remove access that is no longer needed.",
            "Make sure a signed business associate agreement is on file for any "
            "outside party that touches patient data.",
        ],
    )]


# ---- registry + helpers ------------------------------------------------------

# (step label shown in the live scan, check function). ALL_CHECKS derives from it.
CHECK_STEPS = [
    ("Multi-factor authentication", check_no_mfa),
    ("Stale / orphaned accounts", check_stale_accounts),
    ("Administrator access", check_admin_sprawl),
    ("Baseline protections", check_baseline_protections),
    ("External / guest access", check_external_access),
]

ALL_CHECKS = [func for _label, func in CHECK_STEPS]


def _label(user: dict) -> str:
    """A human-friendly name for an account in the report."""
    name = user.get("display_name") or user.get("email") or user.get("id") or "unknown"
    email = user.get("email")
    if email and email != name:
        return f"{name} <{email}>"
    return name

# Connecting Perikrone to a live Microsoft 365 tenant

Perikrone reads a tenant through Microsoft Graph with **app-only, read-only,
least-privilege** permissions. It never writes to or changes anything.

You don't need a tenant to use Perikrone (the demo and guided sources work with
none). Follow this only when you want it to scan a **real** Microsoft 365 /
Entra ID tenant — either one you already admin, or a free one you create below.

---

## A. (Optional) Create a free Entra tenant to test against

Skip if you already have a tenant you administer.

1. Go to the **Microsoft Entra admin center** → <https://entra.microsoft.com>.
2. **Manage tenants → Create** → choose a **Microsoft Entra ID** tenant.
3. Give it a name (e.g. "Perikrone Test"), pick a region, and finish.
   - Microsoft asks for a debit/credit card to verify you're human: a **$1
     hold that is reversed**. The tenant itself is free to run.
4. Add a few **test users** (Entra admin center → **Users → New user**) so there's
   something to scan. Make one an admin and leave MFA off on a couple to see
   findings appear.

## B. Register a read-only app (in whichever tenant you'll scan)

1. Entra admin center → **App registrations → New registration**.
   - Name: `Perikrone (read-only)`. Leave redirect URI blank. Register.
2. On the app's overview, copy the **Directory (tenant) ID** and the
   **Application (client) ID**.
3. **API permissions → Add a permission → Microsoft Graph → Application
   permissions**, add these (all read-only):
   - `User.Read.All`
   - `Directory.Read.All`
   - `Policy.Read.All`
   - `Reports.Read.All`
   - `AuditLog.Read.All`
   Then click **Grant admin consent** for the tenant.
4. **Certificates & secrets → New client secret** → copy the secret **Value**
   immediately (you can't see it again).

> These are all `*.Read.*` permissions — the app can read posture, never change it.

## C. Point Perikrone at it

Set three environment variables (your secret stays in your shell / a secrets
manager — never commit it to a file):

```bash
export PERIKRONE_M365_TENANT_ID="<Directory (tenant) ID>"
export PERIKRONE_M365_CLIENT_ID="<Application (client) ID>"
export PERIKRONE_M365_CLIENT_SECRET="<the secret value>"
```

Then run it:

```bash
python3 run.py --source m365 --open     # one-shot scan of the live tenant
python3 run.py --serve                  # or the app — "Microsoft 365" appears
                                        # in the Source dropdown once creds are set
```

## Notes & limits (v1)

- **MFA state** comes from the Entra authentication-methods registration report.
  If your plan doesn't expose it, Perikrone marks MFA "unknown" and won't
  false-flag accounts — rather than guess.
- **Last sign-in** (for stale accounts) uses `signInActivity`, which needs
  Entra ID P1; on a free tier it may be empty, so stale detection is limited
  there.
- **Legacy authentication** has no single Graph flag; it's left for a manual
  conditional-access review in this version rather than guessed.
- Everything else — admin counts, guest accounts, security defaults — reads on
  any tier.

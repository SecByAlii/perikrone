# Connecting Perikrone to a live Google Workspace tenant

Perikrone reads a Workspace tenant through the Google Admin SDK **Directory API**
with a **read-only** scope. It never writes to or changes the tenant.

You don't need a tenant to use Perikrone (the demo and guided sources work with
none). Follow this only to scan a **real** Google Workspace tenant you administer.

Auth uses an OAuth2 **refresh token** so Perikrone stays dependency-free (no
Google client libraries, no service-account key signing).

---

## 1. Create read-only OAuth credentials

1. In the **Google Cloud Console** (console.cloud.google.com), create or pick a
   project and **enable the Admin SDK API** (APIs & Services → Library → "Admin
   SDK API" → Enable).
2. **OAuth consent screen** → User type **Internal** → add the scope
   `https://www.googleapis.com/auth/admin.directory.user.readonly`.
3. **Credentials → Create credentials → OAuth client ID → Web application.** Under
   **Authorized redirect URIs**, add `https://developers.google.com/oauthplayground`.
   Copy the **Client ID** and **Client secret**.
   (The OAuth 2.0 Playground in the next step requires a *web-application* client
   with that redirect URI — a Desktop client won't work there.)

## 2. Get a refresh token (one time, as a Workspace admin)

Authorize the read-only scope **as a super-admin** and exchange the result for a
refresh token. The quickest route is the **OAuth 2.0 Playground**
(developers.google.com/oauthplayground):

1. Gear icon → check **"Use your own OAuth credentials"** → paste your Client ID
   and secret.
2. In "Step 1," enter the scope
   `https://www.googleapis.com/auth/admin.directory.user.readonly` and authorize
   as the admin account.
3. "Step 2" → **Exchange authorization code for tokens** → copy the **refresh
   token**.

## 3. Point Perikrone at it

Set the environment variables (the refresh token stays in your shell / a secrets
manager — never commit it):

```bash
export PERIKRONE_GOOGLE_CLIENT_ID="<Client ID>"
export PERIKRONE_GOOGLE_CLIENT_SECRET="<Client secret>"
export PERIKRONE_GOOGLE_REFRESH_TOKEN="<refresh token>"
# optional; defaults to "my_customer" (your own Workspace)
export PERIKRONE_GOOGLE_CUSTOMER="my_customer"
```

Then run it:

```bash
python3 run.py --source google --open     # one-shot scan of the live tenant
python3 run.py --serve                    # the app — "google" appears in Source
                                          # once the creds are set
```

## What it checks (and what it doesn't)

Google Workspace maps cleanly onto the **identity** checks:

- **Missing 2-Step Verification** (no MFA) — from each user's `isEnrolledIn2Sv`.
- **Stale accounts** — from `lastLoginTime` (a never-logged-in account is reported
  as such).
- **Administrator sprawl** — from `isAdmin` (super administrators).
- **Guest / external accounts** — from the Directory's `isGuestUser` flag.

One area is **M365-specific and doesn't apply** here, so it's left unset rather
than guessed:

- **Security defaults / legacy auth** — Google has no single equivalent toggle.
  (In-app file-sharing settings live in Drive, out of scope for v1.)

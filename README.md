# Perikrone

**A read-only security-posture auditor for small medical practices.** Point it at
whatever a practice runs, and it flags the real security gaps — then writes a
plain-English report mapping each gap to the HIPAA Security Rule control it
affects and exactly how to fix it. It's the HIPAA Phase-1 checklist, automated.

_Closest-point security._

> **Read-only by design.** Perikrone reads configuration and reports on it. It
> never writes to, changes, or accesses patient data in any system. It's an
> assessment tool, not an admin tool — safe to point at a real environment.

---

## Quickstart

No dependencies — pure Python standard library (3.10+).

```bash
python3 run.py --serve           # launch the app: open in browser, scan from a button
python3 run.py                   # or one-shot: assess the demo and write a report
python3 run.py --open            # ...and open that report in your browser
python3 run.py --source manual   # assess a REAL practice via guided questions
python3 run.py --watch           # monitor: re-scan on a schedule, alert if posture drops
```

`--serve` is the app: it opens Perikrone in your browser, you pick a source and
hit **Run assessment**, and the posture dashboard renders live. Local-only
(binds to 127.0.0.1).

By default Perikrone writes a **self-contained HTML dashboard** to `reports/`
(double-click to open, prints to PDF) plus a Markdown version with `--format md`.
It runs the moment you clone it — no tenant, no credentials — because the **demo
connector** ships with a realistic sample practice. See a rendered example in
[`examples/`](examples/).

```
Perikrone — Cypress Eye Associates
  source: demo   accounts: 9   score: 27/100 (F)
  findings: 6  (1 critical, 3 high, 2 medium)
  report:  reports/cypress-eye-associates-2026-10-09.html
```

The dashboard leads with a posture **score**, a plain-English bottom-line verdict,
a prioritized **action plan**, each finding reframed as *when to fix it*
("Fix now / this week / this month") with links to the official how-to guides,
and — once there's history — a **posture-over-time** trend.

## Monitoring (`--watch`)

`python3 run.py --watch` re-scans on a schedule and **alerts only when posture
degrades** — a new gap appears, an existing one gets worse, or the score drops.
Alerts print to the console, fire a desktop notification (macOS), and append to
`reports/alerts.log`. Leave it running, or schedule single scans with cron/launchd.

```bash
python3 run.py --watch --source m365 --interval 3600    # scan a live tenant hourly
python3 run.py --watch --source demo --simulate-drift   # demo: watch an alert fire
```


## What it checks (v1)

The five Phase-1 gaps that actually get small practices breached, each mapped to
the HIPAA control it affects:

| # | Check | HIPAA control(s) |
|---|---|---|
| 1 | Accounts with **no MFA** | §164.312(d) Authentication · §164.312(a)(1) Access Control |
| 2 | **Stale / orphaned** active accounts | §164.308(a)(3)(ii)(C) Termination · §164.308(a)(4) Access Mgmt |
| 3 | **Too many administrators** | §164.308(a)(4)(ii)(B) Access Authorization · §164.312(a)(1) |
| 4 | **Baseline protections off** (security defaults / legacy auth) | §164.312(a)(1) · §164.308(a)(1)(ii)(B) · §164.312(e)(1) |
| 5 | **External / guest** accounts with access | §164.308(b)(1) Business Associate · §164.308(a)(4) |

## How it's built — adaptable to whatever they run

Two separated pieces, and the split is the whole design:

- **The engine** (`perikrone/engine.py` + `checks.py`) is the brain. It knows the
  security controls and their HIPAA mappings, and evaluates *normalized facts*.
  It knows nothing about any specific system.
- **Connectors** (`perikrone/connectors/`) are dumb adapters — one per system.
  Each one reaches into its system, pulls the relevant facts, and returns them in
  the one normalized shape the engine understands (documented in
  `connectors/base.py`).

Add a new system → write one new connector. The engine and checks never change.
That's how Perikrone grows to cover anything a practice runs.

```
perikrone/
  findings.py            the common language (Finding, Severity, HipaaControl)
  checks.py              the 5 checks + HIPAA mappings  (the IP)
  engine.py              runs the checks, collects findings, scores posture
  report.py              findings -> plain-English HIPAA-mapped Markdown
  report_html.py         findings -> the self-contained HTML dashboard
  connectors/
    base.py              the connector contract + normalized snapshot shape
    demo.py              reads the built-in sample practice
    manual.py            guided Q&A intake — the universal fallback
    m365.py              Microsoft 365 / Entra via Graph (read-only)
  server.py              the launch-and-run app (--serve)
  history.py             saves each scan; powers the posture-over-time trend
  monitor.py             change detection + alerts (--watch)
data/demo_practice.json  the fake practice
docs/m365-setup.md       how to connect a live Microsoft 365 tenant
examples/                a rendered sample report
tests/                   connector tests (run: python3 -m unittest)
reports/                 generated reports land here (git-ignored)
run.py                   CLI entry point
```

## Roadmap

- **Now:** engine + the launch-and-run **dashboard app** (live scan, guided
  "Fix it", re-scan-to-watch-the-score-climb) + **demo**, **guided/manual**, and
  **Microsoft 365 / Entra** (read-only Graph) connectors + **posture-over-time
  trend** + **monitoring & alerts** (`--watch`). ✅
  Connect a tenant: [docs/m365-setup.md](docs/m365-setup.md).
- **Next:** **Google Workspace** (Admin SDK) — same engine, new plug.
- **Firm-level:** EHR/EMR connectors (Epic, eClinicalWorks, Athenahealth,
  NextGen, Tebra). Deferred on purpose — no universal EHR API, each vendor is a
  partner-gated integration, and reading the EHR means touching PHI. Gated on a
  real paying practice and a signed agreement.

## Scope & disclaimer

Perikrone supports, but does not replace, a full HIPAA Security Rule risk
analysis under 45 CFR 164.308(a)(1)(ii)(A). It is an assessment aid.

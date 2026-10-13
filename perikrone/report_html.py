"""The dashboard: a single self-contained HTML page a practice opens in any
browser (double-click, no server, no tools).

Dark, with Perikrone's swamp-to-space identity -- the score is an orbit, the mark
is Saturn, the palette is deep space with a cyan/gold glow. That's also the
modern security-tool look, so it reads as more credible, not less. Framed to land
the human stakes: these aren't abstract findings, they're ways patient
information could get out -- and it hands the practice a real to-do list with
links to the official fix guides.

Self-contained on purpose: all styling inline, no internet, no dependencies.
Prints to a clean light PDF (File -> Print -> Save as PDF)."""

from __future__ import annotations

import html
import math

from .engine import AssessmentResult
from .findings import Finding, Severity

# Severity reframed as *when do I deal with this*.
_ACTION = {
    Severity.CRITICAL: ("Fix now", "crit"),
    Severity.HIGH: ("Fix this week", "high"),
    Severity.MEDIUM: ("Fix this month", "med"),
    Severity.LOW: ("When you can", "low"),
    Severity.INFO: ("Good to know", "info"),
}

_SATURN = """
<svg class="saturn" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
  <defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#6ee7f0"/><stop offset="1" stop-color="#38c6e0"/>
  </linearGradient></defs>
  <ellipse cx="13" cy="13" rx="12" ry="4.2" fill="none" stroke="#e3b23c"
    stroke-width="1.6" transform="rotate(-20 13 13)" opacity=".9"/>
  <circle cx="13" cy="13" r="6.2" fill="url(#pg)"/>
  <ellipse cx="13" cy="13" rx="12" ry="4.2" fill="none" stroke="#e3b23c"
    stroke-width="1.6" transform="rotate(-20 13 13)"
    stroke-dasharray="14 40" opacity=".9"/>
</svg>"""

_CSS = """
:root{
  --ink:#e9eff7; --muted:#9fb1c6; --line:rgba(255,255,255,.10);
  --surface:rgba(255,255,255,.035); --surface2:rgba(255,255,255,.065);
  --brand:#38c6e0; --brand2:#6ee7f0; --saturn:#e3b23c;
  --crit:#ff6b6b; --high:#ff9f45; --med:#ffd43b; --low:#4dabf7;
  --info:#8aa0b6; --good:#51cf66;
}
*{box-sizing:border-box}
body{margin:0;color:var(--ink);
  background:
    radial-gradient(1100px 600px at 80% -10%, rgba(56,198,224,.14), transparent 60%),
    radial-gradient(900px 500px at 0% 0%, rgba(227,178,60,.10), transparent 55%),
    linear-gradient(180deg,#0b1120 0%, #080d18 100%);
  background-attachment:fixed;min-height:100vh;
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:940px;margin:0 auto;padding:34px 20px 70px;}
a{color:var(--brand2);text-decoration:none}
.brandbar{display:flex;align-items:center;gap:10px;margin-bottom:22px}
.brandbar .wordmark{font-size:15px;font-weight:700;letter-spacing:.22em;color:#fff}
.brandbar .tag{color:var(--muted);font-size:12px;letter-spacing:.06em;
  border-left:1px solid var(--line);padding-left:10px}
.saturn{filter:drop-shadow(0 0 6px rgba(56,198,224,.5))}
.head h1{font-size:30px;margin:.1em 0 .18em;letter-spacing:-.01em}
.head .meta{color:var(--muted);font-size:13.5px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;
  padding:26px;margin:22px 0;backdrop-filter:blur(6px)}
.hero{display:flex;gap:30px;align-items:center;flex-wrap:wrap}
.ring{flex:0 0 auto}
.hero .verdict{flex:1 1 300px;min-width:260px}
.hero .verdict h2{margin:.1em 0 .35em;font-size:21px}
.hero .verdict p{margin:.3em 0;color:var(--muted)}
.bottomline{margin-top:18px;border-radius:12px;padding:16px 18px;font-size:15px;
  background:rgba(255,159,69,.08);border:1px solid rgba(255,159,69,.28);
  border-left:4px solid var(--high);color:#ffd9b3}
.bottomline.ok{background:rgba(81,207,102,.08);border-color:rgba(81,207,102,.3);
  border-left-color:var(--good);color:#bdebc8}
.bottomline b{color:#fff}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px}
.scard{flex:1 1 110px;background:var(--surface2);border:1px solid var(--line);
  border-radius:12px;padding:14px 12px;text-align:center}
.scard .n{font-size:30px;font-weight:700;line-height:1}
.scard .l{font-size:12px;color:var(--muted);margin-top:5px;text-transform:uppercase;letter-spacing:.05em}
.scard.crit{border-top:3px solid var(--crit)} .scard.crit .n{color:var(--crit)}
.scard.high{border-top:3px solid var(--high)} .scard.high .n{color:var(--high)}
.scard.med{border-top:3px solid var(--med)}  .scard.med .n{color:var(--med)}
.scard.low{border-top:3px solid var(--low)}  .scard.low .n{color:var(--low)}
h3.section{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--brand);
  margin:38px 4px 10px}
ol.plan{list-style:none;counter-reset:step;margin:0;padding:0}
ol.plan li{counter-increment:step;display:flex;gap:13px;align-items:flex-start;
  background:var(--surface);border:1px solid var(--line);border-radius:12px;
  padding:13px 16px;margin:9px 0}
ol.plan li::before{content:counter(step);flex:0 0 26px;height:26px;border-radius:50%;
  background:var(--surface2);border:1px solid var(--line);color:var(--brand2);
  font-weight:700;font-size:13px;display:flex;align-items:center;justify-content:center}
ol.plan .txt{flex:1 1 auto}
.trend{padding:20px 24px}
.trendhead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
  flex-wrap:wrap;margin-bottom:8px}
.trendnote{font-size:13.5px;color:var(--muted)}
.delta{font-weight:700}
.delta.up{color:var(--good)} .delta.down{color:var(--crit)} .delta.flat{color:var(--muted)}
.trend svg{display:block;margin:6px 0}
.trendfoot{font-size:12.5px;color:var(--muted);margin-top:6px}
details.finding{background:var(--surface);border:1px solid var(--line);border-radius:13px;
  margin:12px 0;overflow:hidden}
details.finding[open]{border-color:rgba(56,198,224,.28)}
summary{list-style:none;cursor:pointer;padding:16px 18px;display:flex;align-items:center;gap:14px}
summary::-webkit-details-marker{display:none}
.pill{flex:0 0 auto;font-size:11.5px;font-weight:700;color:#0b1120;border-radius:999px;
  padding:4px 11px;white-space:nowrap}
.pill.crit{background:var(--crit)} .pill.high{background:var(--high)}
.pill.med{background:var(--med)} .pill.low{background:var(--low)}
.pill.info{background:var(--info);color:#0b1120}
summary .t{flex:1 1 auto;font-weight:600}
summary .chev{flex:0 0 auto;color:var(--muted);transition:transform .15s}
details[open] summary .chev{transform:rotate(90deg)}
.body{padding:2px 18px 20px;border-top:1px solid var(--line)}
.body .stakes{font-size:16px;margin:16px 0 8px}
.body .why{color:var(--muted);margin:10px 0}
.body h4{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--brand);
  margin:20px 0 7px}
.affected{margin:0;padding-left:18px} .affected li{margin:3px 0;color:var(--muted)}
.fix{margin:0;padding-left:20px} .fix li{margin:6px 0}
.links{display:flex;flex-wrap:wrap;gap:9px;margin-top:4px}
.links a{display:inline-flex;align-items:center;gap:7px;font-size:13.5px;font-weight:600;
  background:var(--surface2);border:1px solid rgba(56,198,224,.3);border-radius:9px;
  padding:8px 13px;color:var(--brand2)}
.links a:hover{border-color:var(--brand);background:rgba(56,198,224,.12)}
.links a::before{content:"\\2197";color:var(--brand)}
.fixbox{background:rgba(56,198,224,.06);border:1px solid rgba(56,198,224,.25);
  border-radius:11px;padding:4px 16px 16px;margin-top:16px}
.fixbox h4{color:var(--brand2)}
ol.checklist{list-style:none;margin:6px 0 0;padding:0;counter-reset:fix}
ol.checklist li{counter-increment:fix;display:flex;gap:11px;align-items:flex-start;margin:9px 0}
ol.checklist input{margin-top:3px;width:16px;height:16px;accent-color:var(--brand);flex:0 0 auto}
ol.checklist input:checked + span{color:var(--muted);text-decoration:line-through}
.actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:14px}
.btn{display:inline-flex;align-items:center;gap:7px;font-size:13.5px;font-weight:600;
  border-radius:9px;padding:9px 14px;text-decoration:none;cursor:pointer}
.btn::after{content:"\\2197"}
.btn.primary{background:var(--brand);color:#06121a}
.btn.primary:hover{background:var(--brand2)}
.btn.ghost{background:var(--surface2);border:1px solid rgba(56,198,224,.3);color:var(--brand2)}
.btn.ghost:hover{border-color:var(--brand)}
.btn.fixed{background:#2e8b57;color:#eafff2}
.btn.fixed:hover{background:#39a869}
.btn.fixed::after{content:"\\21BB"}
.hipaa{background:rgba(255,255,255,.03);border:1px solid var(--line);border-radius:9px;
  padding:11px 14px;font-size:13px;color:var(--muted)}
.hipaa code{color:var(--brand2)}
.foot{color:var(--muted);font-size:12.5px;margin-top:34px;border-top:1px solid var(--line);
  padding-top:16px}
@media print{
  body{background:#fff !important;color:#16222e}
  .wrap{max-width:none}
  .card,details.finding,ol.plan li{background:#fff;border-color:#dde3ea;backdrop-filter:none}
  .scard{background:#f6f8fa}
  .brandbar .wordmark{color:#0f6e8c}.saturn{filter:none}
  h3.section,.body h4{color:#0f6e8c}
  a,.hipaa code,.links a{color:#0b5267}
  .fixbox{background:#f3f9fb;border-color:#cde7ef}
  .btn.primary{background:#0f6e8c;color:#fff}.btn.ghost{color:#0b5267;border-color:#cdd9e6}
  .muted,.head .meta,.affected li,.hero .verdict p{color:#5b6b7b}
  .bottomline{background:#fff7f3;color:#5a3418;border-color:#f3d8c9}
  details.finding{break-inside:avoid}summary{cursor:default}
}
"""


def render_html(result: AssessmentResult, interactive: bool = False,
                trend: dict | None = None) -> str:
    score = result.score()
    grade = result.grade()
    counts = result.counts_by_severity()
    ranked = result.ranked()

    verdict_h, verdict_p = _verdict(result)
    hero = f"""
    <div class="card hero">
      {_score_ring(score, grade)}
      <div class="verdict">
        <h2>{html.escape(verdict_h)}</h2>
        <p>{html.escape(verdict_p)}</p>
        {_severity_cards(counts) if not result.clean else ""}
      </div>
    </div>
    {_bottom_line(result)}
    """

    trend_html = _trend_card(trend)
    plan_html = _action_plan(ranked)
    findings_html = ""
    if ranked:
        findings_html = '<h3 class="section">What we found</h3>' + "".join(
            _finding_card(f, interactive) for f in ranked
        )

    resolve_script = (
        "<script>function perikroneResolve(id){"
        "fetch('/resolve?source=demo&check='+encodeURIComponent(id)).then(function(){"
        "if(window.parent&&window.parent.perikroneRescan){window.parent.perikroneRescan();}"
        "else{location.reload();}});}</script>"
    ) if interactive else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Security Posture — {html.escape(result.practice_name)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="brandbar">{_SATURN}<span class="wordmark">PERIKRONE</span>
    <span class="tag">closest-point security</span></div>
  <div class="head">
    <h1>{html.escape(result.practice_name)}</h1>
    <div class="meta">Security posture assessment &middot; {html.escape(result.collected_at)}
      &middot; {result.user_count} accounts reviewed &middot; source: {html.escape(result.source)}</div>
  </div>
  {hero}
  {trend_html}
  {plan_html}
  {findings_html}
  <div class="foot">
    Perikrone reads configuration only &mdash; it never changes anything or touches patient data.
    This report supports, but does not replace, a full HIPAA Security Rule risk analysis
    (45 CFR 164.308(a)(1)(ii)(A)). To save a copy: File &rarr; Print &rarr; Save as PDF.
  </div>
</div>
<script>
  // Open every finding before printing so nothing is hidden in the PDF.
  window.addEventListener('beforeprint',function(){{
    document.querySelectorAll('details.finding').forEach(function(d){{
      d.dataset.wasOpen = d.open ? '1' : '0'; d.open = true;
    }});
  }});
  window.addEventListener('afterprint',function(){{
    document.querySelectorAll('details.finding').forEach(function(d){{
      if(d.dataset.wasOpen === '0') d.open = false;
    }});
  }});
</script>
{resolve_script}
</body>
</html>
"""


def _score_ring(score: int, grade: str) -> str:
    r = 56
    circ = 2 * math.pi * r
    offset = circ * (1 - score / 100)
    color = (
        "var(--good)" if grade in ("A", "B")
        else "var(--med)" if grade == "C"
        else "var(--high)" if grade == "D"
        else "var(--crit)"
    )
    return f"""
    <div class="ring">
      <svg width="150" height="150" viewBox="0 0 150 150" role="img"
           aria-label="Security score {score} of 100, grade {grade}">
        <circle cx="75" cy="75" r="{r}" fill="none" stroke="rgba(255,255,255,.08)"
          stroke-width="12"/>
        <circle cx="75" cy="75" r="{r}" fill="none" stroke="{color}" stroke-width="12"
          stroke-linecap="round" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"
          transform="rotate(-90 75 75)"
          style="filter:drop-shadow(0 0 7px {color})"/>
        <text x="75" y="71" text-anchor="middle" font-size="38" font-weight="700"
          fill="#fff">{score}</text>
        <text x="75" y="95" text-anchor="middle" font-size="12.5"
          fill="var(--muted)">of 100 &middot; grade {grade}</text>
      </svg>
    </div>"""


def _severity_cards(counts: dict[Severity, int]) -> str:
    order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]
    cards = []
    for sev in order:
        if counts[sev]:
            label, cls = _ACTION[sev]
            cards.append(
                f'<div class="scard {cls}"><div class="n">{counts[sev]}</div>'
                f'<div class="l">{label}</div></div>'
            )
    return f'<div class="cards">{"".join(cards)}</div>' if cards else ""


def _action_plan(ranked: list[Finding]) -> str:
    """A single prioritized to-do list: the first fix step from each finding,
    worst first. The thing a practice actually works down."""
    steps = []
    for f in ranked:
        if not f.fix:
            continue
        label, cls = _ACTION[f.severity]
        steps.append(
            f'<li><span class="txt"><span class="pill {cls}">{html.escape(label)}</span> '
            f'{html.escape(f.fix[0])}</span></li>'
        )
    if not steps:
        return ""
    return ('<h3 class="section">Start here &mdash; your action plan</h3>'
            f'<ol class="plan">{"".join(steps)}</ol>')


def _trend_card(trend: dict | None) -> str:
    """Posture-over-time: a sparkline of past scores plus the change since the
    last scan. Needs at least two scans to be meaningful."""
    if not trend:
        return ""
    points = trend.get("points", [])
    if len(points) < 2:
        return ""

    latest = points[-1]
    note = ""
    delta = trend.get("delta")
    if delta:
        d = delta["score"]
        if d > 0:
            cls, arrow, word = "up", "&#9650;", f"up {d}"
        elif d < 0:
            cls, arrow, word = "down", "&#9660;", f"down {abs(d)}"
        else:
            cls, arrow, word = "flat", "&#9644;", "no change"
        bits = [f'<span class="delta {cls}">{arrow} {word} '
                f'point{"" if abs(d) == 1 else "s"}</span>']
        if delta["resolved"]:
            bits.append(f'{_count(delta["resolved"], "issue")} fixed')
        if delta["new"]:
            bits.append(_count(delta["new"], "new issue"))
        note = " &middot; ".join(bits) + " since last scan"

    return f"""
    <div class="card trend">
      <div class="trendhead">
        <h3 class="section" style="margin:0">Posture over time</h3>
        <div class="trendnote">{note}</div>
      </div>
      {_sparkline(points)}
      <div class="trendfoot">{len(points)} scans &middot; now
        {latest["score"]}/100 (grade {latest["grade"]})</div>
    </div>"""


def _sparkline(points: list) -> str:
    w, h, pad = 600, 90, 14
    scores = [p["score"] for p in points]
    n = len(scores)
    grade = points[-1]["grade"]
    color = ("var(--good)" if grade in ("A", "B") else "var(--med)" if grade == "C"
             else "var(--high)" if grade == "D" else "var(--crit)")

    def px(i):
        return pad + i * (w - 2 * pad) / (n - 1)

    def py(s):
        return h - pad - (s / 100) * (h - 2 * pad)

    line = " ".join(f"{px(i):.1f},{py(s):.1f}" for i, s in enumerate(scores))
    area = (f"M {px(0):.1f},{h - pad:.1f} "
            + "".join(f"L {px(i):.1f},{py(s):.1f} " for i, s in enumerate(scores))
            + f"L {px(n - 1):.1f},{h - pad:.1f} Z")
    dots = "".join(
        f'<circle cx="{px(i):.1f}" cy="{py(s):.1f}" r="{4.5 if i == n - 1 else 2.5}" '
        f'fill="{color if i == n - 1 else "var(--muted)"}"/>'
        for i, s in enumerate(scores))
    return f"""
      <svg viewBox="0 0 {w} {h}" width="100%" role="img"
           aria-label="Security score over the last {n} scans">
        <line x1="{pad}" y1="{py(100):.1f}" x2="{w - pad}" y2="{py(100):.1f}"
          stroke="rgba(255,255,255,.07)"/>
        <line x1="{pad}" y1="{py(0):.1f}" x2="{w - pad}" y2="{py(0):.1f}"
          stroke="rgba(255,255,255,.07)"/>
        <path d="{area}" fill="{color}" fill-opacity=".12"/>
        <polyline fill="none" stroke="{color}" stroke-width="2.5"
          stroke-linejoin="round" stroke-linecap="round" points="{line}"/>
        {dots}
      </svg>"""


def _verdict(result: AssessmentResult) -> tuple[str, str]:
    if result.clean:
        return (
            "No gaps found against the five core checks.",
            "Keep checking on a regular schedule — posture drifts as staff and "
            "settings change.",
        )
    n = len(result.findings)
    crit = result.counts_by_severity()[Severity.CRITICAL]
    if crit:
        verb = "needs" if crit == 1 else "need"
        h = f"{_count(n, 'issue')} found — {crit} {verb} attention right now."
    else:
        h = f"{_count(n, 'issue')} found to address."
    return (h, "Here's where this practice stands, worst first, in plain English — "
               "with the fix for each.")


def _bottom_line(result: AssessmentResult) -> str:
    if result.clean:
        return ('<div class="bottomline ok"><b>Bottom line:</b> nothing is exposed '
                'against these checks today. The risk is drift — which is why this '
                'is worth watching, not just checking once.</div>')

    by_id = {}
    for f in result.findings:
        by_id.setdefault(f.check_id, f)

    ways: list[str] = []
    if "no-mfa" in by_id:
        n = len(by_id["no-mfa"].affected)
        ways.append(f"{_count(n, 'account')} that can be opened with just a password")
    if "stale-accounts" in by_id:
        n = len(by_id["stale-accounts"].affected)
        verb = "works" if n == 1 else "work"
        ways.append(f"{_count(n, 'abandoned-looking account')} that still {verb}")
    if "external-access" in by_id:
        n = len(by_id["external-access"].affected)
        ways.append(f"{_count(n, 'outside account')} with standing access")

    settings = []
    if "security-defaults-off" in by_id or "legacy-auth-allowed" in by_id:
        settings.append("basic protections switched off")
    if "admin-sprawl" in by_id:
        settings.append("more administrator accounts than it should have")

    clauses = ways + settings
    core = f"this practice has {_join(clauses)}. " if clauses else ""
    return (
        '<div class="bottomline"><b>Bottom line:</b> ' + core +
        "Each of these is a way patient information could leave without anyone "
        "noticing &mdash; and right now, nothing is watching for it.</div>"
    )


def _finding_card(f: Finding, interactive: bool = False) -> str:
    label, cls = _ACTION[f.severity]
    affected = ""
    if f.affected:
        items = "".join(f"<li>{html.escape(a)}</li>" for a in f.affected)
        affected = f"<h4>Affected</h4><ul class='affected'>{items}</ul>"
    fixbox = ""
    if f.fix or f.fix_links:
        steps = "".join(
            f'<li><input type="checkbox"><span>{html.escape(s)}</span></li>'
            for s in f.fix
        )
        checklist = f"<ol class='checklist'>{steps}</ol>" if steps else ""
        buttons = [
            '<a class="btn primary" href="https://admin.microsoft.com" '
            'target="_blank" rel="noopener">Open the admin console</a>'
        ]
        for text, url in f.fix_links:
            buttons.append(
                f'<a class="btn ghost" href="{html.escape(url)}" '
                f'target="_blank" rel="noopener">{html.escape(text)}</a>'
            )
        if interactive:
            buttons.append(
                f'<button class="btn fixed" type="button" '
                f"onclick=\"perikroneResolve('{html.escape(f.check_id)}')\">"
                f"Mark as fixed &amp; re-scan</button>"
            )
        fixbox = (
            f"<div class='fixbox'><h4>Fix it</h4>{checklist}"
            f"<div class='actions'>{''.join(buttons)}</div></div>"
        )
    hipaa = ""
    if f.hipaa:
        cites = "<br>".join(
            f"<code>{html.escape(c.code)}</code> &mdash; {html.escape(c.name)}"
            for c in f.hipaa
        )
        hipaa = (f"<h4>Why it matters for compliance</h4>"
                 f"<div class='hipaa'>{cites}</div>")
    return f"""
    <details class="finding"{" open" if f.severity >= Severity.HIGH else ""}>
      <summary>
        <span class="pill {cls}">{html.escape(label)}</span>
        <span class="t">{html.escape(f.title)}</span>
        <span class="chev">&#9656;</span>
      </summary>
      <div class="body">
        <p class="stakes"><b>{html.escape(f.summary)}</b></p>
        <p class="why">{html.escape(f.detail)}</p>
        {affected}
        {fixbox}
        {hipaa}
      </div>
    </details>"""


# ---- small text helpers ------------------------------------------------------

def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"

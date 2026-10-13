"""Launch-and-run app mode.

`python3 run.py --serve` starts a tiny local web app, opens it in the browser,
and lets you run an assessment from a button -- with a live scanning screen that
surfaces each risk as the checks fire, then the full dashboard. The "pulls up and
works" experience, not a file you generate from a terminal.

Pure standard library (http.server). Binds to 127.0.0.1 only, so nothing is
exposed off your machine.
"""

from __future__ import annotations

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import history
from .engine import AssessmentResult, assess_by_step
from .report_html import render_html
from .connectors import available_sources, get_connector

# Demo-only: check_ids the user has "marked as fixed" this session, so a re-scan
# shows them clearing and the score climbing. The real connectors re-read reality,
# so this never lies about a live system -- it's the demo's remediation arc.
_resolved: set[str] = set()


def _apply_resolved(result, steps, source):
    if source != "demo" or not _resolved:
        return result, steps
    new_steps = [
        (label, [f for f in found if f.check_id not in _resolved])
        for label, found in steps
    ]
    findings = [f for _label, found in new_steps for f in found]
    new_result = AssessmentResult(
        practice_name=result.practice_name, source=result.source,
        collected_at=result.collected_at, user_count=result.user_count,
        findings=findings,
    )
    return new_result, new_steps

_MARK = """<svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
  <ellipse cx="13" cy="13" rx="12" ry="4.2" fill="none" stroke="#e3b23c" stroke-width="1.6"
    transform="rotate(-20 13 13)"/>
  <circle cx="13" cy="13" r="6.2" fill="#38c6e0"/>
  <ellipse cx="13" cy="13" rx="12" ry="4.2" fill="none" stroke="#e3b23c" stroke-width="1.6"
    transform="rotate(-20 13 13)" stroke-dasharray="14 40"/></svg>"""

_SHELL = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Perikrone</title>
<style>
  :root{--brand:#38c6e0;--brand2:#6ee7f0;--saturn:#e3b23c;--muted:#9fb1c6}
  *{box-sizing:border-box} html,body{height:100%}
  body{margin:0;background:linear-gradient(180deg,#0b1120,#080d18);color:#e9eff7;
    font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    display:flex;flex-direction:column}
  header{display:flex;align-items:center;gap:14px;padding:16px 22px;
    border-bottom:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.02)}
  .wordmark{font-weight:700;letter-spacing:.22em}
  .tag{color:var(--muted);font-size:12px;letter-spacing:.06em;
    border-left:1px solid rgba(255,255,255,.12);padding-left:12px}
  .controls{margin-left:auto;display:flex;align-items:center;gap:12px}
  select{background:#0e1626;color:#e9eff7;border:1px solid rgba(255,255,255,.18);
    border-radius:9px;padding:9px 12px;font-size:14px}
  button{background:var(--brand);color:#06121a;border:0;border-radius:10px;
    padding:10px 18px;font-size:14px;font-weight:700;cursor:pointer}
  button:hover{background:var(--brand2)} button:disabled{opacity:.6;cursor:default}
  main{flex:1 1 auto;position:relative}
  iframe{width:100%;height:100%;border:0;background:#080d18}
  .empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:16px;color:var(--muted);text-align:center;padding:24px}
  .empty svg{filter:drop-shadow(0 0 10px rgba(56,198,224,.5))}
  .hint{max-width:420px;font-size:14px}

  .running{position:absolute;inset:0;display:none;flex-direction:column;padding:28px 30px;overflow:auto}
  .rhead{display:flex;align-items:baseline;justify-content:space-between;gap:16px;
    max-width:780px;width:100%;margin:0 auto 14px}
  .rtitle{font-size:20px;font-weight:600}
  .rcount{color:var(--brand2);font-weight:700;white-space:nowrap}
  .rcount #rrisks{font-size:26px}
  .rbar{height:6px;background:rgba(255,255,255,.08);border-radius:3px;overflow:hidden;
    max-width:780px;width:100%;margin:0 auto 22px}
  #rbarfill{height:100%;width:0;border-radius:3px;
    background:linear-gradient(90deg,var(--brand),var(--saturn));transition:width .4s ease}
  .steps{list-style:none;margin:0 auto;padding:0;max-width:780px;width:100%}
  .step{display:flex;gap:14px;align-items:flex-start;padding:14px 16px;border-radius:12px;
    margin:10px 0;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
    opacity:.4;transition:opacity .3s}
  .step.active,.step.done{opacity:1}
  .step.active{border-color:rgba(56,198,224,.4)}
  .ico{flex:0 0 22px;height:22px;margin-top:1px;display:flex;align-items:center;justify-content:center;
    font-size:18px;font-weight:700}
  .nm{flex:1 1 auto} .nm .lbl{font-weight:600}
  .res{margin-top:2px;font-size:14px}
  .f{display:flex;gap:9px;align-items:center;margin-top:6px;color:#d7e2ee}
  .who{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 2px 2px}
  .chip{font-size:12.5px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);
    border-radius:8px;padding:3px 9px;color:#cdd9e6;opacity:0;animation:pop .35s ease forwards}
  @keyframes pop{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
  .clear{color:#51cf66;font-weight:600}
  .check{color:#51cf66} .warn{color:#ff9f45}
  .dot{width:14px;height:14px;border-radius:50%;border:2px solid rgba(255,255,255,.25)}
  .spinmini{width:18px;height:18px;border:3px solid rgba(255,255,255,.2);
    border-top-color:var(--brand);border-radius:50%;animation:s 1s linear infinite}
  @keyframes s{to{transform:rotate(360deg)}}
  .pill{font-size:11px;font-weight:700;color:#06121a;border-radius:999px;padding:3px 9px;white-space:nowrap}
  .pill.Critical{background:#ff6b6b}.pill.High{background:#ff9f45}.pill.Medium{background:#ffd43b}
  .pill.Low{background:#4dabf7}.pill.Info{background:#8aa0b6}
  .rdone{max-width:780px;width:100%;margin:22px auto 0;display:none}
  .summary{font-size:16px;margin-bottom:14px}
</style></head>
<body>
  <header>
    __MARK__
    <span class="wordmark">PERIKRONE</span>
    <span class="tag">closest-point security</span>
    <div class="controls">
      <label for="src" style="color:var(--muted);font-size:13px">Source</label>
      <select id="src">__OPTIONS__</select>
      <button id="run" onclick="runScan()">Run assessment</button>
    </div>
  </header>
  <main>
    <div class="empty" id="empty">
      <svg width="76" height="76" viewBox="0 0 26 26">
        <ellipse cx="13" cy="13" rx="12" ry="4.2" fill="none" stroke="#e3b23c" stroke-width="1.4"
          transform="rotate(-20 13 13)"/>
        <circle cx="13" cy="13" r="6.2" fill="#38c6e0"/>
        <ellipse cx="13" cy="13" rx="12" ry="4.2" fill="none" stroke="#e3b23c" stroke-width="1.4"
          transform="rotate(-20 13 13)" stroke-dasharray="14 40"/>
      </svg>
      <div class="hint">Pick a source and hit <b>Run assessment</b>. Perikrone will scan it
        live and render the posture dashboard.</div>
    </div>
    <div class="running" id="running">
      <div class="rhead">
        <div class="rtitle">Scanning <span id="rpractice"></span>…</div>
        <div class="rcount"><span id="rrisks">0</span> risks found</div>
      </div>
      <div class="rbar"><div id="rbarfill"></div></div>
      <ul class="steps" id="steps"></ul>
      <div class="rdone" id="rdone"></div>
    </div>
    <iframe id="frame" title="Assessment dashboard" style="display:none"></iframe>
  </main>
<script>
  var curSource=null, _cv=0;
  function el(id){return document.getElementById(id);}
  function esc(s){var d=document.createElement('div'); d.textContent=s; return d.innerHTML;}
  // Called by the dashboard (in the iframe) after a "Mark as fixed" click:
  // re-scan WITHOUT resetting, so the fixed item clears and the score climbs.
  window.perikroneRescan = function(){ runScan(false); };
  function runScan(reset){
    if(reset === undefined){ reset = true; }  // the header button starts fresh
    curSource = el('src').value; _cv = 0;
    el('empty').style.display='none';
    el('frame').style.display='none';
    el('run').disabled=true;
    el('running').style.display='flex';
    el('steps').innerHTML=''; el('rrisks').textContent='0';
    el('rbarfill').style.width='0'; el('rdone').style.display='none';
    var go = function(){
      fetch('/scan.json?source='+encodeURIComponent(curSource))
        .then(function(r){return r.json();})
        .then(function(data){
          if(data.error){
            el('steps').innerHTML='<li class="step done"><span class="ico warn">!</span>'+
              '<div class="nm"><div class="lbl">Could not scan</div>'+
              '<div class="res">'+data.error+'</div></div></li>';
            el('run').disabled=false; return;
          }
          animate(data);
        });
    };
    if(reset){ fetch('/reset').then(go, go); } else { go(); }
  }
  function animate(data){
    el('rpractice').textContent = data.practice;
    var ul = el('steps');
    data.steps.forEach(function(s,i){
      var li=document.createElement('li'); li.className='step'; li.id='step-'+i;
      li.innerHTML='<span class="ico" id="ico-'+i+'"><span class="dot"></span></span>'+
        '<div class="nm"><div class="lbl">'+s.label+'</div>'+
        '<div class="res" id="res-'+i+'"></div></div>';
      ul.appendChild(li);
    });
    var risks=0, i=0, steps=data.steps;
    function step(){
      if(i>=steps.length){ return finish(); }
      var li=el('step-'+i); li.classList.add('active');
      el('ico-'+i).innerHTML='<span class="spinmini"></span>';
      setTimeout(function(){
        var s=steps[i];
        if(!s.findings.length){
          el('ico-'+i).innerHTML='<span class="check">\\u2713</span>';
          el('res-'+i).innerHTML='<span class="clear">Clear</span>';
        } else {
          el('ico-'+i).innerHTML='<span class="warn">\\u26A0</span>';
          el('res-'+i).innerHTML = s.findings.map(function(f){
            var chips = (f.affected||[]).map(function(a,idx){
              return '<span class="chip" style="animation-delay:'+(idx*80)+'ms">'+
                esc(a.split(' <')[0])+'</span>';
            }).join('');
            return '<div class="f"><span class="pill '+f.severity+'">'+f.severity+
              '</span><span>'+esc(f.summary)+'</span></div>'+
              (chips?'<div class="who">'+chips+'</div>':'');
          }).join('');
          risks += s.findings.length; countTo(risks);
        }
        li.classList.remove('active'); li.classList.add('done');
        el('rbarfill').style.width = Math.round((i+1)/steps.length*100)+'%';
        i++; setTimeout(step, 430);
      }, 560);
    }
    function finish(){
      var d=el('rdone');
      d.innerHTML='<div class="summary">Assessment complete &mdash; <b>'+risks+'</b> risk'+
        (risks===1?'':'s')+' &middot; score <b>'+data.score+'/100</b> (grade '+data.grade+')</div>'+
        '<button onclick="showDash()">View full dashboard &rarr;</button>';
      d.style.display='block'; el('run').disabled=false;
    }
    step();
  }
  function countTo(n){
    var cur=_cv, inc=Math.max(1,Math.ceil((n-cur)/6));
    (function tick(){ cur=Math.min(n,cur+inc); el('rrisks').textContent=cur;
      if(cur<n){ setTimeout(tick,45); } else { _cv=n; } })();
  }
  function showDash(){
    var frame=el('frame');
    frame.onload=function(){ el('running').style.display='none'; frame.style.display='block'; };
    frame.src='/dashboard?source='+encodeURIComponent(curSource)+'&t='+Date.now();
  }
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        source = (query.get("source") or ["demo"])[0]
        if parsed.path in ("/", "/index.html"):
            self._send_html(_shell())
        elif parsed.path == "/scan.json":
            self._send_json(self._scan_json(source))
        elif parsed.path == "/dashboard":
            self._send_html(self._dashboard(source))
        elif parsed.path == "/resolve":
            check = (query.get("check") or [""])[0]
            if check:
                _resolved.add(check)
            self._send_json({"ok": True, "resolved": sorted(_resolved)})
        elif parsed.path == "/reset":
            _resolved.clear()
            # Start the demo's trend fresh on a new "Run assessment".
            try:
                demo_name = get_connector("demo").collect().get("practice_name")
                if demo_name:
                    history.clear(demo_name)
            except Exception:
                pass
            self._send_json({"ok": True})
        elif parsed.path == "/health":
            self._send_html("ok")
        else:
            self.send_error(404)

    def _scan_json(self, source: str) -> dict:
        try:
            snapshot = get_connector(source).collect()
        except Exception as exc:
            return {"error": str(exc)}
        result, steps = assess_by_step(snapshot)
        result, steps = _apply_resolved(result, steps, source)
        history.record(result)  # each scan is a point on the trend
        return {
            "practice": result.practice_name,
            "score": result.score(),
            "grade": result.grade(),
            "total": len(result.findings),
            "steps": [
                {
                    "label": label,
                    "findings": [
                        {"title": f.title, "severity": f.severity.label,
                         "summary": f.summary, "affected": f.affected}
                        for f in found
                    ],
                }
                for label, found in steps
            ],
        }

    def _dashboard(self, source: str) -> str:
        try:
            snapshot = get_connector(source).collect()
            result, steps = assess_by_step(snapshot)
            result, _ = _apply_resolved(result, steps, source)
            trend = history.trend_for(result.practice_name)
            return render_html(result, interactive=True, trend=trend)
        except Exception as exc:
            return (f"<body style='font-family:sans-serif;background:#0b1120;color:#e9eff7;"
                    f"padding:40px'><h2>Could not scan '{source}'</h2><p>{exc}</p></body>")

    def _send_html(self, body: str) -> None:
        self._send(body.encode("utf-8"), "text/html; charset=utf-8")

    def _send_json(self, obj: dict) -> None:
        self._send(json.dumps(obj).encode("utf-8"), "application/json")

    def _send(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # keep the console quiet
        pass


def _shell() -> str:
    # 'manual' needs interactive input; 'm365' only works once creds are set.
    skip = {"manual"}
    if not all(os.environ.get(k) for k in (
        "PERIKRONE_M365_TENANT_ID", "PERIKRONE_M365_CLIENT_ID",
        "PERIKRONE_M365_CLIENT_SECRET")):
        skip.add("m365")
    opts = "".join(
        f'<option value="{s}">{s}</option>'
        for s in available_sources() if s not in skip
    )
    return _SHELL.replace("__MARK__", _MARK).replace("__OPTIONS__", opts)


def serve(port: int = 8765, open_browser: bool = True) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Perikrone is running at {url}")
    print("Open it in your browser, hit 'Run assessment', and watch it work.")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()

#!/usr/bin/env python3
"""Perikrone command-line entry point.

    python run.py                      # assess the built-in demo practice
    python run.py --source demo        # same, explicit
    python run.py --data path.json     # demo connector against your own file
    python run.py --out reports/x.md   # choose the output path
    python run.py --print              # also print the full report to screen

Read-only by design: Perikrone reads configuration and reports on it. It never
changes anything in any system.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from perikrone import assess, history, render_markdown
from perikrone.report_html import render_html
from perikrone.connectors import available_sources, get_connector
from perikrone.findings import Severity

_EXT = {"html": ".html", "md": ".md"}

_ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="perikrone",
        description="Read-only security-posture audit for small practices.",
    )
    parser.add_argument(
        "--source", default="demo",
        help=f"data source ({', '.join(available_sources())}); default: demo",
    )
    parser.add_argument(
        "--data", default=None,
        help="path to a JSON snapshot (demo source only)",
    )
    parser.add_argument(
        "--format", default="html", choices=["html", "md", "both"],
        help="report format: html dashboard (default), md, or both",
    )
    parser.add_argument(
        "--out", default=None,
        help="output path (default: reports/<name>-<date>.<ext>)",
    )
    parser.add_argument(
        "--open", dest="auto_open", action="store_true",
        help="open the HTML dashboard in your browser when done",
    )
    parser.add_argument(
        "--print", dest="to_stdout", action="store_true",
        help="also print the Markdown report to the screen",
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="launch the app: open Perikrone in your browser and scan from a button",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="port for --serve (default: 8765)",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="monitor: re-scan on a schedule and alert when posture degrades",
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="seconds between scans in --watch mode (default: 60)",
    )
    parser.add_argument(
        "--cycles", type=int, default=0,
        help="stop --watch after N scans (default: 0 = run until Ctrl+C)",
    )
    parser.add_argument(
        "--simulate-drift", dest="simulate_drift", action="store_true",
        help="demo only: degrade the demo practice after the first scan so an alert fires",
    )
    args = parser.parse_args(argv)

    if args.serve:
        from perikrone.server import serve
        serve(port=args.port)
        return 0

    if args.watch:
        return _watch(args)

    # ---- collect (connector-specific) --------------------------------------
    try:
        kwargs = {"data_path": args.data} if (args.source == "demo" and args.data) else {}
        connector = get_connector(args.source, **kwargs)
        snapshot = connector.collect()
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # ---- assess (source-agnostic) ------------------------------------------
    result = assess(snapshot)
    history.record(result)                       # each run is a point on the trend
    trend = history.trend_for(result.practice_name)

    # ---- render + write -----------------------------------------------------
    formats = ["html", "md"] if args.format == "both" else [args.format]
    written: list[Path] = []
    for fmt in formats:
        ext = _EXT[fmt]
        out_path = (
            Path(args.out) if (args.out and len(formats) == 1)
            else _default_out(result.practice_name, ext)
        )
        content = (render_html(result, trend=trend) if fmt == "html"
                   else render_markdown(result))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)

    _print_summary(result, written)

    if args.to_stdout:
        print("\n" + "-" * 70 + "\n")
        print(render_markdown(result))

    html_report = next((p for p in written if p.suffix == ".html"), None)
    if args.auto_open and html_report:
        import subprocess
        subprocess.run(["open", str(html_report)], check=False)
    return 0


def _watch(args) -> int:
    import time
    from perikrone import monitor

    interval = max(2, args.interval)
    kwargs = {"data_path": args.data} if (args.source == "demo" and args.data) else {}
    print(f"Perikrone monitoring — source: {args.source}, every {interval}s. "
          "Ctrl+C to stop.")
    prev = None
    cycle = 0
    try:
        while True:
            cycle += 1
            try:
                snapshot = get_connector(args.source, **kwargs).collect()
            except (ValueError, FileNotFoundError) as exc:
                print(f"  scan failed: {exc}", file=sys.stderr)
                return 2
            if args.simulate_drift and args.source == "demo" and cycle >= 2:
                snapshot = monitor.apply_demo_drift(snapshot)
            result = assess(snapshot)
            history.record(result)
            stamp = datetime.now().strftime("%H:%M:%S")
            if prev is None:
                print(f"[{stamp}] baseline — {result.practice_name}: "
                      f"{result.score()}/100 ({result.grade()}), "
                      f"{len(result.findings)} findings")
            else:
                alerts = monitor.diff_results(prev, result)
                if monitor.is_degradation(alerts):
                    print(f"[{stamp}] ⚠ ALERT — posture degraded:")
                    for a in alerts:
                        print(f"      - {a.message}")
                    monitor.desktop_notify("Perikrone: posture dropped",
                                           monitor.summary_line(alerts))
                    monitor.log_alerts(result, alerts)
                elif alerts:
                    print(f"[{stamp}] change: " + "; ".join(a.message for a in alerts))
                else:
                    print(f"[{stamp}] no change — stable at "
                          f"{result.score()}/100 ({result.grade()})")
            prev = result
            if args.cycles and cycle >= args.cycles:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nmonitoring stopped.")
    return 0


def _default_out(practice_name: str, ext: str) -> Path:
    slug = "".join(c.lower() if c.isalnum() else "-" for c in practice_name)
    slug = "-".join(filter(None, slug.split("-"))) or "practice"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _ROOT / "reports" / f"{slug}-{date}{ext}"


def _print_summary(result, written: list[Path]) -> None:
    counts = result.counts_by_severity()
    print(f"Perikrone — {result.practice_name}")
    print(f"  source: {result.source}   accounts: {result.user_count}"
          f"   score: {result.score()}/100 ({result.grade()})")
    if result.clean:
        print("  no findings — clean against the five Phase-1 checks.")
    else:
        parts = [
            f"{counts[s]} {s.label.lower()}"
            for s in sorted(Severity, reverse=True) if counts[s]
        ]
        print(f"  findings: {len(result.findings)}  ({', '.join(parts)})")
    for p in written:
        print(f"  report:  {p}")


if __name__ == "__main__":
    raise SystemExit(main())

"""
TimeLeak reports home page.

Scans detector/reports/ for generated scan reports and evaluation
dashboards and builds a single index.html hub linking to all of them.
Every link -- report/dashboard cards and external references alike --
opens in a new tab (target="_blank" + rel="noopener noreferrer"), so this
hub always stays put. Rebuilt automatically after every `main.py scan` /
`main.py experiment`, or on demand via `main.py index`.
"""
import glob
import html
import os
import re
from datetime import datetime

import chatbot

_META_RE = re.compile(r'<meta name="timeleak:([\w-]+)" content="([^"]*)">')

DEMO_APP_URL = "http://127.0.0.1:5000"


def _read_meta(filepath):
    """Pull the timeleak: meta tags out of a generated report's <head>
    without needing a full HTML parser -- cheap and safe since we control
    the exact format these tags are written in."""
    meta = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            head = f.read(4096)
    except OSError:
        return meta
    for key, value in _META_RE.findall(head):
        meta[key] = html.unescape(value)
    return meta


def _relpath(path, base_dir):
    return os.path.relpath(path, base_dir).replace(os.sep, "/")


def _collect_scan_reports(reports_dir):
    items = []
    for path in glob.glob(os.path.join(reports_dir, "report_*.html")):
        meta = _read_meta(path)
        if meta.get("kind") != "scan-report":
            continue
        mtime = os.path.getmtime(path)
        items.append({
            "path": path,
            "href": _relpath(path, reports_dir),
            "endpoint": meta.get("endpoint", "unknown endpoint"),
            "target": meta.get("target", ""),
            "verdict": meta.get("verdict", "no-leak"),
            "confidence": meta.get("confidence", ""),
            "generated": meta.get("generated", ""),
            "mtime": mtime,
        })
    items.sort(key=lambda r: r["mtime"], reverse=True)
    return items


def _collect_dashboards(reports_dir):
    items = []
    exp_dir = os.path.join(reports_dir, "experiments")
    for path in glob.glob(os.path.join(exp_dir, "dashboard_*.html")):
        meta = _read_meta(path)
        if meta.get("kind") != "evaluation-dashboard":
            continue
        mtime = os.path.getmtime(path)
        items.append({
            "path": path,
            "href": _relpath(path, reports_dir),
            "false_positives": meta.get("false-positives", "?"),
            "runs": meta.get("runs", "?"),
            "generated": meta.get("generated", ""),
            "mtime": mtime,
        })
    items.sort(key=lambda r: r["mtime"], reverse=True)
    return items


def _fmt_time(iso_ts):
    try:
        return datetime.fromisoformat(iso_ts).strftime("%b %d, %Y %H:%M UTC")
    except ValueError:
        return iso_ts


def _scan_card(r, index):
    is_leak = r["verdict"] == "leak"
    status_class = "critical" if is_leak else "good"
    badge_text = "LEAK" if is_leak else "NO LEAK"
    endpoint = html.escape(r["endpoint"])
    confidence = html.escape(r["confidence"]) or "&mdash;"
    generated_iso = html.escape(r["generated"])
    generated_abs = html.escape(_fmt_time(r["generated"]))
    href = html.escape(r["href"])
    search_key = html.escape(r["endpoint"].lower())
    return f'''
<a class="card report-card status-{status_class}" href="{href}" target="_blank" rel="noopener noreferrer"
   data-verdict="{'leak' if is_leak else 'clean'}" data-endpoint="{search_key}" data-generated="{generated_iso}"
   style="--stagger:{index}">
  <div class="report-card-top">
    <span class="badge badge-{status_class}">{badge_text}</span>
    <span class="external-icon">→</span>
  </div>
  <div class="report-card-endpoint">{endpoint}</div>
  <div class="report-card-meta">
    <span>Confidence: {confidence}</span>
    <span class="time-ago" data-timestamp="{generated_iso}" title="{generated_abs}">{generated_abs}</span>
  </div>
</a>
'''


def _dashboard_card(r, index):
    fp = r["false_positives"]
    runs = r["runs"]
    fp_class = "good" if fp == "0" else "critical"
    generated_iso = html.escape(r["generated"])
    generated_abs = html.escape(_fmt_time(r["generated"]))
    href = html.escape(r["href"])
    return f'''
<a class="card report-card status-{fp_class}" href="{href}" target="_blank" rel="noopener noreferrer"
   style="--stagger:{index}">
  <div class="report-card-top">
    <span class="badge badge-{fp_class}">{html.escape(str(fp))}/{html.escape(str(runs))} false positives</span>
    <span class="external-icon">→</span>
  </div>
  <div class="report-card-endpoint">Evaluation dashboard</div>
  <div class="report-card-meta">
    <span>Precision · Sensitivity · Sample-size</span>
    <span class="time-ago" data-timestamp="{generated_iso}" title="{generated_abs}">{generated_abs}</span>
  </div>
</a>
'''


def _donut_svg(leak_count, total, size=120, stroke=12):
    import math
    r = (size - stroke) / 2
    circumference = 2 * math.pi * r
    center = size / 2
    pct = (leak_count / total * 100) if total else 0
    return f'''
<svg class="donut-svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="{pct:.0f} percent of scans flagged as leaking">
  <circle class="donut-track" cx="{center}" cy="{center}" r="{r}" stroke-width="{stroke}" fill="none"/>
  <circle class="donut-fill" cx="{center}" cy="{center}" r="{r}" stroke-width="{stroke}" fill="none"
          stroke-linecap="round" transform="rotate(-90 {center} {center})"
          style="--circumference:{circumference:.2f}" data-target="{pct:.1f}"/>
</svg>
'''


def build_index(reports_dir=None):
    """Rebuild detector/reports/index.html from whatever scan reports and
    dashboards currently exist on disk. Returns the file path."""
    if reports_dir is None:
        reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)

    scans = _collect_scan_reports(reports_dir)
    dashboards = _collect_dashboards(reports_dir)

    leak_count = sum(1 for r in scans if r["verdict"] == "leak")
    clean_count = len(scans) - leak_count

    scan_cards = "".join(_scan_card(r, i) for i, r in enumerate(scans)) or (
        '<p class="empty-state">No scan reports yet.<br>Run <code>python main.py scan --url http://localhost:5000/login/v1 '
        '--valid-user alice --invalid-user notauser --samples 100</code> to generate one.</p>'
    )
    dashboard_cards = "".join(_dashboard_card(r, i) for i, r in enumerate(dashboards)) or (
        '<p class="empty-state">No evaluation dashboards yet.<br>Run <code>python main.py experiment --type all</code> to generate one.</p>'
    )

    donut = _donut_svg(leak_count, len(scans))
    now = datetime.now()
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    generated_iso = now.isoformat()

    chatbot_snippet = chatbot.render_chatbot(
        page_entries=[{
            "keywords": ["how many reports", "this hub", "this page", "leak rate", "reports home", "dashboards"],
            "answer": (
                f"This hub currently lists {len(scans)} scan report(s) ({leak_count} flagged as leaking) "
                f"and {len(dashboards)} evaluation dashboard(s). It rebuilds itself automatically after "
                f"every `main.py scan` or `main.py experiment` run."
            ),
        }],
        suggestions=["What's on this page?", "What is CWE-203?", "How do I run a scan?"],
    )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="timeleak:kind" content="index">
<title>TimeLeak</title>
<style>
{_CSS}
{chatbot.CSS}
</style>
</head>
<body>
<div class="scroll-progress" id="scroll-progress"></div>
<div class="topbar">
  <div class="topbar-inner">
    <div class="wordmark"><span class="wordmark-mark"></span><span>TimeLeak</span></div>
    <div class="topbar-right">
      <button class="icon-btn" id="refresh-btn" type="button" aria-label="Refresh this page">
        <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M4 4v5h5M20 20v-5h-5" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
      <button class="theme-toggle" id="theme-toggle" type="button" aria-label="Toggle light and dark theme">
        <svg class="icon-sun" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></g></svg>
        <svg class="icon-moon" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" fill="currentColor"/></svg>
      </button>
    </div>
  </div>
</div>

<div class="page">
  <header class="hero reveal" id="hero">
    <span class="demo-status" id="demo-status" data-demo-url="{DEMO_APP_URL}/health">
      <span class="demo-status-dot"></span><span id="demo-status-text">Checking demo app&hellip;</span>
    </span>
    <h1>Reports home</h1>
    <p class="hero-sub">Every scan and evaluation you've generated, in one place. Click a card to open it in a new tab &mdash; this hub stays put.</p>
    <div class="hero-actions">
      <a class="pill-link" href="{DEMO_APP_URL}" target="_blank" rel="noopener noreferrer">Open demo app ↗</a>
      <a class="pill-link" href="{DEMO_APP_URL}/health" target="_blank" rel="noopener noreferrer">Demo app health ↗</a>
    </div>
  </header>

  <section class="summary-strip reveal">
    <div class="summary-tile">
      <span class="summary-value count-up" data-target="{len(scans)}">0</span>
      <span class="summary-label">scan reports</span>
    </div>
    <div class="summary-tile">
      <span class="summary-value count-up" style="color: {'var(--critical)' if leak_count else 'var(--good)'}" data-target="{leak_count}">0</span>
      <span class="summary-label">flagged as leaking</span>
    </div>
    <div class="summary-tile">
      <span class="summary-value count-up" data-target="{len(dashboards)}">0</span>
      <span class="summary-label">evaluation dashboards</span>
    </div>
    <div class="summary-tile donut-tile">
      <div class="donut-wrap">
        {donut}
        <div class="donut-label">
          <span class="donut-value count-up" data-target="{(leak_count / len(scans) * 100) if scans else 0:.1f}" data-suffix="%">0%</span>
        </div>
      </div>
      <span class="summary-label">leak rate</span>
    </div>
  </section>

  <section class="card quickactions-card reveal">
    <h2>Quick actions</h2>
    <div class="qa-row">
      <div class="qa-text">
        <span class="qa-label">Scan an endpoint</span>
        <code class="qa-code">python main.py scan --url http://localhost:5000/login/v1 --valid-user alice --invalid-user notauser --samples 100</code>
      </div>
      <button class="copy-btn qa-copy" type="button" data-copy="python main.py scan --url http://localhost:5000/login/v1 --valid-user alice --invalid-user notauser --samples 100">Copy</button>
    </div>
    <div class="qa-row">
      <div class="qa-text">
        <span class="qa-label">Run the full evaluation suite</span>
        <code class="qa-code">python main.py experiment --type all</code>
      </div>
      <button class="copy-btn qa-copy" type="button" data-copy="python main.py experiment --type all">Copy</button>
    </div>
    <div class="qa-row">
      <div class="qa-text">
        <span class="qa-label">Rebuild this page</span>
        <code class="qa-code">python main.py index</code>
      </div>
      <button class="copy-btn qa-copy" type="button" data-copy="python main.py index">Copy</button>
    </div>
  </section>

  <section class="reveal" id="scans-section">
    <div class="section-header">
      <h2 class="section-title">Scan reports</h2>
      <div class="controls">
        <input class="search-input" id="scan-search" type="search" placeholder="Filter by endpoint&hellip;" aria-label="Filter scan reports by endpoint">
        <div class="chip-group" id="verdict-filter" role="group" aria-label="Filter by verdict">
          <button class="chip is-active" data-filter="all" type="button">All</button>
          <button class="chip" data-filter="leak" type="button">Leaking</button>
          <button class="chip" data-filter="clean" type="button">Clean</button>
        </div>
        <select class="sort-select" id="scan-sort" aria-label="Sort scan reports">
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </div>
    </div>
    <div class="card-grid" id="scan-grid">
      {scan_cards}
    </div>
    <p class="empty-state" id="no-results" hidden>No reports match that filter.</p>
  </section>

  <section class="reveal">
    <h2 class="section-title">Evaluation dashboards</h2>
    <div class="card-grid">
      {dashboard_cards}
    </div>
  </section>

  <footer class="footer">
    Regenerated <span class="time-ago" data-timestamp="{generated_iso}" title="{html.escape(generated_at)}">{html.escape(generated_at)}</span>
    &middot; run <code>python main.py index</code> to refresh manually
  </footer>
</div>

<div class="toast" id="toast"></div>

{chatbot_snippet}

<script>
{_JS}
{chatbot.JS}
</script>
</body>
</html>
"""

    path = os.path.join(reports_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return path


_CSS = """
:root {
  color-scheme: dark;
  --page-plane: #0a0714;
  --surface-1: #170f2b8f;
  --surface-solid: #1a1330;
  --text-primary: #f4f0ff;
  --text-secondary: #c4b9e0;
  --text-muted: #9a8fc4;
  --border: rgba(196,185,224,0.14);
  --gridline: #2a2140;
  --good: #10b981;
  --critical: #f43f5e;
  --accent: #8b5cf6;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    color-scheme: light;
    --page-plane: #f7f5fb;
    --surface-1: #fdfbffcc;
    --surface-solid: #fdfbff;
    --text-primary: #180f2e;
    --text-secondary: #5b5175;
    --text-muted: #6f6389;
    --border: rgba(24,15,46,0.10);
    --gridline: #e5ddf2;
    --good: #059669;
    --critical: #e11d48;
    --accent: #7c3aed;
  }
}
:root[data-theme="light"] {
  color-scheme: light;
  --page-plane: #f7f5fb;
  --surface-1: #fdfbffcc;
  --surface-solid: #fdfbff;
  --text-primary: #180f2e;
  --text-secondary: #5b5175;
  --text-muted: #6f6389;
  --border: rgba(24,15,46,0.10);
  --gridline: #e5ddf2;
  --good: #059669;
  --critical: #e11d48;
  --accent: #7c3aed;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page-plane: #0a0714;
  --surface-1: #170f2b8f;
  --surface-solid: #1a1330;
  --text-primary: #f4f0ff;
  --text-secondary: #c4b9e0;
  --text-muted: #9a8fc4;
  --border: rgba(196,185,224,0.14);
  --gridline: #2a2140;
  --good: #10b981;
  --critical: #f43f5e;
  --accent: #8b5cf6;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background-color: var(--page-plane);
  background-image:
    linear-gradient(rgba(196,185,224,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(196,185,224,0.05) 1px, transparent 1px),
    radial-gradient(120% 140% at 20% -10%, #3b0764 0%, var(--page-plane) 55%);
  background-size: 44px 44px, 44px 44px, 100% 100%;
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) body {
    background-image:
      linear-gradient(rgba(24,15,46,0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(24,15,46,0.05) 1px, transparent 1px),
      radial-gradient(120% 140% at 20% -10%, #ede9fe 0%, var(--page-plane) 55%);
  }
}
:root[data-theme="light"] body {
  background-image:
    linear-gradient(rgba(24,15,46,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(24,15,46,0.05) 1px, transparent 1px),
    radial-gradient(120% 140% at 20% -10%, #ede9fe 0%, var(--page-plane) 55%);
}
:root[data-theme="dark"] body {
  background-image:
    linear-gradient(rgba(196,185,224,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(196,185,224,0.05) 1px, transparent 1px),
    radial-gradient(120% 140% at 20% -10%, #3b0764 0%, var(--page-plane) 55%);
}

.scroll-progress { position: fixed; top: 0; left: 0; height: 2.5px; width: 0%; background: linear-gradient(90deg, var(--accent), var(--critical)); z-index: 30; transition: width 0.08s linear; }

.topbar {
  position: sticky; top: 0; z-index: 20;
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  background: color-mix(in srgb, var(--page-plane) 72%, transparent);
  border-bottom: 1px solid var(--border);
}
.topbar-inner { max-width: 1080px; margin: 0 auto; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; }
.topbar-right { display: flex; align-items: center; gap: 8px; }
.icon-btn, .theme-toggle {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: 999px;
  border: 1px solid var(--border); background: rgba(127,127,127,0.08);
  color: var(--text-secondary); cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}
.icon-btn:hover { color: var(--text-primary); background: rgba(127,127,127,0.16); transform: rotate(120deg); }
.theme-toggle:hover { color: var(--text-primary); background: rgba(127,127,127,0.16); transform: rotate(-12deg); }
.theme-toggle .icon-moon { display: none; }
:root[data-theme="light"] .theme-toggle .icon-sun,
:root:not([data-theme]) .theme-toggle .icon-sun { display: block; }
:root[data-theme="dark"] .theme-toggle .icon-sun { display: none; }
:root[data-theme="dark"] .theme-toggle .icon-moon { display: block; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) .theme-toggle .icon-sun { display: none; }
  :root:not([data-theme]) .theme-toggle .icon-moon { display: block; }
}

.page { max-width: 1080px; margin: 0 auto; padding: 40px 24px 64px; }
/* Content is visible by default -- JS (if it runs) opts elements into the
   hidden-then-reveal animation via the .js class on <html>. If JS fails to
   load or is blocked, every .reveal element simply stays visible: the
   animation is a pure enhancement, never a requirement for content to show. */
.reveal { transition: opacity 0.6s cubic-bezier(.2,.7,.2,1), transform 0.6s cubic-bezier(.2,.7,.2,1); }
html.js .reveal { opacity: 0; transform: translateY(16px); }
html.js .reveal.in-view { opacity: 1; transform: translateY(0); }

.hero { position: relative; margin-bottom: 8px; padding: 8px 0; --spot-x: 50%; --spot-y: 0%; }
.hero::before {
  content: ""; position: absolute; inset: -20px; z-index: -1; pointer-events: none;
  background: radial-gradient(360px circle at var(--spot-x) var(--spot-y), color-mix(in srgb, var(--accent) 8%, transparent), transparent 70%);
  opacity: 0; transition: opacity 0.3s ease;
}
.hero:hover::before { opacity: 1; }
.hero h1 {
  font-size: clamp(32px, 5vw, 52px); letter-spacing: -0.025em; margin: 0 0 14px;
  background: linear-gradient(135deg, var(--text-primary) 30%, var(--text-secondary));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.demo-status {
  display: inline-flex; align-items: center; gap: 7px; font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
  padding: 5px 12px; border-radius: 999px; border: 1px solid var(--border);
  background: color-mix(in srgb, var(--text-muted) 10%, transparent); color: var(--text-muted);
  margin-bottom: 18px; font-variant-numeric: tabular-nums; transition: background 0.2s ease, color 0.2s ease;
}
.demo-status.is-online { background: color-mix(in srgb, var(--good) 12%, transparent); color: var(--good); }
.demo-status.is-offline { background: color-mix(in srgb, var(--critical) 12%, transparent); color: var(--critical); }
.demo-status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 25%, transparent); }
.hero-sub { color: var(--text-secondary); font-size: 15px; max-width: 62ch; line-height: 1.6; margin: 0 0 22px; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.92em; background: rgba(127,127,127,0.14); padding: 1px 6px; border-radius: 5px; }
.hero-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.pill-link {
  display: inline-flex; align-items: center; gap: 6px;
  border: 1px solid var(--border); background: rgba(127,127,127,0.08); color: var(--text-primary);
  font-size: 13px; font-weight: 600; padding: 9px 16px; border-radius: 999px;
  text-decoration: none; transition: background 0.2s ease, transform 0.15s ease;
}
.pill-link:hover { background: rgba(127,127,127,0.18); transform: translateY(-1px); }

.summary-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 32px 0 24px; }
.summary-tile {
  background: var(--surface-1); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border); border-radius: 16px; padding: 20px; text-align: center;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.summary-tile:hover { transform: translateY(-3px); box-shadow: 0 16px 32px -18px rgba(0,0,0,0.5); }
.summary-value { display: block; font-size: 34px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.summary-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.donut-tile { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.donut-wrap { position: relative; width: 80px; height: 80px; }
.donut-svg { width: 100%; height: 100%; display: block; }
.donut-track { stroke: var(--gridline); }
.donut-fill { stroke: var(--critical); stroke-dasharray: var(--circumference); stroke-dashoffset: var(--circumference); transition: stroke-dashoffset 1.2s cubic-bezier(.2,.8,.2,1) 0.2s; }
.donut-label { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }
.donut-value { font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; }
@media (max-width: 760px) { .summary-strip { grid-template-columns: repeat(2, 1fr); } }

.card {
  background: var(--surface-1); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border); border-radius: 16px;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  transform-style: preserve-3d;
}

.quickactions-card { padding: 24px 28px; margin-bottom: 28px; }
.quickactions-card h2 { font-size: 15px; font-weight: 600; margin: 0 0 16px; }
.qa-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 0; border-top: 1px solid var(--gridline); }
.qa-row:first-of-type { border-top: none; }
.qa-text { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.qa-label { font-size: 12.5px; color: var(--text-muted); }
.qa-code { font-size: 12px; white-space: nowrap; overflow-x: auto; max-width: 60vw; }
.copy-btn {
  flex: none; border: 1px solid var(--border); background: rgba(127,127,127,0.08); color: var(--text-primary);
  font: inherit; font-size: 12px; font-weight: 600; padding: 7px 14px; border-radius: 999px;
  cursor: pointer; transition: background 0.2s ease;
}
.copy-btn:hover { background: rgba(127,127,127,0.18); }
.copy-btn.is-copied { color: var(--good); }

.section-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.section-title { font-size: 15px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin: 0; }
.controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.search-input {
  background: rgba(127,127,127,0.08); border: 1px solid var(--border); border-radius: 999px;
  color: var(--text-primary); font: inherit; font-size: 12.5px; padding: 7px 14px; width: 180px;
  outline: none; transition: border-color 0.15s ease, background 0.15s ease;
}
.search-input:focus { border-color: var(--accent); background: rgba(127,127,127,0.14); }
.search-input::placeholder { color: var(--text-muted); }
.chip-group { display: flex; gap: 2px; background: rgba(127,127,127,0.1); padding: 3px; border-radius: 999px; }
.chip {
  border: none; background: transparent; color: var(--text-secondary);
  font: inherit; font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: 999px;
  cursor: pointer; transition: background 0.2s ease, color 0.2s ease;
}
.chip.is-active { background: var(--surface-solid); color: var(--text-primary); }
.chip:not(.is-active):hover { color: var(--text-primary); }
.sort-select {
  background: rgba(127,127,127,0.08); border: 1px solid var(--border); border-radius: 999px;
  color: var(--text-primary); font: inherit; font-size: 12.5px; padding: 7px 12px;
  outline: none; cursor: pointer;
}

.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-bottom: 40px; }
.report-card {
  display: block; padding: 18px 20px; text-decoration: none; color: inherit;
  border-left: 3px solid transparent;
}
html.js .report-card {
  opacity: 0; transform: translateY(10px);
  animation: card-in 0.5s cubic-bezier(.2,.8,.2,1) forwards;
  animation-delay: calc(var(--stagger, 0) * 60ms);
}
@keyframes card-in { to { opacity: 1; transform: translateY(0); } }
@media (prefers-reduced-motion: reduce) { html.js .report-card { animation: none; opacity: 1; transform: none; } }
.report-card.is-hidden { display: none; }
.report-card:hover { box-shadow: 0 16px 32px -16px rgba(0,0,0,0.5); border-left-color: color-mix(in srgb, var(--text-primary) 14%, var(--border)); }
.status-critical { border-left-color: var(--critical); }
.status-good { border-left-color: var(--good); }
.report-card-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.badge { font-size: 10.5px; font-weight: 700; letter-spacing: 0.05em; padding: 3px 9px; border-radius: 999px; }
.badge-critical { color: var(--critical); background: color-mix(in srgb, var(--critical) 16%, transparent); }
.badge-good { color: var(--good); background: color-mix(in srgb, var(--good) 16%, transparent); }
.external-icon { color: var(--text-muted); font-size: 13px; opacity: 0; transition: opacity 0.15s ease, transform 0.15s ease; }
.report-card:hover .external-icon { opacity: 1; transform: translate(2px, -2px); }
.report-card-endpoint { font-size: 15px; font-weight: 600; margin-bottom: 10px; word-break: break-word; }
.report-card-meta { display: flex; justify-content: space-between; gap: 10px; font-size: 11.5px; color: var(--text-muted); flex-wrap: wrap; }

.empty-state { color: var(--text-muted); font-size: 13.5px; padding: 24px; border: 1px dashed var(--border); border-radius: 14px; line-height: 1.8; }

.toast {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%) translateY(12px);
  background: var(--surface-solid); border: 1px solid var(--border); border-radius: 999px;
  padding: 10px 18px; font-size: 13px; color: var(--text-primary);
  box-shadow: 0 16px 32px rgba(0,0,0,0.35);
  opacity: 0; pointer-events: none; transition: opacity 0.2s ease, transform 0.2s ease;
  z-index: 50;
}
.toast.is-visible { opacity: 1; transform: translateX(-50%) translateY(0); }

.footer { text-align: center; color: var(--text-muted); font-size: 12.5px; margin-top: 32px; }
"""

_JS = """
document.documentElement.classList.add('js');
// navigator.clipboard is unavailable or rejects in some browsers on file://
// pages (treated as a non-secure context) -- fall back to the classic
// hidden-textarea + execCommand('copy') trick, which works everywhere.
function timeleakCopyText(text) {
  return new Promise(function(resolve) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function() { resolve(true); },
        function() { resolve(timeleakFallbackCopy(text)); }
      );
    } else {
      resolve(timeleakFallbackCopy(text));
    }
  });
}
function timeleakFallbackCopy(text) {
  try {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    var ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch (e) {
    return false;
  }
}
(function() {
  // Live demo-app reachability check (helps you know before a scan whether
  // the target is even up), polled periodically since it can start/stop
  // independently of this static page.
  var statusEl = document.getElementById('demo-status');
  var statusTextEl = document.getElementById('demo-status-text');
  function checkDemoApp() {
    if (!statusEl || !statusTextEl) return;
    var url = statusEl.getAttribute('data-demo-url');
    var controller = ('AbortController' in window) ? new AbortController() : null;
    var timer = controller ? setTimeout(function() { controller.abort(); }, 4000) : null;
    fetch(url, { headers: { 'Accept': 'application/json' }, signal: controller ? controller.signal : undefined })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        clearTimeout(timer);
        statusEl.classList.remove('is-offline');
        statusEl.classList.add('is-online');
        statusTextEl.textContent = 'Demo app online · ' + data.requests_served + ' requests served';
      })
      .catch(function() {
        clearTimeout(timer);
        statusEl.classList.remove('is-online');
        statusEl.classList.add('is-offline');
        statusTextEl.textContent = 'Demo app unreachable — start it with python app.py';
      });
  }
  checkDemoApp();
  setInterval(checkDemoApp, 10000);

  // Scroll progress + reveal
  var progressBar = document.getElementById('scroll-progress');
  function updateProgress() {
    var doc = document.documentElement;
    var scrollable = doc.scrollHeight - doc.clientHeight;
    var pct = scrollable > 0 ? (doc.scrollTop / scrollable) * 100 : 0;
    if (progressBar) progressBar.style.width = pct + '%';
  }
  document.addEventListener('scroll', updateProgress, { passive: true });
  updateProgress();

  var revealEls = document.querySelectorAll('.reveal');
  revealEls.forEach(function(el, i) { el.style.transitionDelay = (i * 70) + 'ms'; });
  var io = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) { entry.target.classList.add('in-view'); io.unobserve(entry.target); }
    });
  }, { threshold: 0.1 });
  revealEls.forEach(function(el) { io.observe(el); });

  // Theme toggle
  var themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', function() {
      var root = document.documentElement;
      var current = root.getAttribute('data-theme');
      var systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      var effectiveIsDark = current ? current === 'dark' : systemDark;
      root.setAttribute('data-theme', effectiveIsDark ? 'light' : 'dark');
    });
  }

  // Refresh
  var refreshBtn = document.getElementById('refresh-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', function() { location.reload(); });

  // Count-up numbers
  function countUp(el) {
    var target = parseFloat(el.getAttribute('data-target'));
    var suffix = el.getAttribute('data-suffix') || '';
    if (isNaN(target)) return;
    var duration = 900;
    var start = null;
    var decimals = (el.getAttribute('data-target').split('.')[1] || '').length;
    function step(ts) {
      if (start === null) start = ts;
      var progress = Math.min(1, (ts - start) / duration);
      var eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = target.toFixed(decimals) + suffix;
    }
    requestAnimationFrame(step);
  }
  var countEls = document.querySelectorAll('.count-up');
  var countIo = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) { countUp(entry.target); countIo.unobserve(entry.target); }
    });
  }, { threshold: 0.4 });
  countEls.forEach(function(el) { countIo.observe(el); });

  // Donut ring fill
  requestAnimationFrame(function() {
    document.querySelectorAll('.donut-fill').forEach(function(ring) {
      var target = parseFloat(ring.getAttribute('data-target')) || 0;
      var circumference = parseFloat(getComputedStyle(ring).getPropertyValue('--circumference'));
      var offset = circumference * (1 - target / 100);
      requestAnimationFrame(function() { ring.style.strokeDashoffset = offset; });
    });
  });

  // Relative "time ago" labels, refreshed every 60s
  function timeAgo(iso) {
    var then = new Date(iso).getTime();
    if (isNaN(then)) return null;
    var diffSec = Math.max(0, (Date.now() - then) / 1000);
    if (diffSec < 60) return 'just now';
    var diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + (diffMin === 1 ? ' minute ago' : ' minutes ago');
    var diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return diffHr + (diffHr === 1 ? ' hour ago' : ' hours ago');
    var diffDay = Math.floor(diffHr / 24);
    return diffDay + (diffDay === 1 ? ' day ago' : ' days ago');
  }
  function refreshTimeAgo() {
    document.querySelectorAll('.time-ago').forEach(function(el) {
      var iso = el.getAttribute('data-timestamp');
      var rel = timeAgo(iso);
      if (rel) el.textContent = rel;
    });
  }
  refreshTimeAgo();
  setInterval(refreshTimeAgo, 60000);

  // Hero cursor spotlight
  var hero = document.getElementById('hero');
  if (hero) {
    hero.addEventListener('pointermove', function(e) {
      var rect = hero.getBoundingClientRect();
      hero.style.setProperty('--spot-x', (e.clientX - rect.left) + 'px');
      hero.style.setProperty('--spot-y', (e.clientY - rect.top) + 'px');
    });
  }

  // Copy buttons (quick actions)
  var toast = document.getElementById('toast');
  var toastTimer = null;
  function showToast(text) {
    if (!toast) return;
    toast.textContent = text;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function() { toast.classList.remove('is-visible'); }, 2000);
  }
  document.querySelectorAll('.qa-copy').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var text = btn.getAttribute('data-copy');
      var finish = function(ok) {
        btn.classList.toggle('is-copied', ok);
        var original = btn.textContent;
        btn.textContent = ok ? 'Copied!' : 'Failed';
        showToast(ok ? 'Command copied to clipboard' : 'Could not access clipboard');
        setTimeout(function() { btn.classList.remove('is-copied'); btn.textContent = 'Copy'; }, 1600);
      };
      timeleakCopyText(text).then(finish);
    });
  });

  // Filter + search + sort for scan reports
  var grid = document.getElementById('scan-grid');
  var searchInput = document.getElementById('scan-search');
  var chips = document.querySelectorAll('#verdict-filter .chip');
  var sortSelect = document.getElementById('scan-sort');
  var noResults = document.getElementById('no-results');
  var activeFilter = 'all';

  function applyFilters() {
    if (!grid) return;
    var cards = Array.from(grid.querySelectorAll('.report-card'));
    var query = (searchInput && searchInput.value || '').trim().toLowerCase();
    var visibleCount = 0;
    cards.forEach(function(card) {
      var matchesFilter = activeFilter === 'all' || card.getAttribute('data-verdict') === activeFilter;
      var matchesSearch = !query || (card.getAttribute('data-endpoint') || '').indexOf(query) !== -1;
      var visible = matchesFilter && matchesSearch;
      card.classList.toggle('is-hidden', !visible);
      if (visible) visibleCount += 1;
    });
    if (noResults) noResults.hidden = cards.length === 0 || visibleCount > 0;
  }

  function applySort() {
    if (!grid || !sortSelect) return;
    var cards = Array.from(grid.querySelectorAll('.report-card'));
    cards.sort(function(a, b) {
      var ta = new Date(a.getAttribute('data-generated')).getTime() || 0;
      var tb = new Date(b.getAttribute('data-generated')).getTime() || 0;
      return sortSelect.value === 'oldest' ? ta - tb : tb - ta;
    });
    cards.forEach(function(card) { grid.appendChild(card); });
  }

  if (searchInput) searchInput.addEventListener('input', applyFilters);
  chips.forEach(function(chip) {
    chip.addEventListener('click', function() {
      chips.forEach(function(c) { c.classList.remove('is-active'); });
      chip.classList.add('is-active');
      activeFilter = chip.getAttribute('data-filter');
      applyFilters();
    });
  });
  if (sortSelect) sortSelect.addEventListener('change', applySort);

  // 3D tilt on cards
  document.querySelectorAll('.report-card, .summary-tile').forEach(function(card) {
    card.addEventListener('pointermove', function(e) {
      var rect = card.getBoundingClientRect();
      var px = (e.clientX - rect.left) / rect.width - 0.5;
      var py = (e.clientY - rect.top) / rect.height - 0.5;
      var rx = (-py * 3).toFixed(2);
      var ry = (px * 3).toFixed(2);
      card.style.transform = 'perspective(800px) rotateX(' + rx + 'deg) rotateY(' + ry + 'deg) translateY(-3px)';
    });
    card.addEventListener('pointerleave', function() { card.style.transform = ''; });
  });
})();
"""

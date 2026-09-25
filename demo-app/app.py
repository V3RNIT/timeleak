"""
TimeLeak demo-app: a deliberately vulnerable Flask login/signup service
used as a scan target for the TimeLeak side-channel detector.

Defaults to localhost:5000 for local use. It can also be deployed publicly
(e.g. Render, Railway) as a clearly-labeled, intentionally vulnerable demo
in the spirit of OWASP Juice Shop / WebGoat -- see the top-level README's
Deployment section. Regardless of where it runs, never use real
credentials with it: every endpoint here is intentionally broken, and the
database only ever holds fake seeded users.
"""
import os
import sqlite3
import time
from datetime import datetime, timezone

import bcrypt
from flask import Flask, g, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")

# Cost factor chosen so bcrypt.checkpw() takes roughly 60-100ms on typical
# hardware -- slow enough to produce a clearly measurable timing gap for
# the demo, without making seeding/testing painfully slow.
BCRYPT_ROUNDS = 10

# A hash of a password nobody has, used so "user not found" paths can still
# pay the same bcrypt cost as a real check (v1 skips this on purpose; v3
# uses it deliberately to close the timing gap).
DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-constant-time-padding", bcrypt.gensalt(BCRYPT_ROUNDS))

# Auto-seed on import (not just under __main__) so a production WSGI server
# like gunicorn -- which imports this module directly and never runs the
# __main__ block -- still gets a working database. Free hosting tiers also
# tend to have ephemeral disks, so re-seeding on every fresh boot is the
# correct behavior here, not just a local-dev convenience.
if not os.path.exists(DB_PATH):
    import seed as _seed
    _seed.main()

app = Flask(__name__)

START_TIME = datetime.now(timezone.utc)
_request_count = 0


@app.before_request
def _count_request():
    global _request_count
    _request_count += 1

_LANDING_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TimeLeak demo-app</title>
<style>
  :root {
    --page-plane: #0a0714; --surface: #170f2ba8; --border: rgba(196,185,224,0.14);
    --text-primary: #f4f0ff; --text-secondary: #c4b9e0; --text-muted: #9a8fc4;
    --accent: #8b5cf6; --critical: #f43f5e; --good: #10b981; --warning: #fbbf24;
  }
  * { box-sizing: border-box; }
  html { color-scheme: dark; }
  body {
    margin: 0; min-height: 100vh; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    color: var(--text-primary); background-color: var(--page-plane);
    background-image:
      linear-gradient(rgba(196,185,224,0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(196,185,224,0.05) 1px, transparent 1px),
      radial-gradient(120% 140% at 50% -10%, #3b0764 0%, var(--page-plane) 55%);
    background-size: 44px 44px, 44px 44px, 100% 100%;
    padding: 56px 20px 40px;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 780px; margin: 0 auto; }
  .topline { display: flex; align-items: center; justify-content: space-between; margin-bottom: 44px; flex-wrap: wrap; gap: 12px; }
  .wordmark { display: flex; align-items: center; gap: 9px; font-size: 14px; font-weight: 700; letter-spacing: -0.01em; color: var(--text-secondary); }
  .wordmark-mark { width: 10px; height: 10px; border-radius: 3px; background: linear-gradient(135deg, var(--accent), var(--critical)); }
  .status-pill {
    display: inline-flex; align-items: center; gap: 7px; font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
    padding: 5px 12px; border-radius: 999px; border: 1px solid var(--border);
    background: color-mix(in srgb, var(--good) 12%, transparent); color: var(--good);
    font-variant-numeric: tabular-nums;
  }
  .status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 25%, transparent); }
  h1 {
    font-size: clamp(36px, 6vw, 58px); line-height: 1.02; letter-spacing: -0.03em; margin: 0 0 18px;
    background: linear-gradient(135deg, #ffffff 30%, var(--text-secondary));
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  p.sub { color: var(--text-secondary); font-size: 15.5px; line-height: 1.65; max-width: 62ch; margin: 0 0 40px; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.92em; background: rgba(127,127,127,0.16); padding: 2px 7px; border-radius: 5px; color: var(--text-primary); }

  .section-label { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin: 0 0 14px; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 40px; }
  @media (max-width: 620px) { .grid { grid-template-columns: 1fr; } }
  .ep-card {
    background: var(--surface); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 16px;
    padding: 18px 20px; transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  }
  .ep-card:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--accent) 40%, var(--border)); box-shadow: 0 14px 28px -16px rgba(0,0,0,0.6); }
  .ep-top { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; }
  .method { font-size: 10.5px; font-weight: 800; letter-spacing: 0.04em; padding: 2px 7px; border-radius: 5px; color: var(--accent); background: color-mix(in srgb, var(--accent) 14%, transparent); }
  .method-get { color: var(--good); background: color-mix(in srgb, var(--good) 14%, transparent); }
  .ep-path { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13.5px; font-weight: 600; }
  .ep-desc { font-size: 12.5px; color: var(--text-secondary); line-height: 1.5; }
  .ep-tag { display: inline-block; margin-top: 9px; font-size: 10px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: var(--warning); }
  .ep-tag.ok { color: var(--good); }

  .readout {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 40px;
  }
  @media (max-width: 620px) { .readout { grid-template-columns: 1fr; } }
  .readout-tile { background: var(--surface); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 16px; padding: 16px 18px; }
  .readout-value { display: block; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; margin-bottom: 3px; }
  .readout-label { font-size: 10.5px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

  .footer { font-size: 12.5px; color: var(--text-muted); line-height: 1.8; border-top: 1px solid var(--border); padding-top: 24px; }
  .footer code { display: inline-block; margin-top: 4px; word-break: break-all; }
</style>
</head>
<body>
  <div class="wrap">
    <div class="topline">
      <div class="wordmark"><span class="wordmark-mark"></span><span>TimeLeak demo-app</span></div>
      <span class="status-pill"><span class="status-dot"></span><span id="status-text">RUNNING</span></span>
    </div>

    <h1>Vulnerable login<br>service, on purpose.</h1>
    <p class="sub">A deliberately flawed Flask + SQLite app exposing CWE-203 (Observable Discrepancy) leaks in four different shapes, used as the scan target for the TimeLeak detector. API-only by design &mdash; there's no login form here, just the endpoints below.</p>

    <p class="section-label">Endpoints</p>
    <div class="grid">
      <div class="ep-card">
        <div class="ep-top"><span class="method">POST</span><span class="ep-path">/login/v1</span></div>
        <div class="ep-desc">Timing leak &mdash; bcrypt only runs when the username exists.</div>
        <span class="ep-tag">Leaks</span>
      </div>
      <div class="ep-card">
        <div class="ep-top"><span class="method">POST</span><span class="ep-path">/login/v2</span></div>
        <div class="ep-desc">Response-size leak &mdash; a longer error body on wrong password.</div>
        <span class="ep-tag">Leaks</span>
      </div>
      <div class="ep-card">
        <div class="ep-top"><span class="method">POST</span><span class="ep-path">/login/v3</span></div>
        <div class="ep-desc">Patched control &mdash; constant time and size either way.</div>
        <span class="ep-tag ok">Clean</span>
      </div>
      <div class="ep-card">
        <div class="ep-top"><span class="method">POST</span><span class="ep-path">/signup</span></div>
        <div class="ep-desc">Classic enumeration &mdash; "email already registered" vs generic.</div>
        <span class="ep-tag">Leaks</span>
      </div>
      <div class="ep-card">
        <div class="ep-top"><span class="method method-get">GET</span><span class="ep-path">/health</span></div>
        <div class="ep-desc">Live status &amp; uptime, JSON for scripts, HTML for browsers.</div>
        <span class="ep-tag ok">Utility</span>
      </div>
    </div>

    <p class="section-label">Live readout</p>
    <div class="readout">
      <div class="readout-tile"><span class="readout-value" id="rt-requests">&mdash;</span><span class="readout-label">requests served</span></div>
      <div class="readout-tile"><span class="readout-value" id="rt-uptime">&mdash;</span><span class="readout-label">uptime</span></div>
      <div class="readout-tile"><span class="readout-value" id="rt-since">&mdash;</span><span class="readout-label">started</span></div>
    </div>

    <div class="footer">
      Try it:
      <code>curl -X POST http://127.0.0.1:5000/login/v1 -H "Content-Type: application/json" -d "{\\"username\\":\\"alice\\",\\"password\\":\\"wrong\\"}"</code>
      <br>See <code>demo-app/README.md</code> for full endpoint documentation, or scan it with the TimeLeak detector's <code>main.py scan</code>.
    </div>
  </div>

<script>
(function() {
  var startedAtMs = null;
  function fmtUptime(ms) {
    var s = Math.floor(ms / 1000);
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return (h > 0 ? h + 'h ' : '') + (h > 0 || m > 0 ? m + 'm ' : '') + sec + 's';
  }
  function tick() {
    if (startedAtMs !== null) {
      document.getElementById('rt-uptime').textContent = fmtUptime(Date.now() - startedAtMs);
    }
  }
  function refresh() {
    fetch('/health', { headers: { 'Accept': 'application/json' } })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        document.getElementById('rt-requests').textContent = data.requests_served;
        startedAtMs = new Date(data.started_at).getTime();
        var d = new Date(data.started_at);
        document.getElementById('rt-since').textContent = d.toLocaleTimeString();
        tick();
      })
      .catch(function() { document.getElementById('status-text').textContent = 'UNREACHABLE'; });
  }
  refresh();
  setInterval(refresh, 8000);
  setInterval(tick, 1000);
})();
</script>
</body>
</html>
"""

_HEALTH_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TimeLeak demo-app -- status</title>
<style>
  :root {
    --page-plane: #0a0714; --surface: #170f2b8f; --border: rgba(196,185,224,0.14);
    --text-primary: #f4f0ff; --text-secondary: #c4b9e0; --text-muted: #9a8fc4;
    --accent: #8b5cf6; --critical: #f43f5e; --good: #10b981;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    color: var(--text-primary); background: radial-gradient(120% 140% at 20% -10%, #3b0764 0%, var(--page-plane) 55%);
    display: flex; align-items: center; justify-content: center; padding: 40px 20px;
  }
  .card {
    max-width: 460px; width: 100%; background: var(--surface); backdrop-filter: blur(20px);
    border: 1px solid var(--border); border-radius: 20px; padding: 36px 40px;
  }
  .wordmark { display: flex; align-items: center; gap: 10px; font-size: 15px; font-weight: 700; margin-bottom: 24px; color: var(--text-secondary); }
  .wordmark-mark { width: 10px; height: 10px; border-radius: 3px; background: linear-gradient(135deg, var(--accent), var(--critical)); }
  .status-row { display: flex; align-items: center; gap: 12px; margin-bottom: 28px; }
  .status-dot { width: 14px; height: 14px; border-radius: 50%; background: var(--good); position: relative; flex: none; }
  .status-dot::after {
    content: ""; position: absolute; inset: -6px; border-radius: 50%; border: 1.5px solid var(--good);
    animation: pulse-ring 2s cubic-bezier(.2,.7,.3,1) infinite;
  }
  @keyframes pulse-ring { 0% { transform: scale(0.7); opacity: 0.9; } 100% { transform: scale(1.8); opacity: 0; } }
  .status-text { font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
  .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 24px; }
  .stat-tile { background: rgba(127,127,127,0.08); border: 1px solid var(--border); border-radius: 14px; padding: 14px 16px; }
  .stat-value { display: block; font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; margin-bottom: 3px; }
  .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .ping-row { display: flex; align-items: center; gap: 12px; margin-bottom: 22px; }
  .ping-btn {
    border: none; background: linear-gradient(135deg, var(--accent), var(--critical)); color: #fff;
    font: inherit; font-size: 13px; font-weight: 700; padding: 10px 20px; border-radius: 999px; cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }
  .ping-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 20px -6px color-mix(in srgb, var(--accent) 60%, transparent); }
  .ping-btn:active { transform: scale(0.97); }
  .ping-result { font-size: 12.5px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
  .ping-result strong { color: var(--text-primary); }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.85em; background: rgba(127,127,127,0.14); padding: 1px 6px; border-radius: 5px; }
  .endpoints { font-size: 12px; color: var(--text-muted); line-height: 2; border-top: 1px solid var(--border); padding-top: 16px; }
</style>
</head>
<body>
  <div class="card">
    <div class="wordmark"><span class="wordmark-mark"></span><span>TimeLeak demo-app</span></div>
    <div class="status-row">
      <span class="status-dot"></span>
      <span class="status-text">Healthy</span>
    </div>
    <div class="stat-grid">
      <div class="stat-tile">
        <span class="stat-value" id="uptime">--</span>
        <span class="stat-label">Uptime</span>
      </div>
      <div class="stat-tile">
        <span class="stat-value" id="req-count">--</span>
        <span class="stat-label">Requests served</span>
      </div>
    </div>
    <div class="ping-row">
      <button class="ping-btn" id="ping-btn" type="button">Ping /health</button>
      <span class="ping-result" id="ping-result"></span>
    </div>
    <div class="endpoints">
      <code>GET /</code> &middot; <code>GET /health</code> &middot; <code>POST /login/v1</code> &middot; <code>POST /login/v2</code> &middot; <code>POST /login/v3</code> &middot; <code>POST /signup</code>
    </div>
  </div>
<script>
(function() {
  var startedAt = new Date("__STARTED_AT__").getTime();

  function fmtUptime(ms) {
    var s = Math.floor(ms / 1000);
    var h = Math.floor(s / 3600); s -= h * 3600;
    var m = Math.floor(s / 60); s -= m * 60;
    if (h > 0) return h + "h " + m + "m " + s + "s";
    if (m > 0) return m + "m " + s + "s";
    return s + "s";
  }

  var uptimeEl = document.getElementById("uptime");
  function tick() {
    uptimeEl.textContent = fmtUptime(Date.now() - startedAt);
  }
  tick();
  setInterval(tick, 1000);

  var reqCountEl = document.getElementById("req-count");
  var pingBtn = document.getElementById("ping-btn");
  var pingResult = document.getElementById("ping-result");

  function refresh() {
    var start = performance.now();
    fetch("/health", { headers: { "Accept": "application/json" } })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var elapsed = (performance.now() - start).toFixed(1);
        reqCountEl.textContent = data.requests_served;
        pingResult.innerHTML = "";
        var strong = document.createElement("strong");
        strong.textContent = elapsed + " ms";
        pingResult.appendChild(document.createTextNode("Responded in "));
        pingResult.appendChild(strong);
      })
      .catch(function() {
        pingResult.textContent = "Ping failed -- is the server still running?";
      });
  }
  refresh();
  pingBtn.addEventListener("click", refresh);
})();
</script>
</body>
</html>
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def find_user_by_username(username):
    db = get_db()
    return db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def find_user_by_email(email):
    db = get_db()
    return db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_request_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# /login/v1 -- TIMING LEAK (CWE-203)
#
# Non-existent usernames are rejected immediately. Existing usernames pay
# the cost of a full bcrypt comparison before being rejected. The wall-clock
# gap between the two paths leaks whether a username exists.
# ---------------------------------------------------------------------------
@app.route("/login/v1", methods=["POST"])
def login_v1():
    data = get_request_json()
    username = data.get("username", "")
    password = data.get("password", "")

    # Testing hook for Phase 5's sensitivity experiment: artificially pad
    # the fast (user-not-found) path so the leak can be shrunk on demand.
    inject_delay_ms = request.args.get("inject_delay_ms", default=0, type=float)

    user = find_user_by_username(username)
    if user is None:
        if inject_delay_ms > 0:
            time.sleep(inject_delay_ms / 1000.0)
        return jsonify({"error": "Invalid username or password"}), 401

    ok = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))
    if not ok:
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"success": True, "message": "Login successful"}), 200


# ---------------------------------------------------------------------------
# /login/v2 -- RESPONSE-SIZE LEAK (CWE-203)
#
# Both failure cases return 401, but "wrong password" includes an extra
# hint field, so the response byte count reveals whether the username
# exists even if timing is identical.
# ---------------------------------------------------------------------------
@app.route("/login/v2", methods=["POST"])
def login_v2():
    data = get_request_json()
    username = data.get("username", "")
    password = data.get("password", "")

    user = find_user_by_username(username)
    if user is None:
        return jsonify({"error": "Invalid username or password"}), 401

    ok = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))
    if not ok:
        return jsonify({
            "error": "Invalid username or password",
            "hint": "Please double-check your password and try again. "
                    "If you've forgotten it, use the password reset link "
                    "that was sent to your registered email address.",
        }), 401

    return jsonify({"success": True, "message": "Login successful"}), 200


# ---------------------------------------------------------------------------
# /login/v3 -- PATCHED / CONTROL (no leak)
#
# Every rejection path pays an equivalent bcrypt cost (real or dummy) and
# returns the exact same JSON structure and byte size. This is the "no
# leak" baseline the detector should report as clean.
# ---------------------------------------------------------------------------
@app.route("/login/v3", methods=["POST"])
def login_v3():
    data = get_request_json()
    username = data.get("username", "")
    password = data.get("password", "")

    user = find_user_by_username(username)
    if user is None:
        # Pay the same bcrypt cost against a dummy hash so timing matches
        # the "user exists, wrong password" path.
        bcrypt.checkpw(password.encode("utf-8"), DUMMY_HASH)
        return jsonify({"error": "Invalid username or password"}), 401

    ok = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))
    if not ok:
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"success": True, "message": "Login successful"}), 200


# ---------------------------------------------------------------------------
# /signup -- CLASSIC ENUMERATION LEAK (CWE-203)
#
# Existing emails get an explicit "already registered" message; new emails
# get a generic message. The message content alone reveals registered
# accounts, independent of timing or size.
# ---------------------------------------------------------------------------
@app.route("/signup", methods=["POST"])
def signup():
    data = get_request_json()
    email = data.get("email", "")
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    existing = find_user_by_email(email)
    if existing is not None:
        return jsonify({"error": "Email already registered"}), 409

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")
    db = get_db()
    # Username derived from the email local-part for demo purposes only.
    username = email.split("@")[0]
    db.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, password_hash),
    )
    db.commit()
    return jsonify({"message": "If this email is valid, a confirmation link has been sent."}), 201


@app.route("/", methods=["GET"])
def index():
    return _LANDING_PAGE_HTML


@app.route("/health", methods=["GET"])
def health():
    payload = {
        "status": "ok",
        "started_at": START_TIME.isoformat(),
        "requests_served": _request_count,
    }
    # Programmatic clients (curl, requests, the detector) send Accept: */*
    # and get plain JSON; a real browser explicitly prefers text/html and
    # gets the interactive status page. application/json listed first so a
    # tied wildcard match (the */* case) resolves to JSON, not HTML.
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    if best == "text/html":
        return _HEALTH_PAGE_HTML.replace("__STARTED_AT__", START_TIME.isoformat())
    # CORS-open on this one read-only status endpoint (and only this one) so
    # the reports hub -- a local file:// page, a different origin -- can poll
    # it for a live "is the demo app up" indicator.
    response = jsonify(payload)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response, 200


if __name__ == "__main__":
    # HOST/PORT are only ever set by a hosting platform's environment (e.g.
    # Render sets PORT); local runs fall back to the safe loopback default.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    app.run(host=host, port=port, debug=False)

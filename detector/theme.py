"""
TimeLeak "Evidence File" design system, shared by every generated page.

Each scan report is presented as a forensic case file: blueprint-grid
paper, typewriter body text, condensed display headings, numbered
exhibits, and a rubber-stamp verdict. The interaction patterns borrow from
product launch pages (sticky local nav, pinned scroll-driven story, count-up
figures, highlight carousels, compare tables, bento tiles) and are applied
to the scan's own data.

Pages stay fully self-contained: the two typefaces (both SIL Open Font
License, see assets/fonts/) are base64-inlined at import time, so reports
open offline and never touch a CDN. Everything readable is visible without
JavaScript and in print; motion is layered on top behind `html.js`.
"""
import base64
import os

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

# (family, weight, style, filename)
_FONT_FACES = [
    ("TL Display", 700, "normal", "BarlowCondensed-Bold.woff2"),
    ("TL Display", 800, "normal", "BarlowCondensed-ExtraBold.woff2"),
    ("TL Type", 400, "normal", "CourierPrime-Regular.woff2"),
    ("TL Type", 700, "normal", "CourierPrime-Bold.woff2"),
    ("TL Type", 400, "italic", "CourierPrime-Italic.woff2"),
]

# --- palette (also used by experiments.py for the matplotlib PNGs) --------
# Paper = light theme (default), Blueprint = dark theme. The valid/invalid
# pair is blue ink vs. amber so it stays distinct under common colour-vision
# deficiencies; stamp red and clearance green are reserved for verdicts.
PAPER = "#e9eef3"
SHEET = "#f7f9fb"
GRID = "#cbd6e2"
INK = "#17202b"
FADED = "#5b6878"
VALID = "#1d4ed8"
INVALID = "#c2620a"
STAMP = "#c4122f"
CLEAR = "#13795b"


def _font_face_css():
    """@font-face rules with the woff2 files inlined as data URIs. A missing
    file is skipped rather than fatal -- the stacks below have fallbacks."""
    rules = []
    for family, weight, style, filename in _FONT_FACES:
        path = os.path.join(_FONT_DIR, filename)
        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
        except OSError:
            continue
        rules.append(
            f"@font-face {{ font-family: '{family}'; font-weight: {weight}; font-style: {style}; "
            f"font-display: swap; src: url(data:font/woff2;base64,{data}) format('woff2'); }}"
        )
    return "\n".join(rules)


FONT_CSS = _font_face_css()


THEME_TOGGLE_HTML = """<button class="theme-btn" id="theme-btn" type="button" aria-label="Switch between paper and blueprint theme" title="Paper / Blueprint">
  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M12 3a9 9 0 1 0 0 18V3Z" fill="currentColor"/><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>
</button>"""


def wordmark_html(sub=""):
    sub_html = f'<span class="wm-sub">{sub}</span>' if sub else ""
    return (
        '<a class="wordmark" href="#top" aria-label="Back to top">'
        '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">'
        '<circle cx="12" cy="13" r="8" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M12 13V8.5M12 13l3 2M10 3h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
        f'<span class="wm-name">TimeLeak</span>{sub_html}</a>'
    )


TOKENS_CSS = r"""
:root {
  --paper: #e9eef3; --sheet: #f7f9fb; --grid: #cbd6e2; --grid-strong: #aebccc;
  --ink: #17202b; --ink-2: #334155; --faded: #5b6878;
  --valid: #1d4ed8; --invalid: #c2620a; --stamp: #c4122f; --clear: #13795b; --warn: #a16207;
  --marker: #fde68a; --scrim: rgba(23,32,43,.55); --lift: 0 18px 40px -22px rgba(23,32,43,.45);
  --display: 'TL Display', 'Barlow Condensed', 'Arial Narrow', 'Roboto Condensed', Impact, sans-serif;
  --type: 'TL Type', 'Courier Prime', 'Courier New', ui-monospace, monospace;
  --nav-h: 56px;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #0e1a2b; --sheet: #13233a; --grid: #1c3150; --grid-strong: #2b4669;
    --ink: #e6edf6; --ink-2: #c3cfdd; --faded: #8a9db5;
    --valid: #7fa6ff; --invalid: #ffa452; --stamp: #ff5f6f; --clear: #4fd6a0; --warn: #f5c451;
    --marker: rgba(250,204,21,.32); --scrim: rgba(3,8,16,.7); --lift: 0 18px 40px -20px rgba(0,0,0,.8);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #0e1a2b; --sheet: #13233a; --grid: #1c3150; --grid-strong: #2b4669;
  --ink: #e6edf6; --ink-2: #c3cfdd; --faded: #8a9db5;
  --valid: #7fa6ff; --invalid: #ffa452; --stamp: #ff5f6f; --clear: #4fd6a0; --warn: #f5c451;
  --marker: rgba(250,204,21,.32); --scrim: rgba(3,8,16,.7); --lift: 0 18px 40px -20px rgba(0,0,0,.8);
  color-scheme: dark;
}

"""

BASE_CSS = TOKENS_CSS + r"""
*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: calc(var(--nav-h) + 16px); -webkit-text-size-adjust: 100%; }
body {
  margin: 0; color: var(--ink); background-color: var(--paper);
  background-image: linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 24px 24px; background-position: -1px -1px;
  font-family: var(--type); font-size: 16px; line-height: 1.6;
  -webkit-font-smoothing: antialiased; transition: background-color .4s ease, color .4s ease;
}
a { color: inherit; }
code, kbd { font-family: var(--type); font-size: .92em; background: color-mix(in srgb, var(--ink) 8%, transparent); padding: 1px 6px; border-radius: 3px; }
:focus-visible { outline: 2px solid var(--valid); outline-offset: 3px; }
::selection { background: var(--marker); color: var(--ink); }
h1, h2, h3 { font-family: var(--display); font-weight: 800; text-transform: uppercase; letter-spacing: .01em; line-height: .95; margin: 0; text-wrap: balance; }
p { margin: 0; }

.wrap { max-width: 1140px; margin: 0 auto; padding-inline: 20px; }
.eyebrow { font-family: var(--display); font-weight: 700; font-size: 13px; letter-spacing: .16em; text-transform: uppercase; color: var(--faded); }
.muted { color: var(--faded); }
.num { font-variant-numeric: tabular-nums; }
.v-ink { color: var(--valid); } .i-ink { color: var(--invalid); }

/* ---------- local nav (sticky, product-page style) ---------- */
.lnav {
  position: sticky; top: 0; z-index: 50; height: var(--nav-h);
  background: color-mix(in srgb, var(--paper) 82%, transparent);
  backdrop-filter: saturate(1.4) blur(14px); -webkit-backdrop-filter: saturate(1.4) blur(14px);
  border-bottom: 1px solid var(--grid-strong);
}
.lnav-inner { height: 100%; display: flex; align-items: center; gap: 18px; }
.wordmark { display: inline-flex; align-items: center; gap: 8px; text-decoration: none; flex: none; }
.wm-name { font-family: var(--display); font-weight: 800; font-size: 21px; letter-spacing: .02em; text-transform: uppercase; }
.wm-sub { font-size: 12.5px; color: var(--faded); border-left: 1px solid var(--grid-strong); padding-left: 10px; margin-left: 2px; white-space: nowrap; }
.lnav-links { display: flex; gap: 4px; margin-left: auto; overflow-x: auto; scrollbar-width: none; min-width: 0; }
.lnav-links::-webkit-scrollbar { display: none; }
.lnav-links a {
  font-family: var(--display); font-weight: 700; font-size: 14px; letter-spacing: .08em; text-transform: uppercase;
  text-decoration: none; color: var(--faded); padding: 6px 10px; border-radius: 3px; white-space: nowrap; position: relative;
  transition: color .2s ease;
}
.lnav-links a:hover { color: var(--ink); }
.lnav-links a.is-active { color: var(--ink); }
.lnav-links a.is-active::after { content: ""; position: absolute; left: 10px; right: 10px; bottom: 1px; height: 2px; background: var(--ink); }
.lnav-actions { display: flex; align-items: center; gap: 8px; flex: none; }
.progress { position: absolute; left: 0; bottom: -1px; height: 2px; width: 100%; transform-origin: 0 50%; transform: scaleX(0); background: var(--stamp); }
.progress.is-clear { background: var(--clear); }
@media (max-width: 860px) { .wm-sub { display: none; } }
@media (max-width: 640px) { .lnav-inner { gap: 10px; } .lnav-links a { font-size: 13px; padding: 6px 7px; } .lnav-actions .btn-label { display: none; } }

/* ---------- buttons & controls ---------- */
.btn {
  display: inline-flex; align-items: center; gap: 8px; cursor: pointer; text-decoration: none;
  font-family: var(--display); font-weight: 700; font-size: 14.5px; letter-spacing: .1em; text-transform: uppercase;
  color: var(--ink); background: var(--sheet); border: 1.5px solid var(--ink); border-radius: 3px; padding: 8px 14px;
  transition: background .18s ease, color .18s ease, transform .18s ease, box-shadow .18s ease;
  box-shadow: 3px 3px 0 0 var(--ink);
}
.btn:hover { transform: translate(-1px,-1px); box-shadow: 4px 4px 0 0 var(--ink); }
.btn:active { transform: translate(2px,2px); box-shadow: 1px 1px 0 0 var(--ink); }
.btn-solid { background: var(--ink); color: var(--paper); }
.btn-sm { font-size: 13px; padding: 6px 11px; box-shadow: 2px 2px 0 0 var(--ink); }
.btn-ghost { box-shadow: none; border-color: var(--grid-strong); background: transparent; }
.btn-ghost:hover { box-shadow: none; border-color: var(--ink); transform: none; }
.pill { display: inline-flex; align-items: center; gap: 7px; font-family: var(--display); font-weight: 700; font-size: 13px; letter-spacing: .12em; text-transform: uppercase; padding: 4px 10px; border: 1.5px solid currentColor; border-radius: 3px; white-space: nowrap; }
.pill-leak { color: var(--stamp); } .pill-clear { color: var(--clear); } .pill-warn { color: var(--warn); }
.pill-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.theme-btn { width: 34px; height: 34px; display: grid; place-items: center; cursor: pointer; border: 1.5px solid var(--grid-strong); background: var(--sheet); color: var(--ink); border-radius: 50%; transition: transform .4s cubic-bezier(.3,1.4,.5,1), border-color .2s; }
.theme-btn:hover { border-color: var(--ink); transform: rotate(180deg); }

.seg { position: relative; display: inline-flex; border: 1.5px solid var(--ink); border-radius: 3px; padding: 3px; background: var(--sheet); }
.seg button { position: relative; z-index: 1; border: 0; background: transparent; cursor: pointer; font-family: var(--display); font-weight: 700; font-size: 14px; letter-spacing: .1em; text-transform: uppercase; color: var(--ink); padding: 6px 14px; transition: color .25s ease; }
.seg button[aria-pressed="true"], .seg button[aria-selected="true"] { color: var(--paper); }
.seg-thumb { position: absolute; z-index: 0; top: 3px; bottom: 3px; left: 3px; background: var(--ink); border-radius: 2px; transition: transform .35s cubic-bezier(.3,1.2,.4,1), width .35s cubic-bezier(.3,1.2,.4,1); }

/* ---------- sheets / exhibits ---------- */
.sheet { position: relative; background: var(--sheet); border: 1.5px solid var(--ink); box-shadow: 6px 6px 0 -1.5px var(--sheet), 6px 6px 0 0 var(--ink); }
.exhibit-tab { display: inline-flex; align-items: center; gap: 10px; font-family: var(--display); font-weight: 700; font-size: 14px; letter-spacing: .14em; text-transform: uppercase; background: var(--ink); color: var(--paper); padding: 5px 12px 4px; }
.clip { position: absolute; top: -14px; left: 28px; width: 30px; height: 44px; border: 3px solid var(--faded); border-radius: 12px 12px 14px 14px; border-bottom-color: transparent; transform: rotate(-4deg); opacity: .75; pointer-events: none; }

/* ---------- stamp ---------- */
.stamp {
  --c: var(--stamp); display: inline-grid; justify-items: center; gap: 2px; color: var(--c);
  border: 5px double var(--c); border-radius: 6px; padding: 8px 18px 6px; transform: rotate(-7deg);
  font-family: var(--display); font-weight: 800; text-transform: uppercase; line-height: .9;
  -webkit-mask-image: radial-gradient(circle at 30% 40%, #000 55%, rgba(0,0,0,.82) 70%, #000 85%);
          mask-image: radial-gradient(circle at 30% 40%, #000 55%, rgba(0,0,0,.82) 70%, #000 85%);
}
.stamp-clear { --c: var(--clear); }
.stamp-warn { --c: var(--warn); }
.stamp-word { font-size: clamp(34px, 5vw, 54px); letter-spacing: .06em; }
.stamp-sub { font-size: 13px; letter-spacing: .28em; }
html.js .stamp.will-stamp { opacity: 0; transform: rotate(-7deg) scale(2.4); }
html.js .stamp.is-stamped { animation: stamp-in .5s cubic-bezier(.25,1.6,.45,1) both; }
@keyframes stamp-in { 0% { opacity: 0; transform: rotate(-7deg) scale(2.4); } 60% { opacity: 1; } 100% { opacity: 1; transform: rotate(-7deg) scale(1); } }
.thud { animation: thud .35s ease-out; }
@keyframes thud { 0%,100% { transform: none; } 30% { transform: translateY(3px); } 60% { transform: translateY(-1px); } }

/* ---------- marker highlight (draws in when revealed) ---------- */
.mark { background-image: linear-gradient(transparent 58%, var(--marker) 58%, var(--marker) 92%, transparent 92%); background-repeat: no-repeat; background-size: 100% 100%; padding: 0 2px; }
html.js .mark { background-size: 0% 100%; transition: background-size 1s cubic-bezier(.6,.1,.2,1) .25s; }
html.js .is-in .mark, html.js .mark.is-in { background-size: 100% 100%; }

/* ---------- reveal ---------- */
html.js .reveal { opacity: 0; transform: translateY(28px); transition: opacity .8s cubic-bezier(.2,.7,.2,1), transform .8s cubic-bezier(.2,.7,.2,1); }
html.js .reveal.is-in { opacity: 1; transform: none; }
html.js .reveal-d1 { transition-delay: .08s; } html.js .reveal-d2 { transition-delay: .16s; } html.js .reveal-d3 { transition-delay: .24s; }

/* ---------- section scaffolding ---------- */
.chapter { padding-block: clamp(64px, 10vw, 120px) 0; }
.chapter-head { display: grid; gap: 14px; margin-bottom: 36px; max-width: 760px; }
.chapter-head h2 { font-size: clamp(38px, 6vw, 72px); }
.chapter-head p { color: var(--ink-2); font-size: 17px; max-width: 62ch; }
.chapter-no { font-family: var(--display); font-weight: 700; font-size: 14px; letter-spacing: .18em; color: var(--stamp); text-transform: uppercase; }
.chapter-no.clear { color: var(--clear); }

/* ---------- big figures (launch-page stat lines) ---------- */
.figures { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); border-top: 2px solid var(--ink); border-bottom: 2px solid var(--ink); }
.figure { padding: 22px 18px 20px; border-right: 1px solid var(--grid-strong); display: grid; gap: 4px; align-content: start; }
.figure:last-child { border-right: 0; }
.figure-val { font-family: var(--display); font-weight: 800; font-size: clamp(44px, 6vw, 76px); line-height: .9; letter-spacing: -.01em; font-variant-numeric: tabular-nums; white-space: nowrap; }
.figure-val small { font-size: .42em; letter-spacing: .02em; margin-left: 3px; }
.figure-cap { font-size: 14px; color: var(--ink-2); line-height: 1.45; }
@media (max-width: 820px) { .figures { grid-template-columns: repeat(2, minmax(0,1fr)); } .figure:nth-child(2) { border-right: 0; } .figure:nth-child(-n+2) { border-bottom: 1px solid var(--grid-strong); } }

/* ---------- highlights carousel ---------- */
.hl { position: relative; }
.hl-track { display: grid; grid-auto-flow: column; grid-auto-columns: min(78%, 520px); gap: 20px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 6px 8px 22px 2px; scrollbar-width: none; overscroll-behavior-x: contain; }
.hl-track::-webkit-scrollbar { display: none; }
.hl-card { scroll-snap-align: start; padding: 26px 26px 24px; display: grid; gap: 12px; align-content: start; min-height: 250px; }
.hl-card h3 { font-size: 34px; }
.hl-card p { color: var(--ink-2); }
.hl-step { font-family: var(--display); font-weight: 800; font-size: 64px; line-height: .8; color: transparent; -webkit-text-stroke: 1.5px var(--ink); }
.hl-controls { display: flex; align-items: center; justify-content: center; gap: 14px; margin-top: 4px; }
.hl-dots { display: flex; gap: 8px; align-items: center; padding: 10px 14px; border-radius: 999px; background: color-mix(in srgb, var(--ink) 9%, transparent); }
.hl-dot { position: relative; width: 8px; height: 8px; border-radius: 999px; border: 0; padding: 0; cursor: pointer; background: color-mix(in srgb, var(--ink) 35%, transparent); overflow: hidden; transition: width .35s cubic-bezier(.3,1,.4,1); }
.hl-dot.is-active { width: 44px; }
.hl-dot i { position: absolute; inset: 0; width: 0; background: var(--ink); }
.hl-dot.is-active.is-done i { width: 100%; }
.hl-play { width: 38px; height: 38px; border-radius: 50%; border: 0; cursor: pointer; display: grid; place-items: center; background: color-mix(in srgb, var(--ink) 9%, transparent); color: var(--ink); }
.hl-play .i-play { display: none; } .hl-play.is-paused .i-play { display: block; } .hl-play.is-paused .i-pause { display: none; }

/* ---------- bento ---------- */
.bento { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 18px; }
.tile { padding: 24px; display: grid; gap: 12px; align-content: start; transition: transform .35s cubic-bezier(.2,.8,.2,1), box-shadow .35s; }
.tile:hover { transform: translate(-3px,-3px); box-shadow: 9px 9px 0 -1.5px var(--sheet), 9px 9px 0 0 var(--ink); }
.tile h3 { font-size: 28px; }
.tile p { color: var(--ink-2); font-size: 15px; }
.tile-lg { grid-column: span 4; grid-row: span 2; } .tile-md { grid-column: span 2; } .tile-wide { grid-column: span 3; }
@media (max-width: 900px) { .bento { grid-template-columns: 1fr 1fr; } .tile-lg, .tile-wide { grid-column: span 2; } .tile-md { grid-column: span 1; } .tile-lg { grid-row: auto; } }
@media (max-width: 560px) { .bento { grid-template-columns: 1fr; } .tile-lg, .tile-md, .tile-wide { grid-column: auto; } }
.check { display: inline-grid; place-items: center; width: 26px; height: 26px; border: 1.5px solid var(--clear); color: var(--clear); border-radius: 50%; font-weight: 700; font-size: 14px; flex: none; }
.snippet { font-size: 13.5px; line-height: 1.55; background: var(--paper); border: 1px dashed var(--grid-strong); padding: 12px 14px; overflow-x: auto; white-space: pre; margin: 0; }
.snippet .add { color: var(--clear); font-weight: 700; }

/* ---------- ledger tables ---------- */
.table-scroll { overflow-x: auto; }
.ledger { width: 100%; border-collapse: collapse; font-size: 14.5px; font-variant-numeric: tabular-nums; }
.ledger th, .ledger td { text-align: right; padding: 9px 12px; border-bottom: 1px solid var(--grid-strong); white-space: nowrap; }
.ledger th:first-child, .ledger td:first-child { text-align: left; }
.ledger thead th { font-family: var(--display); font-weight: 700; font-size: 13.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--faded); border-bottom: 2px solid var(--ink); }
.ledger tbody tr { transition: background .15s; }
.ledger tbody tr:hover { background: color-mix(in srgb, var(--marker) 45%, transparent); }

/* ---------- toast, footer ---------- */
.toast { position: fixed; left: 50%; bottom: 26px; z-index: 90; transform: translate(-50%, 20px); opacity: 0; pointer-events: none; background: var(--ink); color: var(--paper); font-family: var(--display); font-weight: 700; letter-spacing: .1em; text-transform: uppercase; font-size: 14px; padding: 10px 18px; border-radius: 3px; transition: opacity .25s, transform .25s; }
.toast.is-on { opacity: 1; transform: translate(-50%, 0); }
.footer { margin-top: clamp(80px, 12vw, 140px); border-top: 3px double var(--ink); padding-block: 22px 60px; display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; font-size: 13.5px; color: var(--faded); }
.footer a { color: var(--ink); }
.footer-links { display: flex; gap: 18px; flex-wrap: wrap; }

.scroll-cue { display: inline-flex; align-items: center; gap: 10px; font-family: var(--display); font-weight: 700; font-size: 13px; letter-spacing: .18em; text-transform: uppercase; color: var(--faded); text-decoration: none; }
.scroll-cue svg { animation: cue 1.8s ease-in-out infinite; }
@keyframes cue { 0%,100% { transform: translateY(0); } 50% { transform: translateY(5px); } }

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}

@media print {
  body { background: #fff !important; color: #000; }
  .lnav, .tl-chatbot, .toast, .no-print, .hl-controls, .scroll-cue { display: none !important; }
  html.js .reveal, html.js .stamp.will-stamp { opacity: 1 !important; transform: none !important; }
  html.js .mark { background-size: 100% 100% !important; }
  .sheet { box-shadow: none; break-inside: avoid; }
  .chapter { padding-top: 32px; }
  .hl-track { grid-auto-flow: row; grid-auto-columns: auto; overflow: visible; }
}
"""


BASE_JS = r"""
document.documentElement.classList.add('js');
var TL = window.TL || (window.TL = {});
(function () {
  var root = document.documentElement;
  TL.reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  /* theme: explicit choice persists; otherwise follow the system */
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  var saved = store('tl-theme');
  if (saved === 'light' || saved === 'dark') root.setAttribute('data-theme', saved);
  var themeBtn = document.getElementById('theme-btn');
  if (themeBtn) themeBtn.addEventListener('click', function () {
    var cur = root.getAttribute('data-theme') ||
      (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    var next = cur === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next); store('tl-theme', next);
    TL.toast(next === 'dark' ? 'Blueprint' : 'Paper');
  });

  /* toast */
  var toastEl = document.getElementById('toast'), toastT;
  TL.toast = function (msg) {
    if (!toastEl) return;
    toastEl.textContent = msg; toastEl.classList.add('is-on');
    clearTimeout(toastT); toastT = setTimeout(function () { toastEl.classList.remove('is-on'); }, 1800);
  };

  /* clipboard with a selection fallback */
  TL.copy = function (text, okMsg) {
    function fallback() {
      var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); TL.toast(okMsg || 'Copied'); } catch (e) { TL.toast('Press Ctrl+C to copy'); }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { TL.toast(okMsg || 'Copied'); }, fallback);
    } else fallback();
  };
  document.querySelectorAll('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () { TL.copy(b.getAttribute('data-copy'), b.getAttribute('data-copy-msg')); });
  });

  /* Blob download (never window.open) */
  TL.download = function (name, text, type) {
    var blob = new Blob([text], { type: type || 'text/plain' });
    var url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 400);
    TL.toast('Saved ' + name);
  };

  /* count-up figures: data-count="78.1" data-dec="1" */
  TL.countUp = function (el) {
    if (el.__done) return; el.__done = true;
    var target = parseFloat(el.getAttribute('data-count'));
    if (isNaN(target)) return;
    var dec = parseInt(el.getAttribute('data-dec') || '0', 10), dur = 1400, t0 = null;
    var fmt = function (v) { return v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }); };
    if (TL.reduced) { el.textContent = fmt(target); return; }
    function step(t) {
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 4);
      el.textContent = fmt(target * e);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  };

  /* reveal on scroll */
  TL.onReveal = [];
  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      var el = en.target; el.classList.add('is-in'); io.unobserve(el);
      el.querySelectorAll('[data-count]').forEach(TL.countUp);
      if (el.hasAttribute('data-count')) TL.countUp(el);
      TL.onReveal.forEach(function (fn) { fn(el); });
    });
  }, { threshold: 0.18, rootMargin: '0px 0px -6% 0px' }) : null;
  TL.observe = function (el) { if (io) io.observe(el); else { el.classList.add('is-in'); el.querySelectorAll('[data-count]').forEach(TL.countUp); } };
  document.querySelectorAll('.reveal, .mark, [data-count]').forEach(function (el) {
    if (el.closest('.reveal') && el.closest('.reveal') !== el) return;
    TL.observe(el);
  });

  /* local nav: progress bar + active section */
  var bar = document.getElementById('progress');
  var links = Array.prototype.slice.call(document.querySelectorAll('.lnav-links a[href^="#"]'));
  var sections = links.map(function (a) { return document.querySelector(a.getAttribute('href')); });
  var ticking = false;
  function onScroll() {
    ticking = false;
    var h = document.documentElement.scrollHeight - window.innerHeight;
    if (bar) bar.style.transform = 'scaleX(' + (h > 0 ? Math.min(1, window.scrollY / h) : 0) + ')';
    var mid = window.innerHeight * 0.35, active = -1;
    sections.forEach(function (s, i) { if (s && s.getBoundingClientRect().top < mid) active = i; });
    links.forEach(function (a, i) {
      var on = i === active; a.classList.toggle('is-active', on);
      if (on && a.scrollIntoView && a.parentNode.scrollWidth > a.parentNode.clientWidth) {
        var p = a.parentNode; p.scrollLeft = a.offsetLeft - p.clientWidth / 2 + a.clientWidth / 2;
      }
    });
    TL.scrollHooks.forEach(function (fn) { fn(); });
  }
  TL.scrollHooks = [];
  window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  window.addEventListener('resize', onScroll);
  TL.refreshScroll = onScroll;

  /* segmented controls: .seg with buttons[data-value]; emits 'seg:change' */
  TL.seg = function (seg, onChange) {
    var btns = seg.querySelectorAll('button'), thumb = seg.querySelector('.seg-thumb');
    function place(b) { if (!thumb) return; thumb.style.width = b.offsetWidth + 'px'; thumb.style.transform = 'translateX(' + (b.offsetLeft - 3) + 'px)'; }
    function pick(b, silent) {
      btns.forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      place(b); if (!silent && onChange) onChange(b.getAttribute('data-value'));
    }
    btns.forEach(function (b) { b.addEventListener('click', function () { pick(b); }); });
    var cur = seg.querySelector('[aria-pressed="true"]') || btns[0];
    requestAnimationFrame(function () { pick(cur, true); });
    window.addEventListener('resize', function () { place(seg.querySelector('[aria-pressed="true"]') || btns[0]); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { place(seg.querySelector('[aria-pressed="true"]') || btns[0]); });
  };

  /* highlights carousel: .hl > .hl-track > .hl-card, .hl-dots, .hl-play */
  TL.carousel = function (hl) {
    var track = hl.querySelector('.hl-track'), cards = track.querySelectorAll('.hl-card');
    var dotsWrap = hl.querySelector('.hl-dots'), play = hl.querySelector('.hl-play');
    var idx = 0, timer = null, paused = TL.reduced, DUR = 5200, dots = [];
    cards.forEach(function (c, i) {
      var d = document.createElement('button'); d.type = 'button'; d.className = 'hl-dot';
      d.setAttribute('aria-label', 'Show item ' + (i + 1)); d.appendChild(document.createElement('i'));
      d.addEventListener('click', function () { go(i, true); }); dotsWrap.appendChild(d); dots.push(d);
    });
    function paint() {
      dots.forEach(function (d, i) {
        var on = i === idx; d.classList.toggle('is-active', on); d.classList.remove('is-done');
        var bar = d.firstChild; bar.style.transition = 'none'; bar.style.width = '0';
        if (on && !paused) { void bar.offsetWidth; bar.style.transition = 'width ' + DUR + 'ms linear'; d.classList.add('is-done'); bar.style.width = ''; }
      });
    }
    function go(i, user) {
      idx = (i + cards.length) % cards.length;
      track.scrollTo({ left: cards[idx].offsetLeft - track.offsetLeft, behavior: TL.reduced ? 'auto' : 'smooth' });
      if (user) { paused = true; if (play) play.classList.add('is-paused'); }
      schedule(); paint();
    }
    function schedule() { clearTimeout(timer); if (!paused) timer = setTimeout(function () { go(idx + 1); }, DUR); }
    if (play) {
      if (paused) play.classList.add('is-paused');
      play.addEventListener('click', function () { paused = !paused; play.classList.toggle('is-paused', paused); schedule(); paint(); });
    }
    var st;
    track.addEventListener('scroll', function () {
      clearTimeout(st); st = setTimeout(function () {
        var best = 0, bd = 1e9;
        cards.forEach(function (c, i) { var d = Math.abs(c.offsetLeft - track.offsetLeft - track.scrollLeft); if (d < bd) { bd = d; best = i; } });
        if (best !== idx) { idx = best; schedule(); paint(); }
      }, 90);
    }, { passive: true });
    var seen = false;
    TL.onReveal.push(function (el) { if (!seen && (el === hl || el.contains(hl))) { seen = true; schedule(); paint(); } });
    paint();
  };
  document.querySelectorAll('.hl').forEach(TL.carousel);

  /* stamps: slam in once visible */
  TL.stamp = function (el) {
    if (!el || el.__stamped) return; el.__stamped = true;
    el.classList.remove('will-stamp'); el.classList.add('is-stamped');
    var host = el.closest('[data-thud]'); if (host && !TL.reduced) { host.classList.remove('thud'); void host.offsetWidth; host.classList.add('thud'); }
  };
  document.querySelectorAll('.stamp[data-auto-stamp]').forEach(function (s) {
    s.classList.add('will-stamp');
    var delay = parseInt(s.getAttribute('data-auto-stamp'), 10) || 0;
    if (!io) { TL.stamp(s); return; }
    var o = new IntersectionObserver(function (en) { if (en[0].isIntersecting) { o.disconnect(); setTimeout(function () { TL.stamp(s); }, delay); } }, { threshold: .6 });
    o.observe(s);
  });

  /* typewriter: [data-type-text] types its own text once */
  document.querySelectorAll('[data-typewriter]').forEach(function (el) {
    if (TL.reduced) return;
    var full = el.textContent; el.textContent = ''; el.classList.add('is-typing');
    var i = 0, speed = parseInt(el.getAttribute('data-typewriter'), 10) || 22;
    (function tick() { el.textContent = full.slice(0, ++i); if (i < full.length) setTimeout(tick, speed); else el.classList.remove('is-typing'); })();
  });

  requestAnimationFrame(onScroll);
})();
"""


def page_head(title, meta_html="", extra_css=""):
    """Common <head> contents. `meta_html` carries the timeleak:* meta tags
    that index_builder reads back (they must stay in the first 4 KB, so they
    go before the inlined fonts)."""
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{meta_html}
<title>{title}</title>
<style>
{BASE_CSS}
{extra_css}
</style>
<style>
{FONT_CSS}
</style>"""


# ---------------------------------------------------------------------------
# Skin: re-dresses the existing report / dashboard / index markup in the
# Evidence File look without rewriting it. Loaded AFTER each page's own CSS.
# Every rule is scoped under `:root:not(#tl)` -- specificity (1,1,0) -- so it
# outranks the old per-theme blocks (at most (0,2,1)) without !important.
# ---------------------------------------------------------------------------
_S = ":root:not(#tl)"

_SKIN_CSS_TEMPLATE = r"""
@S {
  --page-plane: var(--paper); --surface-1: var(--sheet); --surface-solid: var(--sheet);
  --text-primary: var(--ink); --text-secondary: var(--ink-2); --text-muted: var(--faded);
  --border: var(--grid-strong); --gridline: var(--grid);
  --good: var(--clear); --critical: var(--stamp); --warning: var(--warn); --accent: var(--valid);
}
@S body {
  background-color: var(--paper);
  background-image: linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 24px 24px; background-position: -1px -1px;
  font-family: var(--type); color: var(--ink);
}
@S ::selection { background: var(--marker); color: var(--ink); }
@S code { font-family: var(--type); background: color-mix(in srgb, var(--ink) 8%, transparent); color: var(--ink); border-radius: 3px; }

/* display type */
@S h1, @S h2, @S h3, @S .section-title, @S .headline-value, @S .summary-value, @S .stat-tile-value,
@S .ring-value, @S .donut-value, @S .report-card-endpoint, @S .race-time {
  font-family: var(--display); font-weight: 800; letter-spacing: .01em;
}
@S h1, @S h2, @S .section-title { text-transform: uppercase; }
@S .hero h1 { font-size: clamp(48px, 8vw, 96px); line-height: .9; background: none; color: var(--ink); -webkit-text-fill-color: currentColor; }
@S .verdict h1 { font-size: clamp(44px, 7vw, 84px); line-height: .9; }
@S h2 { font-size: 26px; letter-spacing: .03em; }
@S .section-title { font-size: 30px; color: var(--ink); }
@S .stat-tile-value, @S .summary-value, @S .headline-value { font-size: clamp(34px, 4.4vw, 52px); line-height: .95; }
@S .stat-tile-label, @S .summary-label, @S .headline-label, @S .verdict-badge, @S .ring-caption, @S .qa-label {
  font-family: var(--display); font-weight: 700; letter-spacing: .14em; text-transform: uppercase; font-size: 13px; color: var(--faded);
}

/* sheets instead of glass cards */
@S .card, @S .stat-tile, @S .summary-tile, @S .headline-card {
  background: var(--sheet); border: 1.5px solid var(--ink); border-radius: 2px;
  backdrop-filter: none; -webkit-backdrop-filter: none;
  box-shadow: 6px 6px 0 -1.5px var(--sheet), 6px 6px 0 0 var(--ink);
}
@S .headline-card { border-top-width: 6px; }
@S .headline-good { border-top-color: var(--clear); } @S .headline-critical { border-top-color: var(--stamp); } @S .headline-accent { border-top-color: var(--ink); }
@S .report-card { transition: transform .3s cubic-bezier(.2,.8,.2,1), box-shadow .3s; border-left-width: 1.5px; }
@S .report-card::before { content: ""; position: absolute; top: -9px; left: 16px; width: 72px; height: 9px; background: var(--sheet); border: 1.5px solid var(--ink); border-bottom: 0; border-radius: 3px 3px 0 0; }
@S .report-card { position: relative; overflow: visible; margin-top: 9px; }
@S .report-card:hover { transform: translate(-3px, -4px); box-shadow: 10px 11px 0 -1.5px var(--sheet), 10px 11px 0 0 var(--ink); }
@S .report-card.status-critical { border-left: 6px solid var(--stamp); }
@S .report-card.status-good { border-left: 6px solid var(--clear); }

/* nav */
@S .topbar { background: color-mix(in srgb, var(--paper) 84%, transparent); border-bottom: 1px solid var(--grid-strong); backdrop-filter: saturate(1.4) blur(14px); }
@S .wordmark { font-family: var(--display); font-weight: 800; font-size: 22px; letter-spacing: .03em; text-transform: uppercase; color: var(--ink); }
@S .wordmark-mark { display: inline-block; flex: none; box-sizing: border-box; width: 16px; height: 16px; border-radius: 50%; background: none; border: 2.5px solid var(--ink); position: relative; }
@S .wordmark-mark::after { content: ""; position: absolute; left: 5px; top: 1px; width: 2px; height: 6px; background: var(--ink); transform-origin: 1px 5px; animation: tl-tick 4s steps(12) infinite; }
@keyframes tl-tick { to { transform: rotate(360deg); } }
@S .scroll-progress { background: var(--stamp); height: 3px; }

/* buttons, tabs, inputs */
@S .replay-btn, @S .export-btn, @S .copy-btn, @S .samples-toggle, @S .pill-link, @S .icon-btn, @S .theme-toggle, @S .sort-select, @S .search-input, @S .chip-group .chip {
  font-family: var(--display); font-weight: 700; letter-spacing: .1em; text-transform: uppercase; font-size: 13.5px;
  color: var(--ink); background: var(--sheet); border: 1.5px solid var(--ink); border-radius: 3px;
  box-shadow: 2px 2px 0 0 var(--ink); transition: transform .15s ease, box-shadow .15s ease, background .15s, color .15s;
}
@S .search-input { text-transform: none; letter-spacing: .02em; font-family: var(--type); }
@S .replay-btn:hover, @S .export-btn:hover, @S .copy-btn:hover, @S .samples-toggle:hover, @S .pill-link:hover, @S .icon-btn:hover, @S .theme-toggle:hover {
  transform: translate(-1px, -1px); box-shadow: 3px 3px 0 0 var(--ink); background: var(--sheet);
}
@S .replay-btn:active, @S .export-btn:active, @S .copy-btn:active, @S .pill-link:active { transform: translate(2px, 2px); box-shadow: 0 0 0 0 var(--ink); }
@S .theme-toggle, @S .icon-btn { border-radius: 50%; }
@S .chip-group { background: transparent; border: 0; gap: 6px; padding: 0; }
@S .chip-group .chip.is-active { background: var(--ink); color: var(--paper); }
@S .tabs { background: var(--sheet); border: 1.5px solid var(--ink); border-radius: 3px; padding: 3px; }
@S .tab { font-family: var(--display); font-weight: 700; letter-spacing: .1em; text-transform: uppercase; font-size: 14px; border-radius: 2px; color: var(--ink); background: transparent; }
@S .tab.is-active { background: var(--ink); color: var(--paper); box-shadow: none; }

/* pills & badges */
@S .chip-critical, @S .chip-good, @S .badge, @S .topbar-pill, @S .verdict-badge, @S .demo-status {
  font-family: var(--display); font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  background: transparent; border: 1.5px solid currentColor; border-radius: 3px;
}
@S .chip-critical, @S .badge-critical, @S .topbar-pill-critical { color: var(--stamp); }
@S .chip-good, @S .badge-good, @S .topbar-pill-good { color: var(--clear); }
@S .verdict-badge { display: none; }

/* verdict */
@S .verdict { border-left: 1.5px solid var(--ink); overflow: visible; }
@S .verdict-critical { border-top: 6px solid var(--stamp); }
@S .verdict-good { border-top: 6px solid var(--clear); }
@S .verdict-icon { display: none; }
@S .verdict-sentence { font-size: 17px; color: var(--ink-2); max-width: 60ch; }
@S .ring-track { stroke: var(--grid); }
@S .ring-fill-critical { stroke: var(--stamp); } @S .ring-fill-good { stroke: var(--clear); }

/* data colours: valid = blue ink, invalid = amber */
@S .bar-valid, @S .race-dot-valid, @S .seq-tick.seq-valid { fill: var(--valid); background: var(--valid); }
@S .bar-invalid, @S .race-dot-invalid, @S .seq-tick.seq-invalid { fill: var(--invalid); background: var(--invalid); }
@S [style*="#8b5cf6"] { background: var(--valid); }
@S [style*="#ec4899"] { background: var(--invalid); }
@S .race-dot { box-shadow: none; }
@S .race-node { font-family: var(--display); letter-spacing: .1em; text-transform: uppercase; border: 1.5px solid var(--ink); border-radius: 3px; background: var(--sheet); }
@S .race-path { background: repeating-linear-gradient(90deg, var(--grid-strong) 0 6px, transparent 6px 12px); height: 2px; }
@S .axis-label, @S .axis-title { fill: var(--faded); font-family: var(--type); }
@S .gridline { stroke: var(--grid); }
@S .donut-fill { stroke: var(--stamp); } @S .donut-track { stroke: var(--grid); }

/* tables */
@S .stats-table, @S .samples-table { font-family: var(--type); font-variant-numeric: tabular-nums; }
@S .stats-table th, @S .samples-table th { font-family: var(--display); font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--faded); }
@S .stats-table td, @S .stats-table th, @S .samples-table td, @S .samples-table th { border-color: var(--grid-strong); }
@S .samples-table tbody tr:hover, @S .stats-table tbody tr:hover { background: color-mix(in srgb, var(--marker) 45%, transparent); }
@S .test-row { background: color-mix(in srgb, var(--ink) 5%, transparent); border-radius: 2px; }

/* misc report parts */
@S .scenario-num { font-family: var(--display); font-weight: 800; font-size: 34px; background: none; color: transparent; -webkit-text-stroke: 1.5px var(--ink); width: auto; height: auto; }
@S .check-icon { color: var(--clear); background: transparent; border: 1.5px solid var(--clear); }
@S .dot-nav-item { border-radius: 1px; background: var(--grid-strong); }
@S .dot-nav-item.is-active { background: var(--ink); }
@S .toast { background: var(--ink); color: var(--paper); font-family: var(--display); letter-spacing: .1em; text-transform: uppercase; border-radius: 3px; }
@S .tooltip, @S .info-popover { background: var(--ink); color: var(--paper); border-radius: 3px; font-family: var(--type); }
@S .info-btn { border: 1.5px solid var(--faded); color: var(--faded); background: transparent; font-family: var(--type); }
@S .exp-chart { border: 1.5px solid var(--ink); border-radius: 2px; background: #fff; }
@S .lightbox { background: var(--scrim); }
@S .qa-code { background: var(--paper); border: 1px dashed var(--grid-strong); border-radius: 2px; }
@S .footer { border-top: 3px double var(--ink); font-family: var(--type); color: var(--faded); }
@S .footer a, @S .reference-links a { color: var(--ink); }
@S .demo-status-dot { box-shadow: none; }

/* marker highlight + stamp (see theme BASE_CSS for the full versions) */
@S .mark { background-image: linear-gradient(transparent 58%, var(--marker) 58%, var(--marker) 92%, transparent 92%); background-repeat: no-repeat; background-size: 100% 100%; padding: 0 2px; }
html.js .mark { background-size: 0% 100%; transition: background-size 1s cubic-bezier(.6,.1,.2,1) .4s; }
html.js .mark.is-in { background-size: 100% 100%; }
.stamp-slot { display: flex; justify-content: flex-end; }
.hero .stamp-slot { float: right; margin: 6px 10px 12px 20px; }
@media (max-width: 640px) { .hero .stamp-slot { float: none; justify-content: flex-start; margin: 0 0 18px 6px; } }
@S .stamp {
  --c: var(--stamp); display: inline-grid; justify-items: center; gap: 3px; color: var(--c);
  border: 5px double var(--c); border-radius: 6px; padding: 8px 18px 6px; transform: rotate(-7deg);
  font-family: var(--display); font-weight: 800; text-transform: uppercase; line-height: .9; white-space: nowrap;
}
@S .stamp-clear { --c: var(--clear); } @S .stamp-warn { --c: var(--warn); }
.stamp-word { font-size: clamp(30px, 4.4vw, 48px); letter-spacing: .06em; }
.stamp-sub { font-size: 12.5px; letter-spacing: .26em; }
html.js .stamp.will-stamp { opacity: 0; }
html.js .stamp.is-stamped { animation: tl-stamp .5s cubic-bezier(.25,1.6,.45,1) both; }
@keyframes tl-stamp { 0% { opacity: 0; transform: rotate(-7deg) scale(2.4); } 60% { opacity: 1; } 100% { opacity: 1; transform: rotate(-7deg) scale(1); } }
.thud { animation: tl-thud .35s ease-out; }
@keyframes tl-thud { 0%,100% { transform: none; } 30% { transform: translateY(3px); } 60% { transform: translateY(-1px); } }

/* assistant widget */
@S .tl-fab { background: var(--ink); color: var(--paper); border-radius: 4px; animation: none; box-shadow: 3px 3px 0 0 var(--stamp); }
@S .tl-fab:hover { transform: translate(-1px,-1px); box-shadow: 4px 4px 0 0 var(--stamp); }
@S .tl-panel { background: var(--sheet); border: 1.5px solid var(--ink); border-radius: 2px; box-shadow: 8px 8px 0 -1.5px var(--sheet), 8px 8px 0 0 var(--ink); font-family: var(--type); }
@S .tl-panel-title { font-family: var(--display); font-weight: 800; font-size: 18px; letter-spacing: .06em; text-transform: uppercase; }
@S .tl-panel-dot { box-shadow: none; }
@S .tl-msg { border-radius: 2px; font-family: var(--type); }
@S .tl-msg-bot { background: color-mix(in srgb, var(--marker) 55%, transparent); color: var(--ink); }
@S .tl-msg-user { background: var(--ink); color: var(--paper); }
@S .tl-typing { background: color-mix(in srgb, var(--marker) 55%, transparent); border-radius: 2px; }
@S .tl-chip { font-family: var(--display); font-weight: 700; letter-spacing: .08em; text-transform: uppercase; border: 1.5px solid var(--ink); border-radius: 3px; color: var(--ink); background: transparent; }
@S .tl-chip:hover { background: var(--ink); color: var(--paper); }
@S .tl-input { font-family: var(--type); border-radius: 3px; border: 1.5px solid var(--grid-strong); background: var(--paper); }
@S .tl-input:focus { border-color: var(--ink); }
@S .tl-send { background: var(--ink); color: var(--paper); border-radius: 3px; }

@media print {
  @S body { background: #fff; }
  html.js .stamp.will-stamp { opacity: 1; }
  html.js .mark { background-size: 100% 100%; }
}
"""

SKIN_CSS = TOKENS_CSS + _SKIN_CSS_TEMPLATE.replace("@S", _S)

SKIN_JS = r"""
(function () {
  var reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  function stamp(el) {
    el.classList.remove('will-stamp'); el.classList.add('is-stamped');
    var host = el.closest('[data-thud]');
    if (host && !reduced) { host.classList.remove('thud'); void host.offsetWidth; host.classList.add('thud'); }
  }
  var stamps = document.querySelectorAll('.stamp[data-auto-stamp]');
  var marks = document.querySelectorAll('.mark');
  if (!('IntersectionObserver' in window)) { marks.forEach(function (m) { m.classList.add('is-in'); }); return; }
  stamps.forEach(function (s) {
    s.classList.add('will-stamp');
    var delay = parseInt(s.getAttribute('data-auto-stamp'), 10) || 0;
    var o = new IntersectionObserver(function (en) {
      if (en[0].isIntersecting) { o.disconnect(); setTimeout(function () { stamp(s); }, delay); }
    }, { threshold: .5 });
    o.observe(s);
  });
  var mo = new IntersectionObserver(function (en) {
    en.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); mo.unobserve(e.target); } });
  }, { threshold: .6 });
  marks.forEach(function (m) { mo.observe(m); });
})();
"""


def skin_style():
    """<style> blocks to place after a page's own CSS: fonts, palette, skin."""
    return f"<style>\n{FONT_CSS}\n</style>\n<style>\n{SKIN_CSS}\n</style>"


def stamp_html(word, sub, kind="leak", delay_ms=250):
    """Rubber-stamp verdict. kind: 'leak' (red), 'clear' (green), 'warn'."""
    cls = {"leak": "", "clear": " stamp-clear", "warn": " stamp-warn"}.get(kind, "")
    return (
        f'<div class="stamp{cls}" data-auto-stamp="{delay_ms}" role="img" aria-label="{word}, {sub}">'
        f'<span class="stamp-word">{word}</span><span class="stamp-sub">{sub}</span></div>'
    )

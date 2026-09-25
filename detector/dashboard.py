"""
TimeLeak evaluation dashboard.

A single self-contained HTML page that ties together the three Phase 5
experiments (precision, sensitivity, sample-size) into one visual summary,
reusing the same dark-glass design language as report.py. The matplotlib
PNGs are embedded as base64 data URIs so the page stays a single portable
file.
"""
import base64
import html
import os
from datetime import datetime, timezone

import chatbot

ACCENT = "#8b5cf6"
GOOD = "#10b981"
CRITICAL = "#f43f5e"
WARNING = "#fbbf24"


def _b64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _min_detectable_delay(sensitivity_rows):
    """Largest injected delay (smallest resulting gap) that was still
    correctly flagged as a leak -- i.e. the sensitivity boundary."""
    detected = [r for r in sensitivity_rows if r["leak_detected"]]
    if not detected:
        return None
    return min(detected, key=lambda r: r["resulting_gap_ms"])


def _min_reliable_n(sample_size_rows):
    """Smallest N tested at which the leak was already detected."""
    detected = sorted([r for r in sample_size_rows if r["leak_detected"]], key=lambda r: r["n_samples"])
    return detected[0]["n_samples"] if detected else None


def generate_experiments_dashboard(precision, sensitivity, sample_size, output_dir=None):
    """
    precision / sensitivity / sample_size: the dicts returned by
    experiments.run_precision_test / run_sensitivity_test /
    run_sample_size_study (each has 'rows', 'csv', 'png', plus
    precision's 'false_positives' / 'runs').
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "experiments")
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    filename = f"dashboard_{now.strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(output_dir, filename)

    precision_img = _b64_image(precision["png"])
    sensitivity_img = _b64_image(sensitivity["png"])
    sample_size_img = _b64_image(sample_size["png"])

    fp = precision["false_positives"]
    runs = precision["runs"]
    precision_pct = 100 * (1 - fp / runs) if runs else 0
    precision_status = "good" if fp == 0 else "critical"
    precision_headline = "0 false positives" if fp == 0 else f"{fp} false positive(s)"

    boundary = _min_detectable_delay(sensitivity["rows"])
    if boundary:
        sensitivity_headline = f"~{boundary['resulting_gap_ms']:.1f} ms gap"
        sensitivity_sub = f"still detected at {boundary['injected_delay_ms']} ms injected delay"
    else:
        sensitivity_headline = "no gap detected"
        sensitivity_sub = "leak was masked at every tested delay"

    min_n = _min_reliable_n(sample_size["rows"])
    if min_n:
        samplesize_headline = f"N = {min_n}"
        samplesize_sub = "smallest tested sample size with a significant result"
    else:
        samplesize_headline = "not reached"
        samplesize_sub = "no tested sample size reached significance"

    chatbot_snippet = chatbot.render_chatbot(
        page_entries=[{
            "keywords": ["these experiments", "this dashboard", "precision", "sensitivity", "sample size", "sample-size", "false positive"],
            "answer": (
                f"Precision: {precision_headline} across {runs} runs against /login/v3. "
                f"Sensitivity: {sensitivity_headline} — {sensitivity_sub}. "
                f"Sample-size: {samplesize_headline} — {samplesize_sub}."
            ),
        }],
        suggestions=["What do these experiments show?", "What is Cohen's d?", "How do I run experiments?"],
    )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="timeleak:kind" content="evaluation-dashboard">
<meta name="timeleak:false-positives" content="{fp}">
<meta name="timeleak:runs" content="{runs}">
<meta name="timeleak:generated" content="{now.isoformat()}">
<title>TimeLeak Evaluation Dashboard</title>
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
      <span class="topbar-label">Evaluation dashboard</span>
      <button class="theme-toggle" id="theme-toggle" type="button" aria-label="Toggle light and dark theme">
        <svg class="icon-sun" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></g></svg>
        <svg class="icon-moon" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" fill="currentColor"/></svg>
      </button>
    </div>
  </div>
</div>

<div class="page">
  <header class="hero reveal" id="hero">
    <h1>Detector evaluation</h1>
    <p class="hero-sub">Three experiments characterizing TimeLeak itself: does it avoid false positives, how small a leak can it catch, and how many samples does it need. Generated {generated_at}.</p>
  </header>

  <section class="headline-grid">
    <div class="card headline-card headline-{precision_status} reveal">
      <span class="headline-label">Precision</span>
      <span class="headline-value">{precision_headline}</span>
      <span class="headline-sub">across {runs} runs against the patched /login/v3 endpoint</span>
    </div>
    <div class="card headline-card headline-accent reveal">
      <span class="headline-label">Sensitivity</span>
      <span class="headline-value">{sensitivity_headline}</span>
      <span class="headline-sub">{sensitivity_sub}</span>
    </div>
    <div class="card headline-card headline-accent reveal">
      <span class="headline-label">Sample-size</span>
      <span class="headline-value">{samplesize_headline}</span>
      <span class="headline-sub">{samplesize_sub}</span>
    </div>
  </section>

  <section class="card exp-card reveal">
    <h2>1. Precision test</h2>
    <p class="exp-copy">Ran the detector {runs} times against <code>/login/v3</code> (the patched, constant-time/size control) to check for false positives — cases where the detector would flag a leak that isn't really there.</p>
    <img class="exp-chart" src="data:image/png;base64,{precision_img}" alt="Precision test chart" tabindex="0" role="button" aria-label="Enlarge precision test chart">
  </section>

  <section class="card exp-card reveal">
    <h2>2. Sensitivity test</h2>
    <p class="exp-copy">Ran the detector against <code>/login/v1</code> while artificially padding the "user not found" path with <code>?inject_delay_ms=</code>, shrinking the real timing gap step by step, to find the smallest leak TimeLeak can still catch.</p>
    <img class="exp-chart" src="data:image/png;base64,{sensitivity_img}" alt="Sensitivity test chart" tabindex="0" role="button" aria-label="Enlarge sensitivity test chart">
  </section>

  <section class="card exp-card reveal">
    <h2>3. Sample-size study</h2>
    <p class="exp-copy">Ran the detector against <code>/login/v1</code> with increasing sample sizes to see how quickly the statistical signal converges — i.e. the minimum number of requests needed for a confident verdict.</p>
    <img class="exp-chart" src="data:image/png;base64,{sample_size_img}" alt="Sample-size study chart" tabindex="0" role="button" aria-label="Enlarge sample-size study chart">
  </section>

  <footer class="footer">
    Generated by TimeLeak &middot; {generated_at} &middot; for authorized self-assessment only
  </footer>
</div>

<div class="lightbox" id="lightbox" role="dialog" aria-hidden="true" aria-label="Enlarged chart">
  <img class="lightbox-img" id="lightbox-img" src="" alt="">
</div>

{chatbot_snippet}

<script>
{_JS}
{chatbot.JS}
</script>
</body>
</html>
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_doc)

    return filepath


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
  --warning: #fbbf24;
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
    --warning: #d97706;
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
  --warning: #d97706;
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
  --warning: #fbbf24;
  --accent: #8b5cf6;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: radial-gradient(120% 140% at 20% -10%, #3b0764 0%, var(--page-plane) 55%);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) body { background: radial-gradient(120% 140% at 20% -10%, #ede9fe 0%, var(--page-plane) 55%); }
}
:root[data-theme="light"] body { background: radial-gradient(120% 140% at 20% -10%, #ede9fe 0%, var(--page-plane) 55%); }
:root[data-theme="dark"] body { background: radial-gradient(120% 140% at 20% -10%, #3b0764 0%, var(--page-plane) 55%); }
.scroll-progress { position: fixed; top: 0; left: 0; height: 2.5px; width: 0%; background: linear-gradient(90deg, var(--accent), var(--critical)); z-index: 30; transition: width 0.08s linear; }
.topbar {
  position: sticky; top: 0; z-index: 20;
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  background: color-mix(in srgb, var(--page-plane) 72%, transparent);
  border-bottom: 1px solid var(--border);
}
.topbar-inner { max-width: 1080px; margin: 0 auto; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; }
.topbar-right { display: flex; align-items: center; gap: 12px; }
.wordmark { display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 700; letter-spacing: -0.01em; }
.wordmark-mark { width: 12px; height: 12px; border-radius: 4px; background: linear-gradient(135deg, var(--accent), var(--critical)); }
.topbar-label { font-size: 12.5px; color: var(--text-secondary); }
.theme-toggle {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: 999px;
  border: 1px solid var(--border); background: rgba(127,127,127,0.08);
  color: var(--text-secondary); cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}
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
.page { max-width: 1080px; margin: 0 auto; padding: 48px 24px 64px; }
/* Visible by default -- JS opts elements into the hidden-then-reveal
   animation via the .js class on <html>. If JS is blocked or fails, every
   .reveal element simply stays visible; the animation never gates content. */
.reveal { transition: opacity 0.6s cubic-bezier(.2,.7,.2,1), transform 0.6s cubic-bezier(.2,.7,.2,1); }
html.js .reveal { opacity: 0; transform: translateY(16px); }
html.js .reveal.in-view { opacity: 1; transform: translateY(0); }
.hero { position: relative; margin-bottom: 28px; padding: 4px 0; --spot-x: 50%; --spot-y: 0%; }
.hero::before {
  content: ""; position: absolute; inset: -20px; z-index: -1; pointer-events: none;
  background: radial-gradient(360px circle at var(--spot-x) var(--spot-y), color-mix(in srgb, var(--accent) 8%, transparent), transparent 70%);
  opacity: 0; transition: opacity 0.3s ease;
}
.hero:hover::before { opacity: 1; }
.hero h1 { font-size: clamp(30px, 4vw, 44px); letter-spacing: -0.02em; margin: 0 0 12px; }
.hero-sub { color: var(--text-secondary); font-size: 14.5px; max-width: 70ch; line-height: 1.6; margin: 0; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.92em;
  background: rgba(127,127,127,0.14); padding: 1px 6px; border-radius: 5px;
}
.card {
  background: var(--surface-1); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border); border-radius: 20px; padding: 28px 32px; margin-bottom: 20px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset;
  transition: transform 0.2s ease, box-shadow 0.25s ease, border-color 0.25s ease;
  transform-style: preserve-3d;
}
.card:hover { box-shadow: 0 20px 40px -20px rgba(0,0,0,0.5); }
.headline-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-bottom: 8px; }
@media (max-width: 800px) { .headline-grid { grid-template-columns: 1fr; } }
.headline-card { display: flex; flex-direction: column; gap: 6px; border-top: 3px solid transparent; }
.headline-good { border-top-color: var(--good); }
.headline-critical { border-top-color: var(--critical); }
.headline-accent { border-top-color: var(--accent); }
.headline-label { font-size: 11.5px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); }
.headline-value { font-size: 30px; font-weight: 700; letter-spacing: -0.02em; }
.headline-sub { font-size: 12.5px; color: var(--text-secondary); }
.exp-card h2 { font-size: 17px; font-weight: 600; margin: 0 0 10px; }
.exp-copy { color: var(--text-secondary); font-size: 13.5px; line-height: 1.6; max-width: 80ch; margin: 0 0 18px; }
.exp-chart {
  width: 100%; height: auto; border-radius: 14px; border: 1px solid var(--border); display: block;
  cursor: zoom-in; transition: border-color 0.15s ease, transform 0.15s ease;
}
.exp-chart:hover { border-color: color-mix(in srgb, var(--accent) 40%, var(--border)); transform: scale(1.01); }
.footer { text-align: center; color: var(--text-muted); font-size: 12.5px; margin-top: 24px; }

.lightbox {
  position: fixed; inset: 0; z-index: 55; display: flex; align-items: center; justify-content: center;
  padding: 40px; background: color-mix(in srgb, var(--page-plane) 85%, transparent);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  opacity: 0; pointer-events: none; transition: opacity 0.2s ease;
}
.lightbox.is-open { opacity: 1; pointer-events: auto; }
.lightbox-img {
  max-width: 100%; max-height: 100%; border-radius: 14px; border: 1px solid var(--border);
  box-shadow: 0 30px 80px rgba(0,0,0,0.5);
  transform: scale(0.96); transition: transform 0.2s cubic-bezier(.2,.8,.2,1);
}
.lightbox.is-open .lightbox-img { transform: scale(1); }
"""

_JS = """
document.documentElement.classList.add('js');
(function() {
  var revealEls = document.querySelectorAll('.reveal');
  revealEls.forEach(function(el, i) { el.style.transitionDelay = (i * 60) + 'ms'; });
  var io = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) { entry.target.classList.add('in-view'); io.unobserve(entry.target); }
    });
  }, { threshold: 0.1 });
  revealEls.forEach(function(el) { io.observe(el); });

  var progressBar = document.getElementById('scroll-progress');
  function updateProgress() {
    var doc = document.documentElement;
    var scrollable = doc.scrollHeight - doc.clientHeight;
    var pct = scrollable > 0 ? (doc.scrollTop / scrollable) * 100 : 0;
    if (progressBar) progressBar.style.width = pct + '%';
  }
  document.addEventListener('scroll', updateProgress, { passive: true });
  updateProgress();

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

  var hero = document.getElementById('hero');
  if (hero) {
    hero.addEventListener('pointermove', function(e) {
      var rect = hero.getBoundingClientRect();
      hero.style.setProperty('--spot-x', (e.clientX - rect.left) + 'px');
      hero.style.setProperty('--spot-y', (e.clientY - rect.top) + 'px');
    });
  }

  document.querySelectorAll('.card').forEach(function(card) {
    card.addEventListener('pointermove', function(e) {
      var rect = card.getBoundingClientRect();
      var px = (e.clientX - rect.left) / rect.width - 0.5;
      var py = (e.clientY - rect.top) / rect.height - 0.5;
      var rx = (-py * 2.5).toFixed(2);
      var ry = (px * 2.5).toFixed(2);
      card.style.transform = 'perspective(900px) rotateX(' + rx + 'deg) rotateY(' + ry + 'deg) translateY(-3px)';
    });
    card.addEventListener('pointerleave', function() { card.style.transform = ''; });
  });

  var lightbox = document.getElementById('lightbox');
  var lightboxImg = document.getElementById('lightbox-img');
  function openLightbox(src, alt) {
    if (!lightbox || !lightboxImg) return;
    lightboxImg.src = src;
    lightboxImg.alt = alt || '';
    lightbox.classList.add('is-open');
    lightbox.setAttribute('aria-hidden', 'false');
  }
  function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.remove('is-open');
    lightbox.setAttribute('aria-hidden', 'true');
  }
  document.querySelectorAll('.exp-chart').forEach(function(img) {
    img.addEventListener('click', function() { openLightbox(img.src, img.alt); });
    img.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openLightbox(img.src, img.alt); }
    });
  });
  if (lightbox) {
    lightbox.addEventListener('click', closeLightbox);
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') closeLightbox();
    });
  }
})();
"""

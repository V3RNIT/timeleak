"""
TimeLeak HTML report generator.

Renders a self-contained (no external CDN/network dependency) HTML report
from a harness sample set + analysis.analyze() result: overlaid response-
time and response-size histograms behind a segmented tab switch, a
confidence-ring + effect-size-meter widget set, a stats table, and a clear
leak/no-leak verdict banner.
"""
import html
import json
import os
from datetime import datetime, timezone

import numpy as np

import chatbot

# --- design tokens (validated categorical + status palette; see detector's
# dataviz reference) -- violet/magenta jewel-tone theme, CVD-checked via
# the dataviz skill's validate_palette.js (ALL CHECKS PASS at ΔE 15.4/22.6
# for the valid/invalid pair against the #150f28 dark surface) -----------
COLOR_VALID = "#8b5cf6"     # categorical slot 1 (violet) -- dark-mode step
COLOR_INVALID = "#ec4899"   # categorical slot 2 (magenta) -- dark-mode step
COLOR_GOOD = "#10b981"      # status: good (no leak) -- emerald
COLOR_CRITICAL = "#f43f5e"  # status: critical (leak) -- dark-mode step, rose
COLOR_WARNING = "#fbbf24"   # status: warning (meter mid-zone) -- amber

N_BINS = 20


def _info_btn(tip):
    return f'<button type="button" class="info-btn" data-tip="{html.escape(tip)}" aria-label="What is this?">i</button>'


_INFO_WELCH = _info_btn(
    "Compares the average of both groups without assuming they have equal "
    "variance. Sensitive to outliers, which is why it's paired with Mann-Whitney below."
)
_INFO_MANNWHITNEY = _info_btn(
    "A non-parametric test that compares the full distributions rather than "
    "just the mean — more robust for timing data, which is rarely perfectly normal."
)
_INFO_COHENS_D = _info_btn(
    "Effect size: how large the difference is in practice, not just whether it's "
    "statistically detectable. Below 0.2 is treated as negligible even if p is tiny."
)


def _fmt_p(p):
    if p < 0.0001:
        return f"&lt; 0.0001 ({p:.2e})"
    return f"{p:.4f}"


def _fmt_ms(x):
    return f"{x:.3f} ms"


def _fmt_bytes(x):
    return f"{x:.1f} B"


def _fmt_time(iso_ts):
    try:
        dt = datetime.fromisoformat(iso_ts)
        return dt.strftime("%H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
    except (ValueError, TypeError):
        return str(iso_ts)


def _build_sequence_data(valid_records, invalid_records):
    """Reconstruct the true interleaved send order (valid, invalid, valid,
    invalid, ...) from the two split lists, for the replay widget and raw
    samples table."""
    ordered = []
    for v, i in zip(valid_records, invalid_records):
        ordered.append(v)
        ordered.append(i)
    return [
        {
            "i": idx + 1,
            "type": r["payload_type"],
            "ms": round(r["elapsed_ms"], 3),
            "bytes": r["response_bytes"],
            "status": r["status_code"],
            "time": _fmt_time(r.get("timestamp", "")),
        }
        for idx, r in enumerate(ordered)
    ]


def _histogram_bins(a, b, n_bins=N_BINS):
    combined = np.asarray(list(a) + list(b), dtype=float)
    lo, hi = float(np.min(combined)), float(np.max(combined))
    if lo == hi:
        lo -= 0.5
        hi += 0.5
    edges = np.linspace(lo, hi, n_bins + 1)
    counts_a, _ = np.histogram(a, bins=edges)
    counts_b, _ = np.histogram(b, bins=edges)
    return edges, counts_a, counts_b


def _render_histogram_svg(valid_vals, invalid_vals, axis_title, unit_suffix, decimals=1,
                           width=800, height=320, active=False):
    edges, counts_valid, counts_invalid = _histogram_bins(valid_vals, invalid_vals)
    n_bins = len(counts_valid)
    max_count = max(1, int(np.max(counts_valid)), int(np.max(counts_invalid)))

    margin_left, margin_right, margin_top, margin_bottom = 56, 16, 16, 40
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    baseline_y = margin_top + plot_h

    bin_w = plot_w / n_bins
    gap = 2
    bar_w = max(2.0, (bin_w - gap * 3) / 2)

    def bar_height(count):
        return (count / max_count) * plot_h if max_count else 0

    bars_svg = []
    for i in range(n_bins):
        bx = margin_left + i * bin_w
        vh = bar_height(counts_valid[i])
        ih = bar_height(counts_invalid[i])
        vx = bx + gap
        ix = vx + bar_w + gap
        lo_edge, hi_edge = edges[i], edges[i + 1]
        title_common = f"{lo_edge:.{decimals}f}–{hi_edge:.{decimals}f}{unit_suffix}"

        if vh > 0:
            bars_svg.append(
                f'<rect class="bar bar-valid" data-count="{counts_valid[i]}" '
                f'data-range="{html.escape(title_common)}" style="--i:{i}" '
                f'x="{vx:.2f}" y="{baseline_y - vh:.2f}" width="{bar_w:.2f}" height="{vh:.2f}" rx="3">'
                f'<title>Valid · {title_common} · {counts_valid[i]} requests</title></rect>'
            )
        if ih > 0:
            bars_svg.append(
                f'<rect class="bar bar-invalid" data-count="{counts_invalid[i]}" '
                f'data-range="{html.escape(title_common)}" style="--i:{i}" '
                f'x="{ix:.2f}" y="{baseline_y - ih:.2f}" width="{bar_w:.2f}" height="{ih:.2f}" rx="3">'
                f'<title>Invalid · {title_common} · {counts_invalid[i]} requests</title></rect>'
            )

    y_ticks = sorted(set([0, max_count // 2, max_count]))
    grid_svg = []
    for t in y_ticks:
        y = baseline_y - bar_height(t)
        grid_svg.append(
            f'<line x1="{margin_left}" y1="{y:.2f}" x2="{width - margin_right}" y2="{y:.2f}" class="gridline"/>'
            f'<text x="{margin_left - 10}" y="{y + 4:.2f}" class="axis-label" text-anchor="end">{t}</text>'
        )

    x_tick_indices = sorted(set([0, n_bins // 2, n_bins]))
    x_ticks_svg = []
    for idx in x_tick_indices:
        x = margin_left + idx * bin_w
        x_ticks_svg.append(
            f'<text x="{x:.2f}" y="{baseline_y + 20}" class="axis-label" text-anchor="middle">{edges[idx]:.{decimals}f}</text>'
        )

    active_class = " is-active" if active else ""
    svg = f'''
<svg class="hist-svg{active_class}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Overlaid histogram of {html.escape(axis_title)} for valid vs invalid usernames">
  <line x1="{margin_left}" y1="{baseline_y}" x2="{width - margin_right}" y2="{baseline_y}" class="axis-baseline"/>
  {''.join(grid_svg)}
  {''.join(bars_svg)}
  {''.join(x_ticks_svg)}
  <text x="{margin_left + plot_w / 2:.2f}" y="{height - 4}" class="axis-title" text-anchor="middle">{html.escape(axis_title)}</text>
</svg>
'''
    return svg


def _verdict_copy(verdict):
    if verdict["leak_detected"]:
        headline = "LEAK DETECTED"
        status_class = "critical"
        icon = (
            '<path d="M12 2 1 21h22L12 2Zm0 6v6m0 3.5h.01" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        )
    else:
        headline = "NO SIGNIFICANT LEAK"
        status_class = "good"
        icon = (
            '<path d="m4 12 6 6L20 6" stroke="currentColor" stroke-width="2.5" '
            'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        )

    conf = verdict["confidence_level"]
    if verdict["leak_detected"]:
        if conf == "high":
            sentence = (
                "This endpoint reveals, with high statistical confidence, whether a "
                "submitted username exists in the system — an attacker could use this "
                "to enumerate valid accounts."
            )
        else:
            sentence = (
                "This endpoint shows a statistically significant difference between "
                "valid and invalid usernames, though the effect is moderate. Treat this "
                "as a real but less severe leak."
            )
    elif "negligible" in conf:
        sentence = (
            "A difference was detected but its effect size is negligible — "
            "unlikely to be practically exploitable, but worth a second look with more samples."
        )
    else:
        sentence = (
            "No statistically significant difference was found between valid and "
            "invalid usernames in timing or response size at this sample size."
        )

    return headline, status_class, icon, sentence


def _confidence_ring_svg(pct, status_class, size=136, stroke=10):
    r = (size - stroke) / 2
    circumference = 2 * np.pi * r
    center = size / 2
    return f'''
<svg class="ring-svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="Statistical confidence: {pct:.1f} percent">
  <circle class="ring-track" cx="{center}" cy="{center}" r="{r}" stroke-width="{stroke}" fill="none"/>
  <circle class="ring-fill ring-fill-{status_class}" cx="{center}" cy="{center}" r="{r}" stroke-width="{stroke}" fill="none"
          stroke-linecap="round" transform="rotate(-90 {center} {center})"
          style="--circumference:{circumference:.2f}" data-target="{pct:.1f}"/>
</svg>
'''


def _effect_meter_html(d_value, label):
    ad = min(abs(d_value), 1.4)
    pct = min(100, (ad / 1.2) * 100)
    if abs(d_value) < 0.2:
        fill_color = "var(--accent)"
    elif abs(d_value) < 0.8:
        fill_color = COLOR_WARNING
    else:
        fill_color = "var(--critical)"
    return f'''
<div class="meter">
  <div class="meter-track">
    <div class="meter-zone" style="left:0%; width:16.66%"></div>
    <div class="meter-zone" style="left:16.66%; width:25%"></div>
    <div class="meter-zone" style="left:41.66%; width:25%"></div>
    <div class="meter-zone" style="left:66.66%; width:33.34%"></div>
    <div class="meter-fill" style="width:0%; background:{fill_color}" data-target="{pct:.1f}"></div>
  </div>
  <div class="meter-ticks">
    <span style="left:16.66%">0.2</span>
    <span style="left:41.66%">0.5</span>
    <span style="left:66.66%">0.8</span>
  </div>
  <div class="meter-caption"><strong>d = {d_value:.3f}</strong> &middot; {html.escape(label)} effect{_INFO_COHENS_D}</div>
</div>
'''


def _build_sequence_csv(sequence_data):
    lines = ["index,payload_type,elapsed_ms,response_bytes,status_code,time"]
    for r in sequence_data:
        lines.append(f'{r["i"]},{r["type"]},{r["ms"]},{r["bytes"]},{r["status"]},{r["time"]}')
    return "\n".join(lines)


def _p_chip_html(p_value, significant):
    cls = "chip-critical" if significant else "chip-good"
    text = _fmt_p(p_value)
    return f'<span class="chip {cls}">p = {text}</span>'


def generate_report(
    target_url,
    endpoint_label,
    valid_payload,
    invalid_payload,
    analysis_result,
    valid_records,
    invalid_records,
    warmup_count,
    output_dir=None,
):
    """
    Build the self-contained HTML report and write it to
    detector/reports/report_<timestamp>.html. Returns the file path.

    valid_records / invalid_records are the same per-request dict lists
    passed into analysis.analyze() (used here to draw the histograms).
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(output_dir, exist_ok=True)

    timing = analysis_result["timing"]
    size = analysis_result["size"]
    verdict = analysis_result["verdict"]

    valid_times = [r["elapsed_ms"] for r in valid_records]
    invalid_times = [r["elapsed_ms"] for r in invalid_records]
    valid_sizes = [r["response_bytes"] for r in valid_records]
    invalid_sizes = [r["response_bytes"] for r in invalid_records]

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    filename = f"report_{now.strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(output_dir, filename)

    headline, status_class, icon_svg, sentence = _verdict_copy(verdict)

    timing_svg = _render_histogram_svg(
        valid_times, invalid_times, "Response time (ms)", " ms", decimals=1, active=True
    ) if valid_times and invalid_times else ""
    size_svg = _render_histogram_svg(
        valid_sizes, invalid_sizes, "Response size (bytes)", " B", decimals=0, active=False
    ) if valid_sizes and invalid_sizes else ""

    n_per_group = timing["valid"]["n"]
    total_requests = n_per_group + timing["invalid"]["n"]

    primary_p = min(verdict["timing_p_value"], verdict["size_p_value"])
    confidence_pct = max(0.0, min(99.9, (1 - primary_p) * 100))
    ring_svg = _confidence_ring_svg(confidence_pct, status_class)

    timing_meter = _effect_meter_html(verdict["timing_effect_size"], verdict["timing_effect_label"])
    timing_p_chip = _p_chip_html(verdict["timing_p_value"], verdict["timing_leak_detected"])
    size_p_chip = _p_chip_html(verdict["size_p_value"], verdict["size_leak_detected"])

    sequence_data = _build_sequence_data(valid_records, invalid_records)
    sequence_json = json.dumps(sequence_data).replace("</", "<\\/")
    sequence_csv = _build_sequence_csv(sequence_data)

    timing_gap_ms = abs(timing["valid"]["mean"] - timing["invalid"]["mean"])
    try:
        span_s = max(
            0.001,
            (datetime.fromisoformat(valid_records[-1]["timestamp"]) - datetime.fromisoformat(valid_records[0]["timestamp"])).total_seconds(),
        )
        throughput = total_requests / span_s if span_s > 0 else 0.0
    except (ValueError, IndexError):
        throughput = 0.0

    max_lane_mean = max(timing["valid"]["mean"], timing["invalid"]["mean"], 1.0)
    valid_race_s = round(0.4 + (timing["valid"]["mean"] / max_lane_mean) * 1.6, 2)
    invalid_race_s = round(0.4 + (timing["invalid"]["mean"] / max_lane_mean) * 1.6, 2)

    if verdict["leak_detected"]:
        scenario_note = ""
    else:
        scenario_note = (
            '<p class="scenario-hypothetical">This endpoint did not show a significant leak, so this walkthrough '
            "is illustrative only — it describes what would be possible against an unpatched endpoint like "
            "<code>/login/v1</code> or <code>/login/v2</code> in this project.</p>"
        )

    safe_url = html.escape(str(target_url))
    safe_endpoint = html.escape(str(endpoint_label))
    safe_valid_payload = html.escape(str(valid_payload))
    safe_invalid_payload = html.escape(str(invalid_payload))

    curl_valid = (
        f"curl -s -X POST '{target_url}' -H 'Content-Type: application/json' "
        f"-d '{json.dumps(valid_payload)}'"
    )
    curl_invalid = (
        f"curl -s -X POST '{target_url}' -H 'Content-Type: application/json' "
        f"-d '{json.dumps(invalid_payload)}'"
    )
    safe_curl_valid = html.escape(curl_valid)
    safe_curl_invalid = html.escape(curl_invalid)

    verdict_word = "leaks" if verdict["leak_detected"] else "does not leak"
    chatbot_snippet = chatbot.render_chatbot(
        page_entries=[{
            "keywords": ["this report", "this page", "this endpoint", "this scan", "verdict", "what does this show", "result"],
            "answer": (
                f"This report scanned {endpoint_label} and found it {verdict_word} information about "
                f"which usernames exist. Confidence: {verdict['confidence_level']}. Timing p-value: "
                f"{_fmt_p(verdict['timing_p_value']).replace('&lt;', '<')}, Cohen's d: {verdict['timing_effect_size']:.2f} "
                f"({verdict['timing_effect_label']}). Size delta: {verdict['size_delta_bytes']:.1f} bytes."
            ),
        }],
        suggestions=["What does this report show?", "What is CWE-203?", "Explain Cohen's d"],
    )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="timeleak:kind" content="scan-report">
<meta name="timeleak:verdict" content="{'leak' if verdict['leak_detected'] else 'no-leak'}">
<meta name="timeleak:endpoint" content="{safe_endpoint}">
<meta name="timeleak:target" content="{safe_url}">
<meta name="timeleak:confidence" content="{html.escape(verdict['confidence_level'])}">
<meta name="timeleak:generated" content="{now.isoformat()}">
<title>TimeLeak Report — {safe_endpoint}</title>
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
      <div class="topbar-pill topbar-pill-{status_class}">
        <span class="topbar-dot"></span>{headline}
      </div>
      <button class="theme-toggle" id="theme-toggle" type="button" aria-label="Toggle light and dark theme">
        <svg class="icon-sun" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></g></svg>
        <svg class="icon-moon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" fill="currentColor"/></svg>
      </button>
    </div>
  </div>
</div>

<div class="page">
  <header class="hero reveal">
    <div class="hero-meta">
      <div class="hero-meta-row"><span class="muted">Target</span><code>{safe_url}</code></div>
      <div class="hero-meta-row"><span class="muted">Generated</span><span>{generated_at}</span></div>
    </div>
    <div class="stat-strip">
      <div class="stat-tile">
        <span class="stat-tile-value count-up" data-target="{total_requests}" data-suffix="">0</span>
        <span class="stat-tile-label">requests sent</span>
      </div>
      <div class="stat-tile">
        <span class="stat-tile-value count-up" data-target="{throughput:.1f}" data-suffix="/s">0/s</span>
        <span class="stat-tile-label">throughput</span>
      </div>
      <div class="stat-tile">
        <span class="stat-tile-value count-up" data-target="{timing_gap_ms:.1f}" data-suffix=" ms">0 ms</span>
        <span class="stat-tile-label">mean timing gap</span>
      </div>
      <div class="stat-tile">
        <span class="stat-tile-value count-up" data-target="{verdict['size_delta_bytes']:.0f}" data-suffix=" B">0 B</span>
        <span class="stat-tile-label">mean size delta</span>
      </div>
    </div>
  </header>

  <section class="card verdict verdict-{status_class} reveal" id="verdict" aria-live="polite">
    <div class="verdict-left">
      <div class="verdict-icon">
        <svg viewBox="0 0 24 24" width="36" height="36" aria-hidden="true">{icon_svg}</svg>
      </div>
      <div class="verdict-body">
        <div class="verdict-badge">{status_class.upper()}</div>
        <h1>{headline}</h1>
        <p class="verdict-sentence">{sentence}</p>
        <p class="verdict-confidence">Confidence level: <strong>{html.escape(verdict['confidence_level'])}</strong></p>
      </div>
    </div>
    <div class="verdict-ring">
      {ring_svg}
      <div class="ring-label">
        <span class="ring-value count-up" data-target="{confidence_pct:.1f}" data-suffix="%">0%</span>
        <span class="ring-caption">statistical<br>confidence</span>
      </div>
    </div>
  </section>

  <section class="how-it-works card reveal" id="how-it-works">
    <div class="chart-header">
      <h2>The timing race</h2>
      <button class="replay-btn" id="race-btn" type="button">
        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M6 4.5v15l13-7.5-13-7.5Z" fill="currentColor"/></svg>
        Run the race
      </button>
    </div>
    <p class="how-it-works-copy">Both usernames are sent to the same endpoint. Watch how long the server takes to respond to each — the gap between them is the leak.</p>
    <div class="race-lane" data-duration="{valid_race_s}">
      <div class="race-lane-label"><span class="legend-swatch" style="background:{COLOR_VALID}"></span>Valid username</div>
      <div class="race-track">
        <div class="race-node race-client">Client</div>
        <div class="race-path"><div class="race-dot race-dot-valid"></div></div>
        <div class="race-node race-server">Server</div>
      </div>
      <div class="race-time" id="race-time-valid">{_fmt_ms(timing['valid']['mean'])}</div>
    </div>
    <div class="race-lane" data-duration="{invalid_race_s}">
      <div class="race-lane-label"><span class="legend-swatch" style="background:{COLOR_INVALID}"></span>Invalid username</div>
      <div class="race-track">
        <div class="race-node race-client">Client</div>
        <div class="race-path"><div class="race-dot race-dot-invalid"></div></div>
        <div class="race-node race-server">Server</div>
      </div>
      <div class="race-time" id="race-time-invalid">{_fmt_ms(timing['invalid']['mean'])}</div>
    </div>
  </section>

  <section class="grid-2" id="stats">
    <div class="card stat-card reveal">
      <div class="stat-card-head">
        <h2>Response timing</h2>
        {timing_p_chip}
      </div>
      <table class="stats-table">
        <thead><tr><th></th><th>Valid</th><th>Invalid</th></tr></thead>
        <tbody>
          <tr><th>Mean</th><td>{_fmt_ms(timing['valid']['mean'])}</td><td>{_fmt_ms(timing['invalid']['mean'])}</td></tr>
          <tr><th>Median</th><td>{_fmt_ms(timing['valid']['median'])}</td><td>{_fmt_ms(timing['invalid']['median'])}</td></tr>
          <tr><th>Std dev</th><td>{_fmt_ms(timing['valid']['std'])}</td><td>{_fmt_ms(timing['invalid']['std'])}</td></tr>
          <tr><th>N</th><td>{timing['valid']['n']}</td><td>{timing['invalid']['n']}</td></tr>
        </tbody>
      </table>
      <div class="test-results">
        <div class="test-row"><span>Welch's t-test{_INFO_WELCH}</span><strong>p = {_fmt_p(verdict['timing_welch_p_value'])}</strong></div>
        <div class="test-row"><span>Mann-Whitney U{_INFO_MANNWHITNEY}</span><strong>p = {_fmt_p(verdict['timing_p_value'])}</strong></div>
      </div>
      {timing_meter}
    </div>

    <div class="card stat-card reveal">
      <div class="stat-card-head">
        <h2>Response size</h2>
        {size_p_chip}
      </div>
      <table class="stats-table">
        <thead><tr><th></th><th>Valid</th><th>Invalid</th></tr></thead>
        <tbody>
          <tr><th>Mean</th><td>{_fmt_bytes(size['valid']['mean'])}</td><td>{_fmt_bytes(size['invalid']['mean'])}</td></tr>
          <tr><th>Median</th><td>{_fmt_bytes(size['valid']['median'])}</td><td>{_fmt_bytes(size['invalid']['median'])}</td></tr>
          <tr><th>Std dev</th><td>{_fmt_bytes(size['valid']['std'])}</td><td>{_fmt_bytes(size['invalid']['std'])}</td></tr>
          <tr><th>N</th><td>{size['valid']['n']}</td><td>{size['invalid']['n']}</td></tr>
        </tbody>
      </table>
      <div class="test-results">
        <div class="test-row"><span>Mann-Whitney U{_INFO_MANNWHITNEY}</span><strong>p = {_fmt_p(verdict['size_p_value'])}</strong></div>
        <div class="test-row"><span>Mean size delta</span><strong class="count-up" data-target="{verdict['size_delta_bytes']:.1f}" data-suffix=" bytes">0 bytes</strong></div>
      </div>
    </div>
  </section>

  <section class="card chart-card reveal" id="distribution">
    <div class="chart-header">
      <div class="tabs" role="tablist">
        <button class="tab is-active" data-target="chart-timing" role="tab" aria-selected="true">Timing</button>
        <button class="tab" data-target="chart-size" role="tab" aria-selected="false">Response size</button>
      </div>
      <div class="legend">
        <span class="legend-item"><span class="legend-swatch" style="background:{COLOR_VALID}"></span>Valid username</span>
        <span class="legend-item"><span class="legend-swatch" style="background:{COLOR_INVALID}"></span>Invalid username</span>
      </div>
    </div>
    <div class="chart-wrap" id="chart-wrap">
      <div class="chart-pane is-active" id="chart-timing">{timing_svg}</div>
      <div class="chart-pane" id="chart-size">{size_svg}</div>
      <div class="tooltip" id="tooltip" role="tooltip"></div>
    </div>
  </section>

  <section class="card sequence-card reveal" id="sequence">
    <div class="chart-header">
      <h2>Request sequence</h2>
      <button class="replay-btn" id="replay-btn" type="button">
        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M6 4.5v15l13-7.5-13-7.5Z" fill="currentColor"/></svg>
        Replay scan
      </button>
    </div>
    <div class="sequence-strip-wrap">
      <div class="sequence-strip" id="sequence-strip"></div>
      <div class="sequence-playhead" id="sequence-playhead"></div>
    </div>
    <div class="sequence-status" id="sequence-status">Click "Replay scan" to step through the {total_requests} requests in the exact order they were sent.</div>
  </section>

  <section class="card samples-card reveal" id="samples">
    <div class="chart-header">
      <h2>Raw samples</h2>
      <div class="samples-toolbar">
        <button class="export-btn" id="export-json-btn" type="button">
          Download JSON <svg viewBox="0 0 24 24" width="11" height="11" aria-hidden="true"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button class="export-btn" id="export-csv-btn" type="button">
          Download CSV <svg viewBox="0 0 24 24" width="11" height="11" aria-hidden="true"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button class="samples-toggle" id="samples-toggle" type="button" aria-expanded="false">
          Show {total_requests} raw samples
          <svg class="chevron" viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="m6 9 6 6 6-6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
    </div>
    <div class="samples-body" id="samples-body">
      <div class="samples-table-wrap">
        <table class="samples-table" id="samples-table">
          <thead>
            <tr>
              <th data-key="i" data-type="num">#</th>
              <th data-key="type" data-type="str">Type</th>
              <th data-key="ms" data-type="num">Elapsed</th>
              <th data-key="bytes" data-type="num">Size</th>
              <th data-key="status" data-type="num">Status</th>
              <th data-key="time" data-type="str">Time</th>
            </tr>
          </thead>
          <tbody id="samples-tbody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="card scenario-card reveal" id="scenario">
    <h2>Attack scenario{'' if verdict['leak_detected'] else ' (hypothetical)'}</h2>
    {scenario_note}
    <div class="scenario-steps">
      <div class="scenario-step">
        <div class="scenario-num">1</div>
        <div><h3>Recon</h3><p>The attacker sends a list of candidate usernames to this endpoint and records the response time and size for each.</p></div>
      </div>
      <div class="scenario-step">
        <div class="scenario-num">2</div>
        <div><h3>Detection</h3><p>Requests that take {_fmt_ms(timing['valid']['mean'])} on average are flagged as existing accounts; the rest, around {_fmt_ms(timing['invalid']['mean'])}, are discarded as invalid — no password guessing required.</p></div>
      </div>
      <div class="scenario-step">
        <div><div class="scenario-num">3</div></div>
        <div><h3>Impact</h3><p>The attacker now holds a list of confirmed valid usernames, ready for targeted credential stuffing, password spraying, or phishing.</p></div>
      </div>
    </div>
  </section>

  <section class="card remediation-card reveal" id="remediation">
    <h2>Remediation</h2>
    <ul class="remediation-list">
      <li><span class="check-icon">✓</span> Perform a dummy password-hash comparison on the "user not found" path so both outcomes cost the same time (see <code>/login/v3</code> in the demo app).</li>
      <li><span class="check-icon">✓</span> Return byte-for-byte identical JSON structure and status code for every authentication failure, regardless of the reason.</li>
      <li><span class="check-icon">✓</span> Use a single generic error message ("Invalid username or password") for both cases, in login and signup flows alike.</li>
      <li><span class="check-icon">✓</span> Rate-limit and monitor authentication endpoints as defense-in-depth — this does not fix the leak, but slows down large-scale enumeration.</li>
    </ul>
    <div class="reference-links">
      <a href="https://cwe.mitre.org/data/definitions/203.html" target="_blank" rel="noopener noreferrer">CWE-203: Observable Discrepancy ↗</a>
      <a href="https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html" target="_blank" rel="noopener noreferrer">OWASP Authentication Cheat Sheet ↗</a>
    </div>
  </section>

  <section class="card methodology reveal" id="methodology">
    <div class="stat-card-head">
      <h2>Methodology</h2>
      <button class="copy-btn" id="copy-btn" type="button" data-copy-valid="{safe_curl_valid}" data-copy-invalid="{safe_curl_invalid}">
        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M4 16V5a1 1 0 0 1 1-1h11" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg>
        <span class="copy-btn-label">Copy repro commands</span>
      </button>
    </div>
    <ul>
      <li>Endpoint under test: <code>{safe_endpoint}</code></li>
      <li>Sampling: interleaved (valid, invalid, valid, invalid, …) to cancel network jitter and warm-up drift</li>
      <li>Samples per group: <strong>{n_per_group}</strong> (<strong>{total_requests}</strong> total requests)</li>
      <li>Warmup requests discarded before sampling: <strong>{warmup_count}</strong></li>
      <li>Valid payload: <code>{safe_valid_payload}</code></li>
      <li>Invalid payload: <code>{safe_invalid_payload}</code></li>
      <li>Timing measured with <code>time.perf_counter()</code> (monotonic wall-clock)</li>
      <li>Significance threshold: α = 0.05, both Welch's t-test and Mann-Whitney U required to agree</li>
      <li>Effect size below Cohen's d = 0.2 is treated as practically negligible even if statistically significant</li>
    </ul>
  </section>

  <script type="application/json" id="sequence-data">{sequence_json}</script>
  <script type="text/plain" id="sequence-csv">{html.escape(sequence_csv)}</script>

  <footer class="footer">
    <div class="footer-links">
      <a href="https://cwe.mitre.org/data/definitions/203.html" target="_blank" rel="noopener noreferrer">CWE-203 ↗</a>
      <a href="https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html" target="_blank" rel="noopener noreferrer">OWASP Auth Cheat Sheet ↗</a>
    </div>
    Generated by TimeLeak &middot; {generated_at} &middot; for authorized self-assessment only
  </footer>
</div>

<nav class="dot-nav" id="dot-nav" aria-label="Section navigation"></nav>

<div class="info-popover" id="info-popover" role="tooltip"></div>
<div class="toast" id="toast"></div>

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

.scroll-progress {
  position: fixed; top: 0; left: 0; height: 2.5px; width: 0%;
  background: linear-gradient(90deg, var(--accent), var(--critical));
  z-index: 30; transition: width 0.08s linear;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  background: color-mix(in srgb, var(--page-plane) 72%, transparent);
  border-bottom: 1px solid var(--border);
}
.topbar-inner {
  max-width: 1240px;
  margin: 0 auto;
  padding: 14px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.topbar-right { display: flex; align-items: center; gap: 10px; }
.topbar-pill {
  display: flex; align-items: center; gap: 7px;
  font-size: 12px; font-weight: 700; letter-spacing: 0.03em;
  padding: 6px 12px; border-radius: 999px;
}
.topbar-pill-critical { color: var(--critical); background: color-mix(in srgb, var(--critical) 14%, transparent); }
.topbar-pill-good { color: var(--good); background: color-mix(in srgb, var(--good) 14%, transparent); }
.topbar-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 25%, transparent); }

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

.page {
  max-width: 1240px;
  margin: 0 auto;
  padding: 48px 32px 80px;
}
.section-gap { margin-bottom: 28px; }

/* Visible by default -- JS opts elements into the hidden-then-reveal
   animation via the .js class on <html>. If JS is blocked or fails, every
   .reveal element simply stays visible; the animation never gates content. */
.reveal {
  transition: opacity 0.6s cubic-bezier(.2,.7,.2,1), transform 0.6s cubic-bezier(.2,.7,.2,1);
}
html.js .reveal { opacity: 0; transform: translateY(16px); }
html.js .reveal.in-view { opacity: 1; transform: translateY(0); }

.hero { margin-bottom: 20px; }
.hero-meta { font-size: 13px; color: var(--text-secondary); display: flex; gap: 24px; flex-wrap: wrap; }
.hero-meta-row { display: flex; gap: 8px; align-items: baseline; }
.hero-meta code { color: var(--text-primary); }
.muted { color: var(--text-muted); }

.wordmark { display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 700; letter-spacing: -0.01em; }
.wordmark-mark { width: 12px; height: 12px; border-radius: 4px; background: linear-gradient(135deg, var(--accent), var(--critical)); }

code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.92em;
  background: rgba(127,127,127,0.14);
  padding: 1px 6px;
  border-radius: 5px;
}

.card {
  background: var(--surface-1);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 32px 36px;
  margin-bottom: 24px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}
.card:hover {
  transform: translateY(-3px);
  border-color: color-mix(in srgb, var(--text-primary) 16%, var(--border));
  box-shadow: 0 20px 40px -20px rgba(0,0,0,0.5), 0 1px 0 rgba(255,255,255,0.03) inset;
}

.verdict {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-left: 4px solid transparent;
  position: relative;
  overflow: hidden;
  --spot-x: 50%; --spot-y: 50%;
}
.verdict::before {
  content: "";
  position: absolute; inset: 0;
  background: radial-gradient(320px circle at var(--spot-x) var(--spot-y), color-mix(in srgb, var(--spot-color, var(--accent)) 10%, transparent), transparent 70%);
  pointer-events: none;
  transition: opacity 0.3s ease;
  opacity: 0;
}
.verdict:hover::before { opacity: 1; }
.verdict-critical { border-left-color: var(--critical); --spot-color: var(--critical); }
.verdict-good { border-left-color: var(--good); --spot-color: var(--good); }
.verdict-left { display: flex; align-items: center; gap: 24px; flex: 1; min-width: 0; }
.verdict-icon {
  flex: none;
  width: 60px; height: 60px;
  border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
}
.verdict-critical .verdict-icon { color: var(--critical); background: color-mix(in srgb, var(--critical) 16%, transparent); }
.verdict-good .verdict-icon { color: var(--good); background: color-mix(in srgb, var(--good) 16%, transparent); }
.verdict-badge {
  display: inline-block;
  font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
  padding: 3px 9px; border-radius: 999px; margin-bottom: 10px;
}
.verdict-critical .verdict-badge { color: var(--critical); background: color-mix(in srgb, var(--critical) 16%, transparent); }
.verdict-good .verdict-badge { color: var(--good); background: color-mix(in srgb, var(--good) 16%, transparent); }
.verdict h1 { font-size: clamp(28px, 4.2vw, 48px); line-height: 1.03; letter-spacing: -0.025em; margin: 0 0 10px; }
.verdict-sentence { margin: 0 0 8px; color: var(--text-secondary); font-size: 15px; max-width: 58ch; }
.verdict-confidence { margin: 0; font-size: 14px; color: var(--text-secondary); }

.verdict-ring { flex: none; position: relative; width: 136px; height: 136px; }
.ring-svg { transform: scaleY(1); }
.ring-track { stroke: var(--gridline); }
.ring-fill { stroke-dasharray: var(--circumference); stroke-dashoffset: var(--circumference); transition: stroke-dashoffset 1.2s cubic-bezier(.2,.8,.2,1) 0.2s; }
.ring-fill-critical { stroke: var(--critical); }
.ring-fill-good { stroke: var(--good); }
.ring-label { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.ring-value { font-size: 24px; font-weight: 700; letter-spacing: -0.01em; }
.ring-caption { font-size: 10.5px; color: var(--text-muted); line-height: 1.3; margin-top: 2px; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 720px) { .grid-2 { grid-template-columns: 1fr; } .verdict { flex-direction: column; align-items: flex-start; } .verdict-ring { align-self: center; } }

.stat-card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.card h2 { font-size: 15px; font-weight: 600; letter-spacing: -0.005em; margin: 0; color: var(--text-primary); }

.chip { font-size: 11.5px; font-weight: 700; letter-spacing: 0.02em; padding: 4px 10px; border-radius: 999px; font-variant-numeric: tabular-nums; }
.chip-critical { color: var(--critical); background: color-mix(in srgb, var(--critical) 16%, transparent); }
.chip-good { color: var(--good); background: color-mix(in srgb, var(--good) 16%, transparent); }

.stats-table { width: 100%; border-collapse: collapse; font-size: 13.5px; margin-bottom: 18px; }
.stats-table th, .stats-table td { text-align: right; padding: 7px 4px; font-variant-numeric: tabular-nums; }
.stats-table thead th { color: var(--text-muted); font-weight: 500; font-size: 12px; border-bottom: 1px solid var(--gridline); }
.stats-table tbody th { text-align: left; color: var(--text-secondary); font-weight: 500; }
.stats-table tbody tr + tr th, .stats-table tbody tr + tr td { border-top: 1px solid var(--gridline); }

.test-results { display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px; }
.test-row {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 13.5px; color: var(--text-secondary);
  padding: 6px 10px;
  background: rgba(127,127,127,0.08);
  border-radius: 8px;
}
.test-row strong { color: var(--text-primary); font-variant-numeric: tabular-nums; }

.meter { margin-top: 4px; }
.meter-track { position: relative; height: 8px; border-radius: 999px; background: rgba(127,127,127,0.16); overflow: hidden; }
.meter-zone { position: absolute; top: 0; bottom: 0; border-right: 1px solid var(--page-plane); opacity: 0.5; }
.meter-fill { position: absolute; top: 0; left: 0; bottom: 0; border-radius: 999px; transition: width 1s cubic-bezier(.2,.8,.2,1) 0.3s; }
.meter-ticks { position: relative; height: 16px; font-size: 10px; color: var(--text-muted); }
.meter-ticks span { position: absolute; transform: translateX(-50%); top: 2px; }
.meter-caption { font-size: 12.5px; color: var(--text-secondary); margin-top: 10px; }
.meter-caption strong { color: var(--text-primary); font-variant-numeric: tabular-nums; }

.chart-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; }
.tabs { display: flex; gap: 2px; background: rgba(127,127,127,0.12); padding: 3px; border-radius: 11px; }
.tab {
  border: none; background: transparent; color: var(--text-secondary);
  font: inherit; font-size: 13px; font-weight: 600; padding: 7px 14px; border-radius: 8px;
  cursor: pointer; transition: background 0.2s ease, color 0.2s ease;
}
.tab.is-active { background: var(--surface-solid); color: var(--text-primary); box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
.tab:not(.is-active):hover { color: var(--text-primary); }
.legend { display: flex; gap: 16px; font-size: 13px; color: var(--text-secondary); }
.legend-item { display: flex; align-items: center; gap: 6px; }
.legend-swatch { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }

.chart-wrap { position: relative; }
.chart-pane { display: none; }
.chart-pane.is-active { display: block; }
.hist-svg { width: 100%; height: auto; display: block; }
.bar { fill-opacity: 0.92; transition: fill-opacity 0.15s ease; transform-box: fill-box; transform-origin: bottom; }
.hist-svg.is-active .bar { animation: bar-grow 0.5s cubic-bezier(.2,.8,.2,1) both; animation-delay: calc(var(--i) * 12ms); }
@keyframes bar-grow { from { transform: scaleY(0); } to { transform: scaleY(1); } }
@media (prefers-reduced-motion: reduce) { .hist-svg.is-active .bar { animation: none; transform: none; } }
.bar-valid { fill: var(--accent); }
.bar-invalid { fill: #ec4899; }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) .bar-invalid { fill: #db2777; } }
:root[data-theme="light"] .bar-invalid { fill: #db2777; }
.bar-hover { fill-opacity: 1; }
.axis-baseline { stroke: var(--text-muted); stroke-width: 1; opacity: 0.4; }
.gridline { stroke: var(--gridline); stroke-width: 1; }
.axis-label { fill: var(--text-muted); font-size: 11px; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.axis-title { fill: var(--text-secondary); font-size: 12px; }

.tooltip {
  position: absolute; top: 0; left: 0; min-width: 150px;
  background: var(--surface-solid); border: 1px solid var(--border); border-radius: 10px;
  padding: 10px 12px; font-size: 12.5px; pointer-events: none; opacity: 0;
  transition: opacity 0.12s ease; box-shadow: 0 12px 28px rgba(0,0,0,0.35); z-index: 10;
}
.tooltip-series { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); margin-bottom: 4px; }
.tooltip-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.tooltip-value { font-weight: 700; font-size: 14px; font-variant-numeric: tabular-nums; }
.tooltip-range { color: var(--text-muted); margin-top: 2px; }

.methodology ul { margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 13.5px; line-height: 1.9; }
.methodology li strong { color: var(--text-primary); }

.footer { text-align: center; color: var(--text-muted); font-size: 12.5px; margin-top: 24px; }

/* Info popover buttons */
.info-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 15px; height: 15px; margin-left: 5px; border-radius: 50%;
  border: 1px solid var(--border); background: transparent; color: var(--text-muted);
  font-size: 10px; font-style: italic; font-family: Georgia, serif; line-height: 1; cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
  vertical-align: middle;
}
.info-btn:hover, .info-btn.is-open { color: var(--text-primary); background: rgba(127,127,127,0.16); }
.info-popover {
  position: fixed; z-index: 40; max-width: 280px;
  background: var(--surface-solid); border: 1px solid var(--border); border-radius: 12px;
  padding: 12px 14px; font-size: 12.5px; line-height: 1.55; color: var(--text-secondary);
  box-shadow: 0 16px 32px rgba(0,0,0,0.35);
  opacity: 0; transform: translateY(4px); pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.info-popover.is-open { opacity: 1; transform: translateY(0); pointer-events: auto; }

/* Replay / sequence strip widget */
.replay-btn {
  display: flex; align-items: center; gap: 6px;
  border: 1px solid var(--border); background: rgba(127,127,127,0.08); color: var(--text-primary);
  font: inherit; font-size: 12.5px; font-weight: 600; padding: 7px 13px; border-radius: 999px;
  cursor: pointer; transition: background 0.2s ease, transform 0.1s ease;
}
.replay-btn:hover { background: rgba(127,127,127,0.18); }
.replay-btn:active { transform: scale(0.97); }
.replay-btn.is-playing { color: var(--accent); }
.sequence-strip-wrap { position: relative; height: 56px; margin-top: 4px; }
.sequence-strip { display: flex; align-items: flex-end; gap: 1px; height: 100%; width: 100%; }
.seq-tick { flex: 1 1 0; min-width: 1px; border-radius: 2px 2px 0 0; background: var(--accent); opacity: 0.35; transition: opacity 0.15s ease, transform 0.15s ease; transform-origin: bottom; }
.seq-tick.seq-invalid { background: #ec4899; }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) .seq-tick.seq-invalid { background: #db2777; } }
:root[data-theme="light"] .seq-tick.seq-invalid { background: #db2777; }
.seq-tick.is-played { opacity: 1; }
.seq-tick.is-current { opacity: 1; transform: scaleX(1.6); }
.sequence-playhead {
  position: absolute; top: 0; bottom: 0; width: 1px; left: 0;
  background: var(--text-primary); opacity: 0; pointer-events: none;
  transition: left 0.05s linear, opacity 0.2s ease;
  box-shadow: 0 0 8px var(--text-primary);
}
.sequence-playhead.is-active { opacity: 0.6; }
.sequence-status {
  margin-top: 12px; font-size: 12.5px; color: var(--text-secondary);
  font-variant-numeric: tabular-nums; min-height: 18px;
}
.sequence-status .seq-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; }

/* Raw samples table */
.samples-toggle {
  display: flex; align-items: center; gap: 6px;
  border: 1px solid var(--border); background: rgba(127,127,127,0.08); color: var(--text-primary);
  font: inherit; font-size: 12.5px; font-weight: 600; padding: 7px 13px; border-radius: 999px;
  cursor: pointer; transition: background 0.2s ease;
}
.samples-toggle:hover { background: rgba(127,127,127,0.18); }
.samples-toggle .chevron { transition: transform 0.2s ease; }
.samples-toggle.is-open .chevron { transform: rotate(180deg); }
.samples-body { max-height: 0; overflow: hidden; transition: max-height 0.35s cubic-bezier(.2,.8,.2,1); }
.samples-body.is-open { max-height: 460px; }
.samples-table-wrap { max-height: 400px; overflow-y: auto; margin-top: 16px; border-radius: 12px; border: 1px solid var(--border); }
.samples-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.samples-table thead th {
  position: sticky; top: 0; z-index: 1;
  background: var(--surface-solid); color: var(--text-muted); font-weight: 600; font-size: 11px;
  text-align: right; padding: 9px 12px; cursor: pointer; user-select: none;
  border-bottom: 1px solid var(--border); white-space: nowrap;
}
.samples-table thead th:first-child, .samples-table thead th:nth-child(2) { text-align: left; }
.samples-table thead th:hover { color: var(--text-primary); }
.samples-table thead th .sort-arrow { display: inline-block; width: 10px; opacity: 0.6; }
.samples-table tbody td { text-align: right; padding: 6px 12px; font-variant-numeric: tabular-nums; border-bottom: 1px solid var(--gridline); color: var(--text-secondary); }
.samples-table tbody td:first-child, .samples-table tbody td:nth-child(2) { text-align: left; }
.samples-table tbody tr:last-child td { border-bottom: none; }
.samples-table tbody tr:hover { background: rgba(127,127,127,0.06); }
.type-badge { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; color: var(--text-primary); }
.type-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }

/* Copy button + toast */
.copy-btn {
  display: flex; align-items: center; gap: 6px;
  border: 1px solid var(--border); background: rgba(127,127,127,0.08); color: var(--text-primary);
  font: inherit; font-size: 12.5px; font-weight: 600; padding: 7px 13px; border-radius: 999px;
  cursor: pointer; transition: background 0.2s ease;
}
.copy-btn:hover { background: rgba(127,127,127,0.18); }
.copy-btn.is-copied { color: var(--good); }
.toast {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%) translateY(12px);
  background: var(--surface-solid); border: 1px solid var(--border); border-radius: 999px;
  padding: 10px 18px; font-size: 13px; color: var(--text-primary);
  box-shadow: 0 16px 32px rgba(0,0,0,0.35);
  opacity: 0; pointer-events: none; transition: opacity 0.2s ease, transform 0.2s ease;
  z-index: 50;
}
.toast.is-visible { opacity: 1; transform: translateX(-50%) translateY(0); }

/* Hero stat tiles */
.stat-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 24px; }
.stat-tile {
  background: var(--surface-1); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border); border-radius: 16px; padding: 16px 18px;
  display: flex; flex-direction: column; gap: 4px;
}
.stat-tile-value { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.stat-tile-label { font-size: 11.5px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
@media (max-width: 800px) { .stat-strip { grid-template-columns: repeat(2, 1fr); } }

/* Timing race diagram */
.how-it-works-copy { color: var(--text-secondary); font-size: 13.5px; margin: 0 0 22px; max-width: 62ch; }
.race-lane { margin-bottom: 18px; }
.race-lane:last-child { margin-bottom: 0; }
.race-lane-label { display: flex; align-items: center; gap: 7px; font-size: 12.5px; color: var(--text-secondary); margin-bottom: 8px; }
.race-track { display: flex; align-items: center; gap: 12px; }
.race-node {
  flex: none; font-size: 11px; font-weight: 700; letter-spacing: 0.03em; color: var(--text-muted);
  border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; background: rgba(127,127,127,0.06);
}
.race-path { flex: 1; height: 2px; background: var(--gridline); position: relative; border-radius: 1px; }
.race-dot {
  position: absolute; top: 50%; left: 0; width: 12px; height: 12px; border-radius: 50%;
  transform: translate(-50%, -50%); box-shadow: 0 0 10px currentColor;
}
.race-dot-valid { background: var(--accent); color: var(--accent); }
.race-dot-invalid { background: #ec4899; color: #ec4899; }
.race-dot.is-running { animation-name: race-travel; animation-timing-function: cubic-bezier(.3,.6,.4,1); animation-fill-mode: forwards; }
@keyframes race-travel { from { left: 0%; } to { left: 100%; } }
.race-time { margin-top: 6px; font-size: 13px; font-variant-numeric: tabular-nums; color: var(--text-primary); font-weight: 600; text-align: right; }

/* Attack scenario stepper */
.scenario-hypothetical { font-size: 13px; color: var(--text-muted); margin: -6px 0 20px; padding: 10px 14px; background: rgba(127,127,127,0.08); border-radius: 10px; }
.scenario-steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 20px; }
.scenario-step { display: flex; gap: 14px; }
.scenario-num {
  flex: none; width: 30px; height: 30px; border-radius: 50%;
  background: color-mix(in srgb, var(--critical) 16%, transparent); color: var(--critical);
  display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px;
}
.scenario-step h3 { margin: 4px 0 6px; font-size: 14px; font-weight: 600; }
.scenario-step p { margin: 0; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
@media (max-width: 860px) { .scenario-steps { grid-template-columns: 1fr; } }

/* Remediation */
.remediation-list { list-style: none; margin: 4px 0 20px; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.remediation-list li { display: flex; gap: 10px; font-size: 13.5px; color: var(--text-secondary); line-height: 1.6; }
.check-icon {
  flex: none; width: 20px; height: 20px; border-radius: 50%; margin-top: 1px;
  background: color-mix(in srgb, var(--good) 18%, transparent); color: var(--good);
  display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;
}
.reference-links { display: flex; gap: 18px; flex-wrap: wrap; }
.reference-links a, .footer-links a {
  color: var(--accent); font-size: 13px; text-decoration: none; border-bottom: 1px solid transparent;
  transition: border-color 0.15s ease;
}
.reference-links a:hover, .footer-links a:hover { border-color: currentColor; }
.footer-links { display: flex; gap: 18px; justify-content: center; margin-bottom: 8px; }

/* Samples toolbar + export buttons */
.samples-toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.export-btn {
  display: flex; align-items: center; gap: 5px;
  border: 1px solid var(--border); background: transparent; color: var(--text-secondary);
  font: inherit; font-size: 12px; font-weight: 600; padding: 6px 11px; border-radius: 999px;
  cursor: pointer; transition: background 0.2s ease, color 0.2s ease;
}
.export-btn:hover { background: rgba(127,127,127,0.14); color: var(--text-primary); }

/* Fixed dot navigation */
.dot-nav {
  position: fixed; right: 20px; top: 50%; transform: translateY(-50%);
  display: flex; flex-direction: column; gap: 12px; z-index: 15;
}
@media (max-width: 1400px) { .dot-nav { display: none; } }
.dot-nav-item {
  position: relative; width: 8px; height: 8px; border-radius: 50%;
  background: var(--text-muted); opacity: 0.4; cursor: pointer; border: none; padding: 0;
  transition: opacity 0.2s ease, transform 0.2s ease, background 0.2s ease;
}
.dot-nav-item:hover { opacity: 0.8; transform: scale(1.3); }
.dot-nav-item.is-active { opacity: 1; background: var(--accent); transform: scale(1.4); }
.dot-nav-item .dot-nav-tooltip {
  position: absolute; right: 18px; top: 50%; transform: translateY(-50%);
  background: var(--surface-solid); border: 1px solid var(--border); border-radius: 8px;
  padding: 5px 10px; font-size: 11.5px; color: var(--text-primary); white-space: nowrap;
  opacity: 0; pointer-events: none; transition: opacity 0.15s ease;
}
.dot-nav-item:hover .dot-nav-tooltip { opacity: 1; }

/* Subtle 3D tilt on cards */
.card { transform-style: preserve-3d; perspective: 800px; }
.card.is-tilting { transition: transform 0.08s linear, box-shadow 0.25s ease, border-color 0.25s ease; }
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
  // Scroll-reveal for cards (staggered)
  var revealEls = document.querySelectorAll('.reveal');
  revealEls.forEach(function(el, i) { el.style.transitionDelay = (i * 60) + 'ms'; });
  var io = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  revealEls.forEach(function(el) { io.observe(el); });

  // Confidence ring animation
  requestAnimationFrame(function() {
    document.querySelectorAll('.ring-fill').forEach(function(ring) {
      var target = parseFloat(ring.getAttribute('data-target')) || 0;
      var circumference = parseFloat(getComputedStyle(ring).getPropertyValue('--circumference'));
      var offset = circumference * (1 - target / 100);
      requestAnimationFrame(function() { ring.style.strokeDashoffset = offset; });
    });
  });

  // Effect-size meter fill
  requestAnimationFrame(function() {
    document.querySelectorAll('.meter-fill').forEach(function(fill) {
      var target = fill.getAttribute('data-target');
      requestAnimationFrame(function() { fill.style.width = target + '%'; });
    });
  });

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
      var value = target * eased;
      el.textContent = value.toFixed(decimals) + suffix;
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

  // Tab switcher for the chart card
  var tabs = document.querySelectorAll('.tab');
  tabs.forEach(function(tab) {
    tab.addEventListener('click', function() {
      tabs.forEach(function(t) { t.classList.remove('is-active'); t.setAttribute('aria-selected', 'false'); });
      tab.classList.add('is-active'); tab.setAttribute('aria-selected', 'true');
      document.querySelectorAll('.chart-pane').forEach(function(pane) { pane.classList.remove('is-active'); });
      var targetPane = document.getElementById(tab.getAttribute('data-target'));
      if (targetPane) targetPane.classList.add('is-active');
      var svg = targetPane ? targetPane.querySelector('.hist-svg') : null;
      if (svg) { svg.classList.remove('is-active'); void svg.offsetWidth; svg.classList.add('is-active'); }
    });
  });

  // Cursor spotlight on the verdict card
  var verdictCard = document.querySelector('.verdict');
  if (verdictCard) {
    verdictCard.addEventListener('pointermove', function(e) {
      var rect = verdictCard.getBoundingClientRect();
      verdictCard.style.setProperty('--spot-x', (e.clientX - rect.left) + 'px');
      verdictCard.style.setProperty('--spot-y', (e.clientY - rect.top) + 'px');
    });
  }

  // Histogram bar tooltip
  var wrap = document.getElementById('chart-wrap');
  var tooltip = document.getElementById('tooltip');
  if (wrap && tooltip) {
    wrap.addEventListener('pointermove', function(e) {
      var bar = e.target.closest ? e.target.closest('.bar') : null;
      if (!bar) { tooltip.style.opacity = '0'; return; }
      var rect = wrap.getBoundingClientRect();
      var isValid = bar.classList.contains('bar-valid');
      var seriesLabel = isValid ? 'Valid username' : 'Invalid username';
      var count = bar.getAttribute('data-count');
      var range = bar.getAttribute('data-range');

      tooltip.innerHTML = '';
      var seriesEl = document.createElement('div');
      seriesEl.className = 'tooltip-series';
      var dot = document.createElement('span');
      dot.className = 'tooltip-dot';
      dot.style.background = isValid ? 'var(--accent)' : '#ec4899';
      seriesEl.appendChild(dot);
      seriesEl.appendChild(document.createTextNode(seriesLabel));

      var valueEl = document.createElement('div');
      valueEl.className = 'tooltip-value';
      valueEl.textContent = count + ' requests';

      var rangeEl = document.createElement('div');
      rangeEl.className = 'tooltip-range';
      rangeEl.textContent = range;

      tooltip.appendChild(seriesEl);
      tooltip.appendChild(valueEl);
      tooltip.appendChild(rangeEl);

      var x = e.clientX - rect.left + 14;
      var y = e.clientY - rect.top - 12;
      tooltip.style.transform = 'translate(' + x + 'px,' + y + 'px)';
      tooltip.style.opacity = '1';
    });
    wrap.addEventListener('pointerleave', function() { tooltip.style.opacity = '0'; });
  }

  // Scroll progress bar
  var progressBar = document.getElementById('scroll-progress');
  function updateProgress() {
    var doc = document.documentElement;
    var scrollable = doc.scrollHeight - doc.clientHeight;
    var pct = scrollable > 0 ? (doc.scrollTop / scrollable) * 100 : 0;
    if (progressBar) progressBar.style.width = pct + '%';
  }
  document.addEventListener('scroll', updateProgress, { passive: true });
  updateProgress();

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

  // Info popovers
  var popover = document.getElementById('info-popover');
  var openInfoBtn = null;
  function closePopover() {
    if (popover) popover.classList.remove('is-open');
    if (openInfoBtn) openInfoBtn.classList.remove('is-open');
    openInfoBtn = null;
  }
  document.querySelectorAll('.info-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      if (openInfoBtn === btn) { closePopover(); return; }
      closePopover();
      popover.textContent = btn.getAttribute('data-tip');
      var rect = btn.getBoundingClientRect();
      popover.style.left = Math.min(rect.left, window.innerWidth - 296) + 'px';
      popover.style.top = (rect.bottom + 8) + 'px';
      popover.classList.add('is-open');
      btn.classList.add('is-open');
      openInfoBtn = btn;
    });
  });
  document.addEventListener('click', closePopover);
  document.addEventListener('scroll', closePopover, { passive: true });

  // Copy repro commands
  var copyBtn = document.getElementById('copy-btn');
  var toast = document.getElementById('toast');
  var toastTimer = null;
  function showToast(text) {
    if (!toast) return;
    toast.textContent = text;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function() { toast.classList.remove('is-visible'); }, 2200);
  }
  if (copyBtn) {
    copyBtn.addEventListener('click', function() {
      var text = copyBtn.getAttribute('data-copy-valid') + '\\n\\n' + copyBtn.getAttribute('data-copy-invalid');
      var label = copyBtn.querySelector('.copy-btn-label');
      var finish = function(ok) {
        copyBtn.classList.toggle('is-copied', ok);
        if (label) label.textContent = ok ? 'Copied!' : 'Copy failed';
        showToast(ok ? 'Repro commands copied to clipboard' : 'Could not access clipboard');
        setTimeout(function() {
          copyBtn.classList.remove('is-copied');
          if (label) label.textContent = 'Copy repro commands';
        }, 1800);
      };
      timeleakCopyText(text).then(finish);
    });
  }

  // Sequence data (shared by the replay strip and the raw samples table)
  var sequenceDataEl = document.getElementById('sequence-data');
  var sequence = [];
  try { sequence = sequenceDataEl ? JSON.parse(sequenceDataEl.textContent) : []; } catch (err) { sequence = []; }

  // Request-sequence replay strip
  var strip = document.getElementById('sequence-strip');
  var playhead = document.getElementById('sequence-playhead');
  var seqStatus = document.getElementById('sequence-status');
  var replayBtn = document.getElementById('replay-btn');
  var maxMs = sequence.reduce(function(m, r) { return Math.max(m, r.ms); }, 1);
  if (strip && sequence.length) {
    sequence.forEach(function(r) {
      var tick = document.createElement('div');
      tick.className = 'seq-tick' + (r.type === 'invalid' ? ' seq-invalid' : '');
      var h = Math.max(6, (r.ms / maxMs) * 100);
      tick.style.height = h + '%';
      strip.appendChild(tick);
    });
  }
  var replayTimer = null;
  var replaying = false;
  function stopReplay() {
    replaying = false;
    clearTimeout(replayTimer);
    if (replayBtn) replayBtn.classList.remove('is-playing');
    if (playhead) playhead.classList.remove('is-active');
  }
  function playReplay() {
    if (!sequence.length || !strip) return;
    stopReplay();
    replaying = true;
    if (replayBtn) replayBtn.classList.add('is-playing');
    if (playhead) playhead.classList.add('is-active');
    var ticks = strip.querySelectorAll('.seq-tick');
    ticks.forEach(function(t) { t.classList.remove('is-played', 'is-current'); });
    var total = sequence.length;
    var durationMs = Math.min(7000, Math.max(2500, total * 40));
    var perTick = durationMs / total;
    var idx = 0;
    function step() {
      if (!replaying || idx >= total) { stopReplay(); return; }
      var r = sequence[idx];
      var tick = ticks[idx];
      if (idx > 0) ticks[idx - 1].classList.remove('is-current');
      tick.classList.add('is-played', 'is-current');
      var pct = ((idx + 1) / total) * 100;
      if (playhead) playhead.style.left = pct + '%';
      if (seqStatus) {
        var dotColor = r.type === 'invalid' ? '#ec4899' : 'var(--accent)';
        seqStatus.innerHTML = '';
        var dot = document.createElement('span');
        dot.className = 'seq-dot';
        dot.style.background = dotColor;
        seqStatus.appendChild(dot);
        seqStatus.appendChild(document.createTextNode(
          'Request ' + r.i + ' of ' + total + ' \\u2014 ' + r.type + ' \\u2014 ' + r.ms.toFixed(1) + 'ms \\u2014 ' + r.bytes + 'B \\u2014 HTTP ' + r.status
        ));
      }
      idx += 1;
      replayTimer = setTimeout(step, perTick);
    }
    step();
  }
  if (replayBtn) {
    replayBtn.addEventListener('click', function() {
      if (replaying) stopReplay(); else playReplay();
    });
  }

  // Raw samples table: collapsible + sortable
  var samplesToggle = document.getElementById('samples-toggle');
  var samplesBody = document.getElementById('samples-body');
  var tbody = document.getElementById('samples-tbody');
  var tableBuilt = false;
  var sortState = { key: 'i', dir: 1 };

  function renderTable() {
    if (!tbody) return;
    var rows = sequence.slice().sort(function(a, b) {
      var av = a[sortState.key], bv = b[sortState.key];
      if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase(); }
      if (av < bv) return -1 * sortState.dir;
      if (av > bv) return 1 * sortState.dir;
      return 0;
    });
    tbody.innerHTML = '';
    rows.forEach(function(r) {
      var tr = document.createElement('tr');

      var tdI = document.createElement('td'); tdI.textContent = r.i; tr.appendChild(tdI);

      var tdType = document.createElement('td');
      var badge = document.createElement('span');
      badge.className = 'type-badge';
      var dot = document.createElement('span');
      dot.className = 'type-dot';
      dot.style.background = r.type === 'invalid' ? '#ec4899' : 'var(--accent)';
      badge.appendChild(dot);
      badge.appendChild(document.createTextNode(r.type));
      tdType.appendChild(badge);
      tr.appendChild(tdType);

      var tdMs = document.createElement('td'); tdMs.textContent = r.ms.toFixed(3) + ' ms'; tr.appendChild(tdMs);
      var tdBytes = document.createElement('td'); tdBytes.textContent = r.bytes + ' B'; tr.appendChild(tdBytes);
      var tdStatus = document.createElement('td'); tdStatus.textContent = r.status == null ? '\\u2014' : r.status; tr.appendChild(tdStatus);
      var tdTime = document.createElement('td'); tdTime.textContent = r.time; tr.appendChild(tdTime);

      tbody.appendChild(tr);
    });
  }

  document.querySelectorAll('.samples-table thead th').forEach(function(th) {
    th.addEventListener('click', function() {
      var key = th.getAttribute('data-key');
      if (sortState.key === key) sortState.dir *= -1; else { sortState.key = key; sortState.dir = 1; }
      document.querySelectorAll('.samples-table thead th .sort-arrow').forEach(function(a) { a.textContent = ''; });
      var arrow = th.querySelector('.sort-arrow');
      if (!arrow) { arrow = document.createElement('span'); arrow.className = 'sort-arrow'; th.appendChild(arrow); }
      arrow.textContent = sortState.dir === 1 ? ' \\u2191' : ' \\u2193';
      renderTable();
    });
  });

  if (samplesToggle && samplesBody) {
    samplesToggle.addEventListener('click', function() {
      var isOpen = samplesBody.classList.toggle('is-open');
      samplesToggle.classList.toggle('is-open', isOpen);
      samplesToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      if (isOpen && !tableBuilt) { renderTable(); tableBuilt = true; }
    });
  }

  // Export buttons: trigger a file download (a Blob + <a download>, never a
  // popup) so nothing here can ever be blocked by a popup blocker.
  var jsonEl = document.getElementById('sequence-data');
  var csvEl = document.getElementById('sequence-csv');
  var exportJsonBtn = document.getElementById('export-json-btn');
  var exportCsvBtn = document.getElementById('export-csv-btn');
  function downloadFile(content, filename, mime) {
    var blob = new Blob([content], { type: mime });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
  }
  if (exportJsonBtn && jsonEl) {
    exportJsonBtn.addEventListener('click', function() {
      var pretty = JSON.stringify(JSON.parse(jsonEl.textContent), null, 2);
      downloadFile(pretty, 'timeleak_samples.json', 'application/json');
    });
  }
  if (exportCsvBtn && csvEl) {
    exportCsvBtn.addEventListener('click', function() {
      downloadFile(csvEl.textContent, 'timeleak_samples.csv', 'text/csv');
    });
  }

  // Timing race diagram
  var raceBtn = document.getElementById('race-btn');
  var raceLanes = document.querySelectorAll('.race-lane');
  function runRace() {
    raceLanes.forEach(function(lane) {
      var dot = lane.querySelector('.race-dot');
      var timeEl = lane.querySelector('.race-time');
      var duration = parseFloat(lane.getAttribute('data-duration')) || 1;
      var targetMs = parseFloat(timeEl.getAttribute('data-final') || timeEl.textContent);
      if (isNaN(targetMs)) { targetMs = parseFloat(timeEl.textContent); }
      timeEl.setAttribute('data-final', targetMs);
      dot.classList.remove('is-running');
      dot.style.animation = 'none';
      void dot.offsetWidth;
      dot.style.animation = 'race-travel ' + duration + 's cubic-bezier(.3,.6,.4,1) forwards';
      dot.classList.add('is-running');
      var start = null;
      function tick(ts) {
        if (start === null) start = ts;
        var progress = Math.min(1, (ts - start) / (duration * 1000));
        timeEl.textContent = (targetMs * progress).toFixed(1) + ' ms';
        if (progress < 1) requestAnimationFrame(tick);
        else timeEl.textContent = targetMs.toFixed(1) + ' ms';
      }
      requestAnimationFrame(tick);
    });
  }
  if (raceBtn) raceBtn.addEventListener('click', runRace);
  var raceSection = document.getElementById('how-it-works');
  if (raceSection) {
    var raceIo = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) { runRace(); raceIo.unobserve(entry.target); }
      });
    }, { threshold: 0.5 });
    raceIo.observe(raceSection);
  }

  // Fixed dot navigation
  var dotNav = document.getElementById('dot-nav');
  var navSections = [
    { id: 'verdict', label: 'Verdict' },
    { id: 'how-it-works', label: 'Timing race' },
    { id: 'stats', label: 'Stats' },
    { id: 'distribution', label: 'Distribution' },
    { id: 'sequence', label: 'Sequence' },
    { id: 'samples', label: 'Raw samples' },
    { id: 'scenario', label: 'Attack scenario' },
    { id: 'remediation', label: 'Remediation' },
    { id: 'methodology', label: 'Methodology' }
  ].filter(function(s) { return document.getElementById(s.id); });

  if (dotNav && navSections.length) {
    navSections.forEach(function(s) {
      var btn = document.createElement('button');
      btn.className = 'dot-nav-item';
      btn.type = 'button';
      btn.setAttribute('aria-label', s.label);
      btn.dataset.target = s.id;
      var tip = document.createElement('span');
      tip.className = 'dot-nav-tooltip';
      tip.textContent = s.label;
      btn.appendChild(tip);
      btn.addEventListener('click', function() {
        var target = document.getElementById(s.id);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      dotNav.appendChild(btn);
    });

    var dotItems = dotNav.querySelectorAll('.dot-nav-item');
    var navIo = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        var id = entry.target.id;
        var dot = dotNav.querySelector('.dot-nav-item[data-target="' + id + '"]');
        if (!dot) return;
        if (entry.isIntersecting) {
          dotItems.forEach(function(d) { d.classList.remove('is-active'); });
          dot.classList.add('is-active');
        }
      });
    }, { rootMargin: '-40% 0px -50% 0px', threshold: 0 });
    navSections.forEach(function(s) {
      var el = document.getElementById(s.id);
      if (el) navIo.observe(el);
    });
  }

  // Subtle 3D tilt on cards (skip the verdict card, which has its own spotlight effect)
  var tiltCards = document.querySelectorAll('.card:not(.verdict)');
  tiltCards.forEach(function(card) {
    card.addEventListener('pointerenter', function() { card.classList.add('is-tilting'); });
    card.addEventListener('pointermove', function(e) {
      var rect = card.getBoundingClientRect();
      var px = (e.clientX - rect.left) / rect.width - 0.5;
      var py = (e.clientY - rect.top) / rect.height - 0.5;
      var rx = (-py * 3).toFixed(2);
      var ry = (px * 3).toFixed(2);
      card.style.transform = 'perspective(800px) rotateX(' + rx + 'deg) rotateY(' + ry + 'deg) translateY(-3px)';
    });
    card.addEventListener('pointerleave', function() {
      card.classList.remove('is-tilting');
      card.style.transform = '';
    });
  });
})();
"""

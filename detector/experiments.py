"""
TimeLeak evaluation experiments.

Three repeatable studies that characterize the detector itself, run against
the demo app:

1. Precision  -- repeatedly scan the patched endpoint (/login/v3) and check
   for false positives.
2. Sensitivity -- shrink the real timing gap on /login/v1 via its
   ?inject_delay_ms= hook and find the smallest gap the detector still
   catches.
3. Sample-size study -- scan /login/v1 with increasing N and see how
   quickly the statistical signal converges.

Each experiment writes a CSV and a matplotlib PNG chart to
detector/reports/experiments/, styled to match the HTML report's palette.
"""
import argparse
import csv
import os
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from harness import check_results, preflight, sample_interleaved, split_by_type
from analysis import analyze
import theme

# --- Evidence File palette (theme.py): charts are printed "exhibits" on
# paper, so they read the same inside the paper and blueprint page themes --
BG = "#ffffff"
SURFACE = theme.SHEET
GRID = theme.GRID
TEXT = theme.INK
TEXT_MUTED = theme.FADED
ACCENT = theme.VALID
GOOD = theme.CLEAR
CRITICAL = theme.STAMP
WARNING = "#a16207"

EXPERIMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "experiments")


def _ensure_dir():
    os.makedirs(EXPERIMENTS_DIR, exist_ok=True)


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _style_axes(fig, ax):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=TEXT_MUTED, labelsize=10)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.6)
    ax.set_axisbelow(True)


def _write_csv(filename, fieldnames, rows):
    _ensure_dir()
    path = os.path.join(EXPERIMENTS_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _scan(url, valid_payload, invalid_payload, n_samples, warmup):
    preflight(url, valid_payload)
    results = sample_interleaved(url, valid_payload, invalid_payload, n_samples=n_samples, warmup=warmup)
    check_results(results)
    valid, invalid = split_by_type(results)
    return analyze(valid, invalid)


# ---------------------------------------------------------------------------
# 1. Precision test
# ---------------------------------------------------------------------------
def run_precision_test(base_url, valid_user="alice", invalid_user="notauser",
                        password="wrongpass", runs=10, samples=50, warmup=5,
                        progress_callback=None):
    """Run the detector against the patched endpoint (/login/v3) `runs`
    times and confirm it reports no leak each time (no false positives)."""
    url = f"{base_url}/login/v3"
    valid_payload = {"username": valid_user, "password": password}
    invalid_payload = {"username": invalid_user, "password": password}

    rows = []
    for i in range(1, runs + 1):
        report = _scan(url, valid_payload, invalid_payload, samples, warmup)
        v = report["verdict"]
        rows.append({
            "run": i,
            "leak_detected": v["leak_detected"],
            "confidence_level": v["confidence_level"],
            "timing_p_value": v["timing_p_value"],
            "timing_effect_size": v["timing_effect_size"],
            "size_p_value": v["size_p_value"],
        })
        if progress_callback:
            progress_callback(i, runs)

    false_positives = sum(1 for r in rows if r["leak_detected"])

    ts = _timestamp()
    csv_path = _write_csv(
        f"precision_{ts}.csv",
        ["run", "leak_detected", "confidence_level", "timing_p_value", "timing_effect_size", "size_p_value"],
        rows,
    )
    png_path = _plot_precision(rows, false_positives, runs, ts)

    return {"rows": rows, "false_positives": false_positives, "runs": runs, "csv": csv_path, "png": png_path}


def _plot_precision(rows, false_positives, runs, ts):
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    _style_axes(fig, ax)

    xs = [r["run"] for r in rows]
    ps = [r["timing_p_value"] for r in rows]
    colors = [CRITICAL if r["leak_detected"] else GOOD for r in rows]

    ax.scatter(xs, ps, c=colors, s=90, zorder=3, edgecolors=BG, linewidths=1)
    ax.axhline(0.05, color=WARNING, linestyle="--", linewidth=1.2, label="α = 0.05 significance threshold")
    ax.set_yscale("log")
    ax.set_xlabel("Run #")
    ax.set_ylabel("Mann-Whitney p-value (timing)")
    ax.set_title(f"Precision test: /login/v3 x {runs} runs  —  {false_positives} false positive(s)")
    ax.set_xticks(xs)
    legend = ax.legend(facecolor=SURFACE, edgecolor=GRID, labelcolor=TEXT, fontsize=9, loc="upper right")

    fig.tight_layout()
    _ensure_dir()
    path = os.path.join(EXPERIMENTS_DIR, f"precision_{ts}.png")
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 2. Sensitivity test
# ---------------------------------------------------------------------------
def run_sensitivity_test(base_url, valid_user="alice", invalid_user="notauser",
                          password="wrongpass", delays_ms=(50, 20, 10, 5, 1),
                          samples=80, warmup=5, progress_callback=None):
    """Scan /login/v1 with the 'user not found' path artificially padded by
    each delay in delays_ms, shrinking the real timing gap, to find the
    smallest leak the detector can still catch."""
    valid_payload = {"username": valid_user, "password": password}
    invalid_payload = {"username": invalid_user, "password": password}

    rows = []
    for i, delay in enumerate(delays_ms, start=1):
        url = f"{base_url}/login/v1?inject_delay_ms={delay}"
        report = _scan(url, valid_payload, invalid_payload, samples, warmup)
        v = report["verdict"]
        gap_ms = report["timing"]["valid"]["mean"] - report["timing"]["invalid"]["mean"]
        rows.append({
            "injected_delay_ms": delay,
            "resulting_gap_ms": round(gap_ms, 3),
            "leak_detected": v["leak_detected"],
            "timing_p_value": v["timing_p_value"],
            "timing_effect_size": v["timing_effect_size"],
            "timing_effect_label": v["timing_effect_label"],
        })
        if progress_callback:
            progress_callback(i, len(delays_ms))

    ts = _timestamp()
    csv_path = _write_csv(
        f"sensitivity_{ts}.csv",
        ["injected_delay_ms", "resulting_gap_ms", "leak_detected", "timing_p_value", "timing_effect_size", "timing_effect_label"],
        rows,
    )
    png_path = _plot_sensitivity(rows, ts)

    return {"rows": rows, "csv": csv_path, "png": png_path}


def _plot_sensitivity(rows, ts):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=150)
    for ax in (ax1, ax2):
        _style_axes(fig, ax)

    delays = [r["injected_delay_ms"] for r in rows]
    d_values = [r["timing_effect_size"] for r in rows]
    p_values = [max(r["timing_p_value"], 1e-300) for r in rows]
    colors = [CRITICAL if r["leak_detected"] else GOOD for r in rows]

    ax1.plot(delays, d_values, color=ACCENT, linewidth=1.5, zorder=2)
    ax1.scatter(delays, d_values, c=colors, s=80, zorder=3, edgecolors=BG, linewidths=1)
    ax1.axhline(0.2, color=WARNING, linestyle="--", linewidth=1.2, label="d = 0.2 (negligible threshold)")
    ax1.set_xlabel("Injected delay on invalid path (ms)")
    ax1.set_ylabel("Cohen's d (timing effect size)")
    ax1.set_title("Effect size vs. injected delay")
    ax1.invert_xaxis()
    ax1.legend(facecolor=SURFACE, edgecolor=GRID, labelcolor=TEXT, fontsize=8, loc="best")

    ax2.plot(delays, p_values, color=ACCENT, linewidth=1.5, zorder=2)
    ax2.scatter(delays, p_values, c=colors, s=80, zorder=3, edgecolors=BG, linewidths=1)
    ax2.axhline(0.05, color=WARNING, linestyle="--", linewidth=1.2, label="α = 0.05")
    ax2.set_yscale("log")
    ax2.set_xlabel("Injected delay on invalid path (ms)")
    ax2.set_ylabel("Mann-Whitney p-value (log scale)")
    ax2.set_title("Detection confidence vs. injected delay")
    ax2.invert_xaxis()
    ax2.legend(facecolor=SURFACE, edgecolor=GRID, labelcolor=TEXT, fontsize=8, loc="best")

    fig.suptitle("Sensitivity test: /login/v1 with shrinking timing gap", color=TEXT, fontsize=13)
    fig.tight_layout()
    _ensure_dir()
    path = os.path.join(EXPERIMENTS_DIR, f"sensitivity_{ts}.png")
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 3. Sample-size study
# ---------------------------------------------------------------------------
def run_sample_size_study(base_url, valid_user="alice", invalid_user="notauser",
                           password="wrongpass", sizes=(10, 25, 50, 100, 250, 500),
                           warmup=8, progress_callback=None):
    """Scan /login/v1 with increasing sample size N and record how the
    p-value and confidence evolve."""
    url = f"{base_url}/login/v1"
    valid_payload = {"username": valid_user, "password": password}
    invalid_payload = {"username": invalid_user, "password": password}

    rows = []
    for i, n in enumerate(sizes, start=1):
        report = _scan(url, valid_payload, invalid_payload, n, warmup)
        v = report["verdict"]
        rows.append({
            "n_samples": n,
            "leak_detected": v["leak_detected"],
            "confidence_level": v["confidence_level"],
            "timing_p_value": v["timing_p_value"],
            "timing_effect_size": v["timing_effect_size"],
        })
        if progress_callback:
            progress_callback(i, len(sizes))

    ts = _timestamp()
    csv_path = _write_csv(
        f"sample_size_{ts}.csv",
        ["n_samples", "leak_detected", "confidence_level", "timing_p_value", "timing_effect_size"],
        rows,
    )
    png_path = _plot_sample_size(rows, ts)

    return {"rows": rows, "csv": csv_path, "png": png_path}


def _plot_sample_size(rows, ts):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), dpi=150, sharex=True)
    for ax in (ax1, ax2):
        _style_axes(fig, ax)

    ns = [r["n_samples"] for r in rows]
    p_values = [max(r["timing_p_value"], 1e-300) for r in rows]
    d_values = [r["timing_effect_size"] for r in rows]
    colors = [CRITICAL if r["leak_detected"] else GOOD for r in rows]

    ax1.plot(ns, p_values, color=ACCENT, linewidth=1.5, zorder=2)
    ax1.scatter(ns, p_values, c=colors, s=80, zorder=3, edgecolors=BG, linewidths=1)
    ax1.axhline(0.05, color=WARNING, linestyle="--", linewidth=1.2, label="α = 0.05")
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_ylabel("Mann-Whitney p-value")
    ax1.set_title("Sample-size study: /login/v1")
    ax1.legend(facecolor=SURFACE, edgecolor=GRID, labelcolor=TEXT, fontsize=9, loc="best")

    ax2.plot(ns, d_values, color=ACCENT, linewidth=1.5, zorder=2)
    ax2.scatter(ns, d_values, c=colors, s=80, zorder=3, edgecolors=BG, linewidths=1)
    ax2.set_xscale("log")
    ax2.set_xlabel("Samples per group (N)")
    ax2.set_ylabel("Cohen's d (effect size)")
    ax2.set_xticks(ns)
    ax2.set_xticklabels([str(n) for n in ns])

    fig.tight_layout()
    _ensure_dir()
    path = os.path.join(EXPERIMENTS_DIR, f"sample_size_{ts}.png")
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path


def _build_arg_parser():
    parser = argparse.ArgumentParser(description="TimeLeak evaluation experiments")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Demo app base URL")
    parser.add_argument("--type", required=True, choices=["precision", "sensitivity", "sample-size", "all"])
    return parser


def main():
    args = _build_arg_parser().parse_args()

    def progress(i, total):
        print(f"  [{i}/{total}]")

    if args.type in ("precision", "all"):
        print("Running precision test (10x /login/v3)...")
        result = run_precision_test(args.base_url, progress_callback=progress)
        print(f"False positives: {result['false_positives']}/{result['runs']}")
        print(f"CSV: {result['csv']}")
        print(f"PNG: {result['png']}\n")

    if args.type in ("sensitivity", "all"):
        print("Running sensitivity test (/login/v1, shrinking gap)...")
        result = run_sensitivity_test(args.base_url, progress_callback=progress)
        print(f"CSV: {result['csv']}")
        print(f"PNG: {result['png']}\n")

    if args.type in ("sample-size", "all"):
        print("Running sample-size study (/login/v1)...")
        result = run_sample_size_study(args.base_url, progress_callback=progress)
        print(f"CSV: {result['csv']}")
        print(f"PNG: {result['png']}\n")


if __name__ == "__main__":
    main()

"""
TimeLeak statistical analysis.

Takes the raw sample records produced by harness.sample_interleaved() and
determines whether the "valid" and "invalid" groups differ significantly
in response timing and/or response size -- i.e. whether the endpoint
leaks information about which usernames exist.
"""
import warnings

import numpy as np
from scipy import stats

ALPHA = 0.05  # significance threshold for p-values

# Cohen's d thresholds (Cohen, 1988): below 0.2 is considered negligible
# even if statistically significant -- a real but practically unexploitable
# difference (e.g. sub-millisecond noise on a fast local network).
NEGLIGIBLE_EFFECT_D = 0.2
SMALL_EFFECT_D = 0.5
LARGE_EFFECT_D = 0.8

# A response-size difference below this many bytes is treated as noise
# even if a test reports it as "significant" (e.g. header-only jitter).
MIN_MEANINGFUL_SIZE_DELTA_BYTES = 2


def describe(samples):
    """Return {mean, median, std, n} for a 1D list/array of numbers."""
    arr = np.asarray(samples, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "n": int(len(arr)),
    }


def cohens_d(group_a, group_b):
    """
    Cohen's d effect size using the pooled standard deviation. Positive
    means group_a is larger on average. Returns 0.0 for degenerate inputs
    (fewer than 2 samples, or zero pooled variance with equal means).
    """
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return 0.0

    var1, var2 = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0 if np.mean(a) == np.mean(b) else float("inf")

    return float((np.mean(a) - np.mean(b)) / pooled_std)


def effect_size_label(d):
    ad = abs(d)
    if ad < NEGLIGIBLE_EFFECT_D:
        return "negligible"
    if ad < SMALL_EFFECT_D:
        return "small"
    if ad < LARGE_EFFECT_D:
        return "medium"
    return "large"


def _safe_mannwhitney(a, b):
    """Mann-Whitney U, tolerant of degenerate inputs (identical/constant
    samples) where scipy would otherwise emit warnings, raise, or return
    NaN (zero-variance normal approximation when every value is tied)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = stats.mannwhitneyu(a, b, alternative="two-sided")
        pvalue = float(result.pvalue)
    except ValueError:
        # e.g. "All numbers are identical" -- no detectable difference.
        return 1.0

    if np.isnan(pvalue):
        return 1.0
    return pvalue


def compare_distributions(group_a, group_b):
    """
    Compare two numeric groups (timing or size samples) with both Welch's
    t-test and the Mann-Whitney U test, plus Cohen's d effect size.

    Returns a dict with both p-values, the effect size and its label, and
    whether the difference counts as statistically AND practically
    significant.
    """
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t_result = stats.ttest_ind(a, b, equal_var=False)
    welch_p = float(t_result.pvalue) if not np.isnan(t_result.pvalue) else 1.0

    mannwhitney_p = _safe_mannwhitney(a, b)

    d = cohens_d(a, b)
    label = effect_size_label(d)

    statistically_significant = (welch_p < ALPHA) and (mannwhitney_p < ALPHA)
    practically_significant = label != "negligible"

    return {
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "welch_p_value": welch_p,
        "mannwhitney_p_value": mannwhitney_p,
        "cohens_d": d,
        "effect_size_label": label,
        "statistically_significant": statistically_significant,
        "practically_significant": practically_significant,
        # Significant p-value but negligible effect: real signal, likely
        # not exploitable in practice (e.g. p < 0.05 but d < 0.2).
        "significant_but_negligible": statistically_significant and not practically_significant,
    }


def analyze(valid_records, invalid_records):
    """
    Full analysis over harness output: compares timing (elapsed_ms) and
    response size (response_bytes) between the two groups and produces a
    verdict.

    valid_records / invalid_records: lists of dicts as produced by
    harness.split_by_type(), each containing 'elapsed_ms' and
    'response_bytes'.
    """
    valid_times = [r["elapsed_ms"] for r in valid_records]
    invalid_times = [r["elapsed_ms"] for r in invalid_records]
    valid_sizes = [r["response_bytes"] for r in valid_records]
    invalid_sizes = [r["response_bytes"] for r in invalid_records]

    timing_stats = {
        "valid": describe(valid_times),
        "invalid": describe(invalid_times),
        "comparison": compare_distributions(valid_times, invalid_times),
    }
    size_stats = {
        "valid": describe(valid_sizes),
        "invalid": describe(invalid_sizes),
        "comparison": compare_distributions(valid_sizes, invalid_sizes),
    }

    size_delta_bytes = abs(size_stats["valid"]["mean"] - size_stats["invalid"]["mean"])
    timing_comp = timing_stats["comparison"]
    size_comp = size_stats["comparison"]

    timing_leak = timing_comp["statistically_significant"] and timing_comp["practically_significant"]
    size_leak = (
        size_comp["statistically_significant"]
        and size_delta_bytes >= MIN_MEANINGFUL_SIZE_DELTA_BYTES
    )

    leak_detected = timing_leak or size_leak

    if leak_detected and (timing_comp["effect_size_label"] == "large" or size_delta_bytes >= 20):
        confidence_level = "high"
    elif leak_detected:
        confidence_level = "moderate"
    elif timing_comp["significant_but_negligible"] or size_comp["significant_but_negligible"]:
        confidence_level = "low (statistically significant but practically negligible)"
    else:
        confidence_level = "none"

    verdict = {
        "leak_detected": leak_detected,
        "timing_leak_detected": timing_leak,
        "size_leak_detected": size_leak,
        "timing_p_value": timing_comp["mannwhitney_p_value"],
        "timing_welch_p_value": timing_comp["welch_p_value"],
        "timing_effect_size": timing_comp["cohens_d"],
        "timing_effect_label": timing_comp["effect_size_label"],
        "size_p_value": size_comp["mannwhitney_p_value"],
        "size_delta_bytes": size_delta_bytes,
        "confidence_level": confidence_level,
    }

    return {
        "timing": timing_stats,
        "size": size_stats,
        "verdict": verdict,
    }

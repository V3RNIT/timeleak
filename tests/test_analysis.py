"""Verdict logic in detector/analysis.py (see CLAUDE.md "Detection logic")."""
import numpy as np

from analysis import analyze, cohens_d, compare_distributions, effect_size_label, _safe_mannwhitney


def _records(times, sizes):
    return [{"elapsed_ms": t, "response_bytes": s} for t, s in zip(times, sizes)]


def _rng():
    return np.random.default_rng(203)


def test_clear_timing_gap_is_a_high_confidence_leak():
    rng = _rng()
    valid = _records(rng.normal(80, 2, 40), [41] * 40)
    invalid = _records(rng.normal(3, 0.5, 40), [41] * 40)
    v = analyze(valid, invalid)["verdict"]
    assert v["leak_detected"] and v["timing_leak_detected"]
    assert not v["size_leak_detected"]
    assert v["confidence_level"] == "high"


def test_identical_distributions_are_not_a_leak():
    rng = _rng()
    valid = _records(rng.normal(80, 2, 40), [41] * 40)
    invalid = _records(rng.normal(80, 2, 40), [41] * 40)
    v = analyze(valid, invalid)["verdict"]
    assert not v["leak_detected"]
    assert v["confidence_level"] == "none"


def test_constant_size_difference_is_a_size_leak():
    rng = _rng()
    times = rng.normal(80, 2, 30)
    v = analyze(_records(times, [199] * 30), _records(rng.normal(80, 2, 30), [41] * 30))["verdict"]
    assert v["size_leak_detected"]
    assert v["size_delta_bytes"] == 158
    assert v["confidence_level"] == "high"  # delta >= 20 bytes


def test_one_byte_size_difference_is_ignored():
    rng = _rng()
    v = analyze(_records(rng.normal(5, 1, 30), [42] * 30), _records(rng.normal(5, 1, 30), [41] * 30))["verdict"]
    assert not v["size_leak_detected"]


def test_tiny_but_significant_gap_is_gated_by_effect_size():
    # Huge N makes a 0.05-sigma shift "significant"; Cohen's d keeps it out.
    rng = _rng()
    a = rng.normal(10.0, 1.0, 20000)
    b = rng.normal(10.05, 1.0, 20000)
    comp = compare_distributions(a, b)
    assert comp["statistically_significant"]
    assert not comp["practically_significant"]
    v = analyze(_records(a, [41] * len(a)), _records(b, [41] * len(b)))["verdict"]
    assert not v["leak_detected"]
    assert v["confidence_level"].startswith("low")


def test_mannwhitney_on_identical_constant_samples_is_one_not_nan():
    assert _safe_mannwhitney([41] * 20, [41] * 20) == 1.0


def test_cohens_d_edge_cases():
    assert cohens_d([1], [2]) == 0.0                      # too few samples
    assert cohens_d([5, 5, 5], [5, 5, 5]) == 0.0          # zero variance, equal means
    assert cohens_d([6, 6, 6], [5, 5, 5]) == float("inf")  # zero variance, different means
    assert effect_size_label(0.1) == "negligible"
    assert effect_size_label(-0.6) == "medium"
    assert effect_size_label(2.0) == "large"

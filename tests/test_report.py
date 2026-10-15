"""Report generation, its evidence seal, and the case index that links it."""
import hashlib
import html
import re

import numpy as np

from analysis import analyze
from index_builder import build_index
from report import generate_report


def _scan_records(rng, n=25):
    valid, invalid = [], []
    for k in range(n):
        ts = f"2026-10-15T10:00:{k:02d}.000000+00:00"
        valid.append({"payload_type": "valid", "elapsed_ms": float(rng.normal(80, 2)), "response_bytes": 41, "status_code": 401, "timestamp": ts})
        invalid.append({"payload_type": "invalid", "elapsed_ms": float(rng.normal(3, .4)), "response_bytes": 41, "status_code": 401, "timestamp": ts})
    return valid, invalid


def _make_report(tmp_path):
    valid, invalid = _scan_records(np.random.default_rng(7))
    path = generate_report(
        target_url="http://127.0.0.1:5000/login/v1", endpoint_label="POST /login/v1",
        valid_payload={"username": "alice", "password": "wrongpass"},
        invalid_payload={"username": "notauser", "password": "wrongpass"},
        analysis_result=analyze(valid, invalid), valid_records=valid, invalid_records=invalid,
        warmup_count=5, output_dir=str(tmp_path),
    )
    with open(path, encoding="utf-8") as f:
        return path, f.read()


def test_report_is_self_contained_and_states_verdict(tmp_path):
    _, doc = _make_report(tmp_path)
    assert '<meta name="timeleak:verdict" content="leak">' in doc
    assert "Enumerable" in doc                      # stamp verdict
    assert not re.search(r'<(script|link)[^>]+(src|href)="https?://', doc)  # no CDN
    assert "p = &lt;" not in doc and "statistical<br>confidence" not in doc


def test_evidence_seal_matches_embedded_csv(tmp_path):
    _, doc = _make_report(tmp_path)
    seal = re.search(r'<meta name="timeleak:seal" content="([0-9a-f]{64})">', doc).group(1)
    csv = html.unescape(re.search(r'<script type="text/plain" id="sequence-csv">(.*?)</script>', doc, re.S).group(1))
    assert hashlib.sha256(csv.encode("utf-8")).hexdigest() == seal
    assert seal in doc.split("Methodology", 1)[1]   # printed for readers too


def test_case_index_lists_the_report(tmp_path):
    path, _ = _make_report(tmp_path)
    index = build_index(str(tmp_path))
    with open(index, encoding="utf-8") as f:
        page = f.read()
    assert path.rsplit("/", 1)[-1] in page and "POST /login/v1" in page


def test_report_links_back_to_case_index(tmp_path):
    _, doc = _make_report(tmp_path)
    assert doc.count('href="index.html"') >= 2  # logo + footer

"""Request harness helpers in detector/harness.py."""
import socket

import pytest

from harness import ScanError, build_payload, check_results, expand_payload, preflight, split_by_type


def test_expand_payload_substitutes_fresh_token():
    out = expand_payload({"email": "probe+{n}@example.com", "password": "x"}, "42")
    assert out == {"email": "probe+42@example.com", "password": "x"}


def test_expand_payload_without_token_returns_same_object():
    payload = {"username": "alice", "password": "x"}
    assert expand_payload(payload, "1") is payload


def test_build_payload_overrides_extra_field():
    assert build_payload("username", "alice", {"password": "p", "username": "old"}) == {"password": "p", "username": "alice"}


def test_split_by_type_keeps_order():
    rs = [{"payload_type": t, "i": i} for i, t in enumerate(["valid", "invalid", "valid", "invalid"])]
    valid, invalid = split_by_type(rs)
    assert [r["i"] for r in valid] == [0, 2] and [r["i"] for r in invalid] == [1, 3]


def test_check_results_tolerates_a_few_failures():
    rs = [{"status_code": 401}] * 19 + [{"status_code": None}]
    assert check_results(rs) == 1


def test_check_results_rejects_mostly_failed_scan():
    rs = [{"status_code": None}] * 5 + [{"status_code": 401}] * 5
    with pytest.raises(ScanError):
        check_results(rs)


def test_preflight_fails_fast_on_closed_port():
    with socket.socket() as s:          # grab a free port, then close it
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(ScanError):
        preflight(f"http://127.0.0.1:{port}/login/v1", {"username": "a"}, timeout=1)

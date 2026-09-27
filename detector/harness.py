"""
TimeLeak request harness.

Sends controlled, interleaved requests to a target endpoint and precisely
measures wall-clock elapsed time and response body size, so that timing or
size differences between a "valid" and "invalid" payload can be analyzed
statistically (see analysis.py).

Standalone usage (mainly for testing this module in isolation -- Phase 6's
main.py wraps this with a friendlier CLI):

    python harness.py --url http://127.0.0.1:5000/login/v1 \
        --field username --valid-value alice --invalid-value notauser \
        --extra password=wrongpass --samples 50 --warmup 5
"""
import argparse
import json
import time
from datetime import datetime, timezone

import requests

DEFAULT_TIMEOUT_S = 5.0


def timed_request(session, url, payload, timeout=DEFAULT_TIMEOUT_S):
    """
    Send a single POST request and precisely measure elapsed wall-clock
    time (perf_counter, monotonic and immune to system clock adjustments)
    and response body size in bytes.

    Returns a dict: {elapsed_ms, response_bytes, status_code, timestamp}.
    On a network-level failure (timeout, connection error), status_code is
    None and response_bytes is 0 -- the caller decides whether to retry or
    discard the sample.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    try:
        resp = session.post(url, json=payload, timeout=timeout)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "elapsed_ms": elapsed_ms,
            "response_bytes": len(resp.content),
            "status_code": resp.status_code,
            "timestamp": timestamp,
        }
    except requests.exceptions.RequestException as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "elapsed_ms": elapsed_ms,
            "response_bytes": 0,
            "status_code": None,
            "timestamp": timestamp,
            "error": str(exc),
        }


def build_payload(field, value, extra_fields=None):
    payload = dict(extra_fields or {})
    payload[field] = value
    return payload


FRESH_TOKEN = "{n}"


def expand_payload(payload, token):
    """Replace every "{n}" in string values with `token`.

    Endpoints that change state on first contact -- a signup form registers
    the "non-existing" email on the very first request -- need a value that
    has never been seen before on every request, e.g.
    "probe+{n}@example.com". Payloads without "{n}" are returned unchanged.
    """
    if not any(isinstance(v, str) and FRESH_TOKEN in v for v in payload.values()):
        return payload
    return {k: v.replace(FRESH_TOKEN, token) if isinstance(v, str) else v for k, v in payload.items()}


def warmup_requests(session, url, valid_payload, invalid_payload, count):
    """Fire a handful of throwaway requests to avoid cold-start skew
    (first-connection TCP/TLS handshake cost, interpreter/JIT warmup,
    OS-level caching) polluting the real samples."""
    run_id = f"w{int(time.time() * 1000)}"
    for i in range(count):
        payload = valid_payload if i % 2 == 0 else invalid_payload
        timed_request(session, url, expand_payload(payload, f"{run_id}-{i}"))


def sample_interleaved(url, valid_payload, invalid_payload, n_samples,
                        warmup=5, delay_ms=0, timeout=DEFAULT_TIMEOUT_S,
                        progress_callback=None):
    """
    Send n_samples requests per group, interleaved (valid, invalid, valid,
    invalid, ...) rather than in two separate batches, so that network
    jitter and warm-up drift affect both groups equally instead of biasing
    whichever group happens to run first or second.

    Returns a list of dicts: {payload_type, elapsed_ms, response_bytes,
    status_code, timestamp}, in send order, length 2 * n_samples.
    """
    session = requests.Session()
    results = []
    run_id = f"{int(time.time() * 1000)}"

    if warmup > 0:
        warmup_requests(session, url, valid_payload, invalid_payload, warmup)

    for i in range(n_samples):
        for payload_type, payload in (("valid", valid_payload), ("invalid", invalid_payload)):
            sent = expand_payload(payload, f"{run_id}-{len(results)}")
            record = timed_request(session, url, sent, timeout=timeout)
            record["payload_type"] = payload_type
            results.append(record)
            if progress_callback:
                progress_callback(len(results), n_samples * 2)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

    session.close()
    return results


class ScanError(RuntimeError):
    """The target could not be measured reliably; no verdict should be drawn."""


# Above this share of failed requests (timeouts, refused connections) the
# samples no longer describe the endpoint's behaviour, only the network's --
# analysing them would report an unreachable server as "no leak".
MAX_FAILED_RATIO = 0.1


def preflight(url, payload, timeout=DEFAULT_TIMEOUT_S):
    """Send one request before sampling so a dead or mistyped target fails
    fast with a clear message instead of after N wasted requests."""
    with requests.Session() as session:
        record = timed_request(session, url, expand_payload(payload, f"pre{int(time.time() * 1000)}"), timeout=timeout)
    if record["status_code"] is None:
        raise ScanError(f"Could not reach {url}: {record.get('error', 'no response')}")
    return record


def check_results(results, max_failed_ratio=MAX_FAILED_RATIO):
    """Raise ScanError if too many requests failed at the network level."""
    failed = sum(1 for r in results if r["status_code"] is None)
    if results and failed / len(results) > max_failed_ratio:
        raise ScanError(
            f"{failed} of {len(results)} requests failed (no HTTP response); "
            "the target is unreachable or unstable, so no verdict was drawn."
        )
    return failed


def split_by_type(results):
    """Split a sample_interleaved() result list into (valid, invalid) lists."""
    valid = [r for r in results if r["payload_type"] == "valid"]
    invalid = [r for r in results if r["payload_type"] == "invalid"]
    return valid, invalid


def _build_arg_parser():
    parser = argparse.ArgumentParser(description="TimeLeak request harness (standalone test mode)")
    parser.add_argument("--url", required=True, help="Full target URL, e.g. http://127.0.0.1:5000/login/v1")
    parser.add_argument("--field", default="username", help="JSON field to vary between valid/invalid (default: username)")
    parser.add_argument("--valid-value", required=True, help="Value for the 'valid' payload group")
    parser.add_argument("--invalid-value", required=True, help="Value for the 'invalid' payload group")
    parser.add_argument("--extra", action="append", default=[], metavar="KEY=VALUE",
                         help="Extra constant payload field, e.g. --extra password=wrongpass (repeatable)")
    parser.add_argument("--samples", type=int, default=50, help="Number of samples per group (default: 50)")
    parser.add_argument("--warmup", type=int, default=5, help="Number of throwaway warmup requests (default: 5)")
    parser.add_argument("--delay-ms", type=float, default=0, help="Delay between requests in ms (default: 0)")
    parser.add_argument("--output", default=None, help="Optional path to save raw results as JSON")
    return parser


def _parse_extra_fields(extra_list):
    extra_fields = {}
    for item in extra_list:
        if "=" not in item:
            raise ValueError(f"--extra must be KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        extra_fields[key] = value
    return extra_fields


def main():
    args = _build_arg_parser().parse_args()
    extra_fields = _parse_extra_fields(args.extra)

    valid_payload = build_payload(args.field, args.valid_value, extra_fields)
    invalid_payload = build_payload(args.field, args.invalid_value, extra_fields)

    print(f"Target:  {args.url}")
    print(f"Valid:   {valid_payload}")
    print(f"Invalid: {invalid_payload}")
    print(f"Samples: {args.samples} per group | Warmup: {args.warmup}")
    print()

    results = sample_interleaved(
        args.url, valid_payload, invalid_payload,
        n_samples=args.samples, warmup=args.warmup, delay_ms=args.delay_ms,
    )

    valid, invalid = split_by_type(results)
    valid_times = [r["elapsed_ms"] for r in valid]
    invalid_times = [r["elapsed_ms"] for r in invalid]
    valid_sizes = [r["response_bytes"] for r in valid]
    invalid_sizes = [r["response_bytes"] for r in invalid]

    def avg(xs):
        return sum(xs) / len(xs) if xs else float("nan")

    print(f"Collected {len(results)} total requests ({len(valid)} valid / {len(invalid)} invalid)")
    print(f"  Valid   -> mean {avg(valid_times):.3f} ms | mean {avg(valid_sizes):.1f} bytes")
    print(f"  Invalid -> mean {avg(invalid_times):.3f} ms | mean {avg(invalid_sizes):.1f} bytes")

    status_codes = sorted({r["status_code"] for r in results})
    print(f"  Status codes seen: {status_codes}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nRaw results saved to {args.output}")


if __name__ == "__main__":
    main()

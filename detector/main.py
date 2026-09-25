"""
TimeLeak CLI entrypoint.

Usage:
    python main.py scan --url http://localhost:5000/login/v1 \
        --valid-user alice --invalid-user notauser --samples 100

    python main.py experiment --type precision
    python main.py experiment --type sensitivity
    python main.py experiment --type sample-size
    python main.py experiment --type all
"""
import argparse
import sys
from urllib.parse import urlparse

from harness import sample_interleaved, split_by_type
from analysis import analyze
from report import generate_report
import experiments
from dashboard import generate_experiments_dashboard
from index_builder import build_index


def _print_verdict(result):
    v = result["verdict"]
    print()
    print("=" * 60)
    print("LEAK DETECTED" if v["leak_detected"] else "NO SIGNIFICANT LEAK")
    print("=" * 60)
    print(f"Confidence level:      {v['confidence_level']}")
    print(f"Timing p-value:        {v['timing_p_value']:.4g}  (Cohen's d = {v['timing_effect_size']:.3f}, {v['timing_effect_label']})")
    print(f"Size p-value:          {v['size_p_value']:.4g}  (delta = {v['size_delta_bytes']:.1f} bytes)")
    print()


def cmd_scan(args):
    url = args.url
    valid_payload = {args.field: args.valid_user, "password": args.password}
    invalid_payload = {args.field: args.invalid_user, "password": args.password}

    print(f"Scanning {url}")
    print(f"  valid={valid_payload}  invalid={invalid_payload}")
    print(f"  samples={args.samples}  warmup={args.warmup}")

    results = sample_interleaved(
        url, valid_payload, invalid_payload,
        n_samples=args.samples, warmup=args.warmup,
    )
    valid, invalid = split_by_type(results)
    report = analyze(valid, invalid)
    _print_verdict(report)

    endpoint_label = f"POST {urlparse(url).path}"

    path = generate_report(
        target_url=url,
        endpoint_label=endpoint_label,
        valid_payload=valid_payload,
        invalid_payload=invalid_payload,
        analysis_result=report,
        valid_records=valid,
        invalid_records=invalid,
        warmup_count=args.warmup,
    )
    print(f"Report written to: {path}")

    index_path = build_index()
    print(f"Reports home updated: {index_path}")
    return report


def cmd_experiment(args):
    def progress(i, total):
        print(f"  [{i}/{total}]")

    precision = sensitivity = sample_size = None

    if args.type in ("precision", "all"):
        print(f"Running precision test ({args.runs}x {args.base_url}/login/v3)...")
        precision = experiments.run_precision_test(
            args.base_url, runs=args.runs, samples=args.samples, warmup=args.warmup,
            progress_callback=progress,
        )
        print(f"False positives: {precision['false_positives']}/{precision['runs']}")
        print(f"CSV: {precision['csv']}")
        print(f"PNG: {precision['png']}\n")

    if args.type in ("sensitivity", "all"):
        delays = tuple(int(x) for x in args.delays.split(","))
        print(f"Running sensitivity test ({args.base_url}/login/v1, delays={delays})...")
        sensitivity = experiments.run_sensitivity_test(
            args.base_url, delays_ms=delays, samples=args.samples, warmup=args.warmup,
            progress_callback=progress,
        )
        print(f"CSV: {sensitivity['csv']}")
        print(f"PNG: {sensitivity['png']}\n")

    if args.type in ("sample-size", "all"):
        sizes = tuple(int(x) for x in args.sizes.split(","))
        print(f"Running sample-size study ({args.base_url}/login/v1, sizes={sizes})...")
        sample_size = experiments.run_sample_size_study(
            args.base_url, sizes=sizes, warmup=args.warmup,
            progress_callback=progress,
        )
        print(f"CSV: {sample_size['csv']}")
        print(f"PNG: {sample_size['png']}\n")

    if args.type == "all" and precision and sensitivity and sample_size:
        dash_path = generate_experiments_dashboard(precision, sensitivity, sample_size)
        print(f"Dashboard written to: {dash_path}")

    index_path = build_index()
    print(f"Reports home updated: {index_path}")


def cmd_index(args):
    path = build_index()
    print(f"Reports home: {path}")


def _build_arg_parser():
    parser = argparse.ArgumentParser(description="TimeLeak: side-channel timing/response-size leakage detector")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan a single endpoint for a valid/invalid username leak")
    scan.add_argument("--url", required=True, help="Full target URL, e.g. http://localhost:5000/login/v1")
    scan.add_argument("--valid-user", required=True, help="A username known to exist")
    scan.add_argument("--invalid-user", required=True, help="A username known not to exist")
    scan.add_argument("--field", default="username", help="JSON field name for the username (default: username)")
    scan.add_argument("--password", default="wrongpass", help="Password value sent with every request (default: wrongpass)")
    scan.add_argument("--samples", type=int, default=100, help="Samples per group (default: 100)")
    scan.add_argument("--warmup", type=int, default=8, help="Warmup requests before sampling (default: 8)")
    scan.set_defaults(func=cmd_scan)

    experiment = sub.add_parser("experiment", help="Run a Phase 5 evaluation experiment")
    experiment.add_argument("--type", required=True, choices=["precision", "sensitivity", "sample-size", "all"])
    experiment.add_argument("--base-url", default="http://localhost:5000", help="Demo app base URL")
    experiment.add_argument("--runs", type=int, default=10, help="Precision test: number of repeated scans (default: 10)")
    experiment.add_argument("--samples", type=int, default=80, help="Samples per group for precision/sensitivity (default: 80)")
    experiment.add_argument("--warmup", type=int, default=8, help="Warmup requests per scan (default: 8)")
    experiment.add_argument("--delays", default="50,20,10,5,1", help="Sensitivity test: comma-separated injected delays in ms")
    experiment.add_argument("--sizes", default="10,25,50,100,250,500", help="Sample-size study: comma-separated N values")
    experiment.set_defaults(func=cmd_experiment)

    index_cmd = sub.add_parser("index", help="Rebuild the reports home page from whatever exists on disk")
    index_cmd.set_defaults(func=cmd_index)

    return parser


def main():
    parser = _build_arg_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)


if __name__ == "__main__":
    main()

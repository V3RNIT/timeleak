"""
TimeLeak one-command demo.

    python run.py                  # start demo app, scan all endpoints, run a quick evaluation, open the Case Index
    python run.py --samples 100    # more samples per group
    python run.py --full-eval      # full evaluation study (several minutes)
    python run.py --skip-eval      # scans only
    python run.py --no-browser     # don't open a browser (CI / remote machines)

Everything it produces is linked from detector/reports/index.html (the Case
Index): every scan report, the evaluation dashboard, and the live demo app.
It only ever targets the bundled demo app on 127.0.0.1.
"""
import argparse
import os
import subprocess
import sys
import time
import webbrowser

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
DETECTOR = os.path.join(ROOT, "detector")
DEMO_URL = "http://127.0.0.1:5000"
INDEX = os.path.join(DETECTOR, "reports", "index.html")

SCANS = [
    ("/login/v1", "username", "alice", "notauser"),
    ("/login/v2", "username", "alice", "notauser"),
    ("/login/v3", "username", "alice", "notauser"),
    # {n}: a never-seen email per request, otherwise signup registers it once
    ("/signup", "email", "alice@example.com", "probe+{n}@example.com"),
]


def _demo_up():
    try:
        return requests.get(DEMO_URL + "/health", headers={"Accept": "application/json"}, timeout=1).ok
    except requests.RequestException:
        return False


def _start_demo():
    """Start the demo app unless one is already answering. Returns the
    process we started (None if we reused a running one)."""
    if _demo_up():
        print(f"Demo app already running at {DEMO_URL}")
        return None
    print("Starting demo app...")
    log = open(os.path.join(ROOT, "demo-app", "demo-app.log"), "w")
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "demo-app", "app.py")], stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        if _demo_up():
            print(f"Demo app running at {DEMO_URL}")
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.25)
    sys.exit("Demo app failed to start; see demo-app/demo-app.log")


def _detector(*args):
    """Run detector/main.py with the given arguments, streaming its output."""
    cmd = [sys.executable, "main.py", *args]
    result = subprocess.run(cmd, cwd=DETECTOR)
    if result.returncode != 0:
        sys.exit(f"Command failed: {' '.join(cmd)}")


def main():
    parser = argparse.ArgumentParser(description="Run the full TimeLeak demo end to end")
    parser.add_argument("--samples", type=int, default=50, help="Samples per group for each scan (default: 50)")
    parser.add_argument("--skip-eval", action="store_true", help="Skip the evaluation experiments")
    parser.add_argument("--full-eval", action="store_true", help="Run the full evaluation (CLI defaults; several minutes)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open the Case Index in a browser")
    parser.add_argument("--exit", action="store_true", help="Stop the demo app when finished instead of keeping it running")
    args = parser.parse_args()

    # Fresh fake accounts so repeated signup scans start from the same state.
    subprocess.run([sys.executable, os.path.join(ROOT, "demo-app", "seed.py")], check=True, stdout=subprocess.DEVNULL)
    proc = _start_demo()

    try:
        for path, field, valid, invalid in SCANS:
            print(f"\n=== Scanning {path} ===")
            _detector("scan", "--url", DEMO_URL + path, "--field", field, "--valid-user", valid,
                      "--invalid-user", invalid, "--samples", str(args.samples))

        if not args.skip_eval:
            print("\n=== Evaluation experiments ===")
            if args.full_eval:
                _detector("experiment", "--type", "all", "--base-url", DEMO_URL)
            else:
                _detector("experiment", "--type", "all", "--base-url", DEMO_URL, "--runs", "3", "--samples", "20",
                          "--warmup", "3", "--delays", "20,5,1", "--sizes", "10,25,50")

        _detector("index")
        print(f"\nDone. Case Index: {INDEX}")
        if not args.no_browser:
            webbrowser.open("file://" + INDEX)

        if proc and not args.exit:
            print(f"Demo app still running at {DEMO_URL} (links on the Case Index use it). Press Ctrl+C to stop.")
            proc.wait()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        if proc and proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    main()

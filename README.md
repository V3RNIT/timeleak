# TimeLeak

A side-channel timing and response-size leakage detector for web authentication forms, built as a final-year CS minor project.

## What this is

Web login and signup endpoints often behave *slightly* differently depending on whether a submitted username or email exists — a faster or slower response, a longer or shorter error message. That difference is [CWE-203: Observable Discrepancy](https://cwe.mitre.org/data/definitions/203.html): an information leak that lets an attacker enumerate valid accounts without ever guessing a password, just by watching how the server responds. TimeLeak has two parts: a deliberately vulnerable Flask demo app (`/demo-app`) that reproduces this flaw in three different forms plus a patched control, and a statistical detector (`/detector`) that scans an endpoint, measures timing and response size, and tells you with a p-value and effect size whether it leaks.

## Project layout

```
demo-app/          Flask + SQLite target app (3 vulnerable login variants + 1 patched + signup)
detector/
  harness.py        Interleaved request sampling, precise timing
  analysis.py        Welch's t-test, Mann-Whitney U, Cohen's d, verdict logic
  report.py           Self-contained interactive HTML report generator
  experiments.py      Precision / sensitivity / sample-size evaluation studies
  dashboard.py         Combines the three experiments into one summary page
  index_builder.py      Builds the reports home page (detector/reports/index.html)
  main.py                 CLI entrypoint (scan / experiment / index)
  reports/                  Generated output lands here (gitignored)
```

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
```

Seed and start the demo app (leave this running in its own terminal):

```bash
python demo-app/seed.py
python demo-app/app.py
```

It listens on `http://127.0.0.1:5000` only — this project is not meant to be exposed externally.

## Usage

All commands below assume you're in `detector/` with the demo app running.

**Scan a single endpoint:**

```bash
python main.py scan --url http://localhost:5000/login/v1 --valid-user alice --invalid-user notauser --samples 100
```

Prints a verdict to the console and writes an interactive HTML report to `detector/reports/`.

**Run an evaluation experiment:**

```bash
python main.py experiment --type precision      # 10x scan against the patched endpoint, checks for false positives
python main.py experiment --type sensitivity     # shrinks the real timing gap via ?inject_delay_ms=, finds the detection floor
python main.py experiment --type sample-size     # increasing N, watches how fast the signal converges
python main.py experiment --type all             # runs all three and builds a combined dashboard
```

Each experiment writes a CSV and a matplotlib PNG chart to `detector/reports/experiments/`.

**Rebuild the reports home page on demand:**

```bash
python main.py index
```

`scan` and `experiment` already rebuild it automatically. Open `detector/reports/index.html` in a browser — it lists every scan report and evaluation dashboard you've generated, each opening in a new tab.

## Deployment

The demo app can be deployed publicly for free as a clearly-labeled, intentionally
vulnerable teaching target — the same idea as OWASP Juice Shop or WebGoat. It holds
no real user data (just 20 fake seeded accounts) and auto-seeds its database on
every boot, so it works fine on hosts with ephemeral disks.

**[Render.com](https://render.com) (recommended — free, simplest for Flask + SQLite):**

1. Push this repo to GitHub (see below).
2. On Render: **New → Web Service** → connect the repo.
3. Set **Root Directory** to `demo-app`.
4. **Build Command:** `pip install -r ../requirements.txt`
5. **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT` (already in `demo-app/Procfile`, Render picks it up automatically once Root Directory is set).
6. Deploy. Render assigns a free `https://<your-service>.onrender.com` URL and sets `$PORT` for you.

Free-tier services spin down after ~15 minutes idle and take a few seconds to wake
on the next request — normal for a free demo, but expect the *first* scan after a
quiet period to look like an outlier (cold-start latency, not a leak).

Then scan the live URL the same way as local:

```bash
python main.py scan --url https://<your-service>.onrender.com/login/v1 --valid-user alice --invalid-user notauser --samples 100
```

Note network latency to a real remote host adds noise the pure-localhost numbers
in this README don't have — the interleaved sampling still cancels it out fairly,
but expect wider variance than the local results above.

**Publishing an example report:** commit a generated report or two under
`detector/reports/` (they're gitignored by default; `git add -f` a couple you like)
and enable **GitHub Pages** (repo Settings → Pages → serve from the `detector/reports`
folder) for a free, static, permanent link to show off your results.

**GitHub setup**, if not done yet:

```bash
cd MINOR
git init
git add demo-app detector requirements.txt README.md .gitignore
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/timeleak.git
git push -u origin main
```

## Ethics

TimeLeak was built and tested **only** against the self-hosted demo app included in this repository, running on `localhost` under the author's own control. It is intended for **authorized security testing and developer self-assessment** — running it against your own code, or a system you have explicit written permission to test. Do not point this tool at any third-party system, production service, or endpoint you do not own or have authorization to test. Side-channel scanning of systems without permission is unauthorized access in most jurisdictions.

## Results summary

Real numbers from running this project's own demo app and detector end to end (N=40 samples/group unless noted; full-scale evaluation experiments used N=80–500 per the CLI defaults):

| Endpoint | Leak type | Verdict | Confidence | Cohen's d | p-value (Mann-Whitney) |
|---|---|---|---|---|---|
| `/login/v1` | Timing (CWE-203) | **LEAK DETECTED** | high | 6.24 (large) | < 0.0001 (1.44e-14) |
| `/login/v2` | Response size (CWE-203) | **LEAK DETECTED** | high | 6.10 (large, timing) | < 0.0001 (1.44e-14) — size delta 158 bytes, size p ≈ 6.5e-19 |
| `/login/v3` | Patched control | no significant leak | none | -0.105 (negligible) | 0.6685 |

**Precision test:** 0 / 10 false positives against `/login/v3`. One run's Mann-Whitney p-value alone dipped to 0.026 (would have been a false positive on its own), but Welch's t-test didn't agree — validating the dual-test-agreement requirement.

**Sensitivity test:** even at the largest tested injected delay (50ms, shrinking the real ~65ms gap down to **~5.4ms**), TimeLeak still detected the leak (d = 0.92, p ≈ 1.4e-15). The leak stayed detectable across the entire tested range `[50, 20, 10, 5, 1]`ms — the true detection floor is smaller than what was tested here.

**Sample-size study:** `/login/v1`'s leak is large enough (d ≈ 6–9) to be detected with high confidence at every tested N, including the smallest (**N = 10**).

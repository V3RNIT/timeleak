# TimeLeak — project context for Claude

Final-year B.Tech CST minor project (Dr. Akhilesh Das Gupta Institute of Professional
Studies, GGSIP University). Team: Vernit Singh Rana (owner), Ujjwal Kukreti, Harshit.

TimeLeak detects **CWE-203 Observable Discrepancy** in web login/signup forms: whether
a server responds measurably differently (timing or response size) for an existing vs.
non-existing username, which enables account enumeration.

## Layout

```
demo-app/            Deliberately vulnerable Flask + SQLite target (teaching target, like Juice Shop)
  app.py             /login/v1 timing leak, /login/v2 size leak, /login/v3 patched control,
                     /signup enumeration leak, /health (JSON + CORS), styled landing page.
                     Auto-seeds users.db on import. HOST/PORT env vars (default 127.0.0.1:5000).
                     ?inject_delay_ms= shrinks the timing gap (used by the sensitivity experiment).
  seed.py            20 fake users, password "Password123!"; alice = valid, notauser = invalid
  Procfile           gunicorn for Render.com
detector/
  harness.py         Interleaved valid/invalid sampling, warmup, time.perf_counter()
  analysis.py        Welch's t-test + Mann-Whitney U + Cohen's d -> verdict
  report.py          Self-contained interactive HTML report
  experiments.py     precision / sensitivity / sample-size studies (CSV + matplotlib PNG)
  dashboard.py       Combines the three experiments into one page
  index_builder.py   Builds detector/reports/index.html (home page linking everything)
  chatbot.py         Universal chatbot widget injected into every generated page
  main.py            CLI: scan / experiment / index
  reports/           Generated output (gitignored)
TimeLeak_Project_Synopsis.docx, TimeLeak_Synopsis_Presentation.pptx   College deliverables
```

## Run it (Linux / cloud)

```bash
pip install -r requirements.txt
python demo-app/app.py &                  # serves http://127.0.0.1:5000
cd detector
python main.py scan --url http://127.0.0.1:5000/login/v1 --valid-user alice --invalid-user notauser --samples 30
python main.py experiment --type precision --runs 3 --samples 30   # quick smoke run
python main.py index
```

Expected: v1 and v2 -> LEAK DETECTED, v3 -> no significant leak.
There is no automated test suite yet; `pytest` tests under `tests/` would be welcome.

## Detection logic (do not weaken without discussion)

- alpha = 0.05. A **timing leak** requires BOTH Welch p < 0.05 AND Mann-Whitney p < 0.05
  AND Cohen's d >= 0.2 (practical significance). The dual-test agreement is deliberate:
  it prevented a false positive in the precision study.
- A **size leak** requires both tests significant AND a mean size delta >= 2 bytes.
- `_safe_mannwhitney` coerces NaN p-values (identical distributions) to 1.0.
- Confidence: high if d is "large" or size delta >= 20 bytes; moderate otherwise.

## UI conventions for generated HTML

- Pages must be fully self-contained: inline CSS/JS/SVG, no CDNs, no external fonts.
- Dark violet theme everywhere: BG #0a0714, SURFACE #170f2b, GRID #2a2140,
  ACCENT #8b5cf6, GOOD #10b981, CRITICAL #f43f5e, WARNING #fbbf24,
  TEXT #f4f0ff, TEXT_MUTED #9a8fc4. Keep themes consistent across all pages.
- Links between pages open in a new tab: `target="_blank" rel="noopener noreferrer"`.
- Content must stay visible without JS (`.reveal` hiding is gated behind `html.js`).
- Exports use Blob downloads, not window.open. Every page includes the chatbot widget.
- Matplotlib must use the Agg backend (headless).

## Rules

- **Ethics:** only ever scan the bundled demo app on localhost (or the owner's own
  Render deployment). Never point the detector at any third-party system.
- **Official results come from the owner's laptop.** Numbers in README "Results summary",
  the synopsis and the slides must not be replaced with cloud-VM measurements; cloud
  timings differ. Cloud runs are fine for smoke tests.
- Don't commit generated reports, `users.db`, or `.venv/`.
- Python 3.11+. Keep dependencies to requirements.txt; ask before adding new ones.
- Match the existing code style: plain functions, module-level constants, docstrings
  explaining *why*, argparse CLIs.

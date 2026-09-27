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
  theme.py           "Evidence File" design system: palette tokens, embedded fonts, skin CSS/JS,
                     stamp helper. Every page loads theme.skin_style() after its own CSS.
  assets/fonts/      Barlow Condensed + Courier Prime woff2 (SIL OFL), inlined into pages
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
Signup: `python main.py scan --url http://127.0.0.1:5000/signup --field email --valid-user alice@example.com --invalid-user "probe+{n}@example.com"`
(`{n}` is replaced with a fresh value per request; without it the first request registers the email).
A scan aborts (exit 2, no report) if the target is unreachable or >10% of requests fail.
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
- "Evidence File" look everywhere (theme.py is the source of truth): graph-paper background,
  Courier Prime body text, Barlow Condensed uppercase headings, sheets with an offset
  paper-stack shadow, rubber-stamp verdicts. Paper (light, default) and Blueprint (dark) themes
  via tokens --paper/--sheet/--grid/--ink/--faded; data colours --valid (blue ink) vs --invalid
  (amber); verdict colours --stamp (leak) and --clear (clean). Don't reintroduce the old violet glass.
- Don't show 1 - p as a "confidence" percentage; confidence is the analysis label (high/moderate/none).
- Matplotlib charts use the paper palette (white sheet) so they read in both page themes.
- The demo app serves its fonts from demo-app/static/fonts (copies of detector/assets/fonts).
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

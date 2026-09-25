"""
TimeLeak Assistant -- a shared, self-contained FAQ chat widget embedded on
every generated page (scan reports, the evaluation dashboard, the reports
home page).

This is a client-side keyword-matching assistant, not a hosted LLM: these
are static HTML files meant to work fully offline, and shipping an API key
inside every generated report would be both a security anti-pattern and a
network dependency the rest of this project deliberately avoids. The
knowledge base below covers CWE-203, the statistics TimeLeak reports, and
CLI usage, plus a few dynamic facts about the specific page it's embedded
on (passed in via `facts`).
"""
import html
import json

_UNIVERSAL_ENTRIES = [
    {
        "keywords": ["what is timeleak", "about timeleak", "what does timeleak do", "purpose"],
        "answer": "TimeLeak is a side-channel timing and response-size leakage detector for web login/signup forms. It sends interleaved requests with a known-valid and a known-invalid username, measures timing and response size, and runs statistical tests to say whether the endpoint leaks which usernames exist.",
    },
    {
        "keywords": ["cwe-203", "cwe 203", "observable discrepancy", "what is cwe"],
        "answer": "CWE-203 (Observable Discrepancy) is a class of flaw where a system behaves differently depending on secret internal state — e.g. taking longer, or returning a different response, for a valid username than an invalid one. That difference alone can let an attacker enumerate accounts without ever guessing a password.",
    },
    {
        "keywords": ["timing leak", "timing attack", "timing side"],
        "answer": "A timing leak happens when the server takes measurably longer to respond for one case than another — e.g. running bcrypt.checkpw() only when a username exists. TimeLeak's harness sends interleaved requests and compares elapsed time (time.perf_counter()) between the two groups.",
    },
    {
        "keywords": ["size leak", "response size", "response-size", "byte"],
        "answer": "A response-size leak happens when the server returns a different payload length or structure depending on secret state — e.g. adding an extra hint field only when the password was wrong for a real account. TimeLeak compares response byte counts the same way it compares timing.",
    },
    {
        "keywords": ["welch", "t-test", "t test"],
        "answer": "Welch's t-test compares the means of two groups without assuming they have equal variance. It's sensitive to outliers, which is why TimeLeak also runs Mann-Whitney U and requires both to agree before calling something a leak.",
    },
    {
        "keywords": ["mann-whitney", "mann whitney", "u test"],
        "answer": "The Mann-Whitney U test compares the full distributions of two groups rather than just their means — it doesn't assume normality, which matters because network timing data is rarely perfectly normal. It's the more robust of the two tests TimeLeak runs.",
    },
    {
        "keywords": ["cohen", "effect size", "cohen's d"],
        "answer": "Cohen's d measures how large a difference is in practice, not just whether it's statistically detectable. TimeLeak treats d < 0.2 as negligible even if the p-value is tiny — a real but likely unexploitable difference, like sub-millisecond noise.",
    },
    {
        "keywords": ["p-value", "p value", "significance", "alpha"],
        "answer": "TimeLeak uses α = 0.05 as the significance threshold, and requires *both* Welch's t-test and Mann-Whitney U to fall below it before flagging a leak — a single test dipping under 0.05 by chance isn't enough on its own.",
    },
    {
        "keywords": ["interleav", "sampling method", "warmup"],
        "answer": "TimeLeak sends requests interleaved — valid, invalid, valid, invalid, ... — rather than in two separate batches, so network jitter and warm-up drift affect both groups equally instead of biasing whichever one runs first. A handful of throwaway warmup requests fire before real sampling starts too.",
    },
    {
        "keywords": ["how do i scan", "run a scan", "scan command", "scan an endpoint"],
        "answer": "python main.py scan --url http://localhost:5000/login/v1 --valid-user alice --invalid-user notauser --samples 100",
    },
    {
        "keywords": ["run experiment", "run the evaluation", "experiment command", "sensitivity test", "precision test", "sample-size study", "sample size study"],
        "answer": "python main.py experiment --type all — runs the precision, sensitivity, and sample-size studies and builds a combined dashboard. Use --type precision / sensitivity / sample-size to run just one.",
    },
    {
        "keywords": ["ethic", "authorized", "can i scan", "legal", "permission"],
        "answer": "TimeLeak is built for authorized self-assessment only — run it against your own code or a system you have explicit permission to test, never against a third party without authorization. See the Ethics section of the top-level README.",
    },
    {
        "keywords": ["cli", "command line", "main.py"],
        "answer": "The CLI has three subcommands: `scan` (test one endpoint), `experiment` (run an evaluation study), and `index` (rebuild this reports home page). Run `python main.py --help` for the full list of flags.",
    },
]

_FALLBACK_ANSWER = (
    "I don't have a canned answer for that — I'm a small keyword-matching "
    "assistant, not a full AI. Try asking about CWE-203, timing or size "
    "leaks, Welch's t-test, Mann-Whitney U, Cohen's d, or how to run a scan."
)

_GREETING = "Hi! I'm the TimeLeak Assistant. Ask me about CWE-203, the statistics on this page, or how to use the CLI."


def build_knowledge_base(page_entries=None):
    """page_entries: extra {'keywords': [...], 'answer': '...'} dicts specific
    to the page this widget is embedded on (e.g. this report's own verdict)."""
    entries = list(page_entries or []) + _UNIVERSAL_ENTRIES
    return entries


def render_chatbot(page_entries=None, suggestions=None):
    """
    Returns (html_snippet, kb_json) for the floating chat widget.
    `html_snippet` goes right before </body>; `kb_json` is embedded as a
    <script type="application/json"> the shared JS (in _CHATBOT_JS, appended
    to each page's own _JS) reads at runtime.
    """
    kb = build_knowledge_base(page_entries)
    kb_json = json.dumps(kb).replace("</", "<\\/")

    suggestions = suggestions or [
        "What is CWE-203?",
        "Explain Cohen's d",
        "How do I run a scan?",
    ]
    chip_html = "".join(
        f'<button class="tl-chip" type="button" data-q="{html.escape(s)}">{html.escape(s)}</button>'
        for s in suggestions
    )

    snippet = f'''
<div class="tl-chatbot" id="tl-chatbot">
  <button class="tl-fab" id="tl-fab" type="button" aria-label="Open TimeLeak Assistant" aria-expanded="false">
    <svg class="tl-fab-icon-chat" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H9l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-8Z"
            fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
      <circle cx="8.5" cy="9.5" r="1" fill="currentColor"/><circle cx="12" cy="9.5" r="1" fill="currentColor"/><circle cx="15.5" cy="9.5" r="1" fill="currentColor"/>
    </svg>
    <svg class="tl-fab-icon-close" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
  </button>

  <div class="tl-panel" id="tl-panel" role="dialog" aria-label="TimeLeak Assistant" aria-hidden="true">
    <div class="tl-panel-header">
      <div class="tl-panel-title">
        <span class="tl-panel-dot"></span>
        <span>TimeLeak Assistant</span>
      </div>
      <span class="tl-panel-sub">Rule-based &middot; answers from a fixed knowledge base</span>
    </div>
    <div class="tl-thread" id="tl-thread"></div>
    <div class="tl-chips" id="tl-chips">{chip_html}</div>
    <form class="tl-input-row" id="tl-form">
      <input class="tl-input" id="tl-input" type="text" placeholder="Ask about CWE-203, p-values, the CLI&hellip;" autocomplete="off" aria-label="Ask the TimeLeak Assistant">
      <button class="tl-send" type="submit" aria-label="Send">
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="m3 11 18-8-8 18-2-8-8-2Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>
      </button>
    </form>
  </div>
</div>
<script type="application/json" id="tl-kb">{kb_json}</script>
<script type="application/json" id="tl-greeting">{json.dumps(_GREETING)}</script>
<script type="application/json" id="tl-fallback">{json.dumps(_FALLBACK_ANSWER)}</script>
'''
    return snippet


CSS = """
.tl-chatbot { position: fixed; right: 22px; bottom: 22px; z-index: 60; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.tl-fab {
  width: 54px; height: 54px; border-radius: 50%; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--accent), var(--critical));
  color: #fff; box-shadow: 0 10px 28px -6px color-mix(in srgb, var(--accent) 60%, transparent);
  transition: transform 0.2s cubic-bezier(.2,.8,.2,1), box-shadow 0.2s ease;
  animation: tl-fab-breathe 2.8s ease-in-out infinite;
}
.tl-fab:hover { transform: scale(1.07); }
.tl-fab:active { transform: scale(0.96); }
@keyframes tl-fab-breathe {
  0%, 100% { box-shadow: 0 10px 28px -6px color-mix(in srgb, var(--accent) 60%, transparent); }
  50% { box-shadow: 0 10px 34px -4px color-mix(in srgb, var(--accent) 85%, transparent); }
}
.tl-chatbot.is-open .tl-fab { animation: none; }
.tl-fab-icon-close { display: none; }
.tl-chatbot.is-open .tl-fab-icon-chat { display: none; }
.tl-chatbot.is-open .tl-fab-icon-close { display: block; }

.tl-panel {
  position: absolute; right: 0; bottom: 68px; width: 340px; max-width: calc(100vw - 44px);
  height: 440px; max-height: calc(100vh - 120px);
  display: flex; flex-direction: column;
  background: var(--surface-solid); border: 1px solid var(--border); border-radius: 18px;
  box-shadow: 0 24px 60px -12px rgba(0,0,0,0.55);
  opacity: 0; transform: translateY(16px) scale(0.97); pointer-events: none;
  transform-origin: bottom right;
  transition: opacity 0.2s cubic-bezier(.2,.8,.2,1), transform 0.2s cubic-bezier(.2,.8,.2,1);
}
.tl-chatbot.is-open .tl-panel { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }

.tl-panel-header { padding: 16px 18px 12px; border-bottom: 1px solid var(--gridline); }
.tl-panel-title { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 700; color: var(--text-primary); }
.tl-panel-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--good); box-shadow: 0 0 0 3px color-mix(in srgb, var(--good) 25%, transparent); }
.tl-panel-sub { display: block; margin-top: 4px; font-size: 11px; color: var(--text-muted); }

.tl-thread { flex: 1; overflow-y: auto; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.tl-msg { max-width: 84%; padding: 9px 13px; border-radius: 14px; font-size: 13px; line-height: 1.5; word-break: break-word; white-space: pre-wrap; }
.tl-msg-bot { align-self: flex-start; background: rgba(139,92,246,0.12); color: var(--text-primary); border-bottom-left-radius: 4px; }
.tl-msg-user { align-self: flex-end; background: var(--accent); color: #ffffff; border-bottom-right-radius: 4px; }
.tl-msg-bot code, .tl-msg-user code { background: rgba(0,0,0,0.18); padding: 1px 5px; border-radius: 4px; font-size: 0.92em; }

.tl-typing { align-self: flex-start; display: flex; gap: 4px; padding: 10px 13px; background: rgba(139,92,246,0.12); border-radius: 14px; border-bottom-left-radius: 4px; }
.tl-typing span { width: 5px; height: 5px; border-radius: 50%; background: var(--text-muted); animation: tl-typing-bounce 1.1s ease-in-out infinite; }
.tl-typing span:nth-child(2) { animation-delay: 0.15s; }
.tl-typing span:nth-child(3) { animation-delay: 0.3s; }
@keyframes tl-typing-bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-4px); opacity: 1; } }

.tl-chips { display: flex; gap: 6px; flex-wrap: wrap; padding: 0 16px 10px; }
.tl-chip {
  border: 1px solid var(--border); background: rgba(127,127,127,0.08); color: var(--text-secondary);
  font: inherit; font-size: 11px; padding: 5px 10px; border-radius: 999px; cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.tl-chip:hover { background: rgba(127,127,127,0.16); color: var(--text-primary); }

.tl-input-row { display: flex; gap: 8px; padding: 12px 14px; border-top: 1px solid var(--gridline); }
.tl-input {
  flex: 1; background: rgba(127,127,127,0.08); border: 1px solid var(--border); border-radius: 999px;
  color: var(--text-primary); font: inherit; font-size: 12.5px; padding: 9px 14px; outline: none;
  transition: border-color 0.15s ease;
}
.tl-input:focus { border-color: var(--accent); }
.tl-input::placeholder { color: var(--text-muted); }
.tl-send {
  flex: none; width: 36px; height: 36px; border-radius: 50%; border: none; cursor: pointer;
  background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center;
  transition: transform 0.15s ease, background 0.15s ease;
}
.tl-send:hover { transform: scale(1.06); }

@media (max-width: 460px) {
  .tl-chatbot { right: 14px; bottom: 14px; }
  .tl-panel { width: calc(100vw - 28px); }
}
"""

JS = """
(function() {
  var root = document.getElementById('tl-chatbot');
  if (!root) return;
  var fab = document.getElementById('tl-fab');
  var panel = document.getElementById('tl-panel');
  var thread = document.getElementById('tl-thread');
  var form = document.getElementById('tl-form');
  var input = document.getElementById('tl-input');
  var chipsWrap = document.getElementById('tl-chips');

  var kb = [];
  var greeting = 'Hi!';
  var fallback = "I don't have an answer for that.";
  try { kb = JSON.parse(document.getElementById('tl-kb').textContent); } catch (e) {}
  try { greeting = JSON.parse(document.getElementById('tl-greeting').textContent); } catch (e) {}
  try { fallback = JSON.parse(document.getElementById('tl-fallback').textContent); } catch (e) {}

  var opened = false;

  function addMessage(text, who) {
    var msg = document.createElement('div');
    msg.className = 'tl-msg tl-msg-' + who;
    msg.textContent = text;
    thread.appendChild(msg);
    thread.scrollTop = thread.scrollHeight;
    return msg;
  }

  function findAnswer(query) {
    var q = query.toLowerCase();
    var best = null, bestScore = 0;
    kb.forEach(function(entry) {
      var score = 0;
      entry.keywords.forEach(function(kw) {
        if (q.indexOf(kw) !== -1) score += kw.length;
      });
      if (score > bestScore) { bestScore = score; best = entry; }
    });
    return best ? best.answer : fallback;
  }

  function respond(query) {
    addMessage(query, 'user');
    var typing = document.createElement('div');
    typing.className = 'tl-typing';
    typing.innerHTML = '<span></span><span></span><span></span>';
    thread.appendChild(typing);
    thread.scrollTop = thread.scrollHeight;
    var delay = 350 + Math.random() * 350;
    setTimeout(function() {
      thread.removeChild(typing);
      addMessage(findAnswer(query), 'bot');
    }, delay);
  }

  function openPanel() {
    root.classList.add('is-open');
    fab.setAttribute('aria-expanded', 'true');
    panel.setAttribute('aria-hidden', 'false');
    if (!opened) {
      opened = true;
      addMessage(greeting, 'bot');
    }
    input.focus();
  }
  function closePanel() {
    root.classList.remove('is-open');
    fab.setAttribute('aria-expanded', 'false');
    panel.setAttribute('aria-hidden', 'true');
  }

  fab.addEventListener('click', function() {
    if (root.classList.contains('is-open')) closePanel(); else openPanel();
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && root.classList.contains('is-open')) closePanel();
  });

  if (chipsWrap) {
    chipsWrap.querySelectorAll('.tl-chip').forEach(function(chip) {
      chip.addEventListener('click', function() { respond(chip.getAttribute('data-q')); });
    });
  }

  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      var text = input.value.trim();
      if (!text) return;
      input.value = '';
      respond(text);
    });
  }
})();
"""

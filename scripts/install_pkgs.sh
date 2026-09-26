#!/bin/bash
# Installs Python dependencies at the start of Claude Code cloud sessions.
# Exits immediately on local machines, where the .venv is already set up.

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR" || exit 0

# Skip the install when the environment cache already has everything.
if python -c "import flask, bcrypt, requests, numpy, scipy, matplotlib" 2>/dev/null; then
  exit 0
fi

# --ignore-installed blinker: the cloud image ships a Debian-owned blinker
# that pip cannot uninstall, which made Flask's install fail silently.
if ! pip install --quiet --ignore-installed blinker -r requirements.txt pytest; then
  echo "install_pkgs.sh: pip install failed; run it manually to see why" >&2
fi
exit 0

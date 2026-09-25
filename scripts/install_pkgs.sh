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

pip install --quiet -r requirements.txt pytest
exit 0

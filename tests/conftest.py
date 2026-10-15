"""Shared pytest setup: make detector/ and demo-app/ importable the same
way their own scripts import siblings (plain `import analysis`)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("detector", "demo-app"):
    path = os.path.join(ROOT, sub)
    if path not in sys.path:
        sys.path.insert(0, path)

#!/usr/bin/env sh
# Creates .venv with the pinned cdp CLI and pytest, and turns on the repo's git hooks.
set -e
cd "$(dirname "$0")/.."
if ! python3 -m venv .venv 2>/dev/null; then
  echo "python3 venv module missing: sudo apt-get install -y python3-venv (Linux), then rerun" >&2
  exit 1
fi
.venv/bin/pip install -q -r requirements.txt
git config core.hooksPath .githooks
.venv/bin/cdp --version
echo "ok: .venv ready, hooks on (.githooks)"

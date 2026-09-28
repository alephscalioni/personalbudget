#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=python3
if [[ -x .venv/bin/python ]]; then PYTHON=.venv/bin/python; fi
exec "$PYTHON" -m uvicorn backend.app:app --host "${PERSONALBUDGET_HOST:-127.0.0.1}" --port "${PERSONALBUDGET_PORT:-8787}"

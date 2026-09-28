#!/usr/bin/env bash
set -euo pipefail
BASE="/home/aleph/brain-panel/workspaces/kaleu"
cd "$BASE/scripts/finance/pluggy"
exec ./monitor_compras.py >>"$BASE/memory/monitor-compras.log" 2>&1

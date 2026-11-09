#!/usr/bin/env bash
# Gate for every PR. Done means this passes. Never weaken it to go green.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m py_compile monitor.py report.py scripts/health.py
python3 - <<'PY'
import glob, yaml
for f in glob.glob(".github/workflows/*.yml"):
    yaml.safe_load(open(f)); print("yaml ok", f)
PY
# Report builds from the live data branch (read-only copy in a temp dir)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git clone -q --depth 1 --branch data "https://github.com/ryancwho/duo-watch.git" "$tmp/data"
PYTHONPATH=. python3 report.py "$tmp/data" >/dev/null && grep -q "## Coverage" "$tmp/data/REPORT.md" && echo "report ok"
[ -d tests ] && python3 -m pytest -q tests || echo "no tests dir yet"
echo "CHECK PASSED"

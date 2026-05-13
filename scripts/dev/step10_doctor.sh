#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 10 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/run_toy_benchmark.py
echo "compileall: OK"
echo

echo "=== Run toy benchmark ==="
PYTHONPATH=src python3 scripts/dev/run_toy_benchmark.py
echo

test -f results/local/toy_benchmark_v0/results.jsonl
test -f results/local/toy_benchmark_v0/summary.json

python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("results/local/toy_benchmark_v0/summary.json").read_text())
rows = Path("results/local/toy_benchmark_v0/results.jsonl").read_text().strip().splitlines()

assert summary["total_tasks"] == 3, summary
assert summary["solved_tasks"] == 3, summary
assert summary["failed_tasks"] == 0, summary
assert summary["pass_rate"] == 1.0, summary
assert len(rows) == 3, rows

print("summary_json: OK")
print("results_jsonl_rows:", len(rows))
print("pass_rate:", summary["pass_rate"])
print("average_reward:", summary["average_reward"])
PY

echo
echo "STEP10_DOCTOR_OK"

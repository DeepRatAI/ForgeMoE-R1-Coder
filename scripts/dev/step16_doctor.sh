#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 16 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/run_toy_agentic_experiment.py
echo "compileall: OK"
echo

echo "=== Run toy agentic experiment ==="
PYTHONPATH=src python3 scripts/dev/run_toy_agentic_experiment.py
echo

test -f results/local/toy_agentic_experiment_v0/task_results.jsonl
test -f results/local/toy_agentic_experiment_v0/summary.json

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/toy_agentic_experiment_v0")
summary = json.loads((root / "summary.json").read_text())
rows = (root / "task_results.jsonl").read_text().strip().splitlines()

assert summary["total_tasks"] == 2, summary
assert summary["solved_tasks"] == 2, summary
assert summary["failed_tasks"] == 0, summary
assert summary["solve_rate"] == 1.0, summary
assert summary["total_parse_failures"] == 2, summary
assert len(rows) == 2, rows

print("experiment_summary: OK")
print("task_result_rows:", len(rows))
print("solve_rate:", summary["solve_rate"])
print("average_selected_reward:", summary["average_selected_reward"])
print("total_parse_failures:", summary["total_parse_failures"])
PY

echo
echo "STEP16_DOCTOR_OK"

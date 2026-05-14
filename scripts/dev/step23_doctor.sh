#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 23 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q \
  src/forgeagentcoder/agent/edit_intent.py \
  scripts/dev/run_structured_edit_intent_toy.py
echo "compileall: OK"
echo

echo "=== Run structured edit intent toy ==="
PYTHONPATH=src python3 scripts/dev/run_structured_edit_intent_toy.py
echo

RESULT_DIR="results/local/structured_edit_intent_toy_v0"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/task_results.jsonl"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/structured_edit_intent_toy_v0")
summary = json.loads((root / "summary.json").read_text())
rows = [json.loads(line) for line in (root / "task_results.jsonl").read_text().strip().splitlines()]

assert summary["schema_version"] == "forgeagent.structured_edit_intent_toy.v0", summary
assert summary["total_tasks"] == 3, summary
assert summary["valid_intents"] == 3, summary
assert summary["canonical_patch_count"] == 3, summary
assert summary["patch_apply_success_count"] == 3, summary
assert summary["solved_tasks"] == 3, summary
assert summary["solve_rate"] == 1.0, summary
assert len(rows) == 3, rows

print("structured_edit_intent_summary: OK")
print("total_tasks:", summary["total_tasks"])
print("valid_intents:", summary["valid_intents"])
print("canonical_patch_count:", summary["canonical_patch_count"])
print("patch_apply_success_count:", summary["patch_apply_success_count"])
print("solved_tasks:", summary["solved_tasks"])
print("solve_rate:", summary["solve_rate"])
print("elapsed_seconds:", summary["elapsed_seconds"])
PY

echo
echo "STEP23_DOCTOR_OK"

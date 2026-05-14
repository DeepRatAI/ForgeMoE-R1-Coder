#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 25 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q \
  src/forgeagentcoder/agent/edit_intent.py \
  src/forgeagentcoder/agent/intent_repair.py \
  scripts/dev/run_intent_repair_normalization_replay.py
echo "compileall: OK"
echo

echo "=== Run intent repair normalization replay ==="
PYTHONPATH=src python3 scripts/dev/run_intent_repair_normalization_replay.py
echo

RESULT_DIR="results/local/intent_repair_normalization_v0"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/task_results.jsonl"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/intent_repair_normalization_v0")
summary = json.loads((root / "summary.json").read_text())
rows = [json.loads(line) for line in (root / "task_results.jsonl").read_text().strip().splitlines()]

assert summary["schema_version"] == "forgeagent.intent_repair_normalization_replay.v0", summary
assert summary["total_tasks"] == 3, summary
assert summary["source_json_parse_success_count"] == 3, summary
assert summary["original_valid_intent_count"] == 0, summary
assert summary["repaired_valid_intent_count"] == 3, summary
assert summary["canonical_patch_count"] == 3, summary
assert summary["patch_apply_success_count"] == 3, summary
assert summary["solved_tasks"] == 3, summary
assert summary["solve_rate"] == 1.0, summary
assert len(rows) == 3, rows

print("intent_repair_summary: OK")
print("total_tasks:", summary["total_tasks"])
print("source_json_parse_success_count:", summary["source_json_parse_success_count"])
print("original_valid_intent_count:", summary["original_valid_intent_count"])
print("repaired_valid_intent_count:", summary["repaired_valid_intent_count"])
print("canonical_patch_count:", summary["canonical_patch_count"])
print("patch_apply_success_count:", summary["patch_apply_success_count"])
print("solved_tasks:", summary["solved_tasks"])
print("solve_rate:", summary["solve_rate"])
print("elapsed_seconds:", summary["elapsed_seconds"])
PY

echo
echo "STEP25_DOCTOR_OK"

#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 24.1 doctor ==="
python3 --version
echo

echo "=== Compile analyzer ==="
python3 -m compileall -q scripts/dev/analyze_step24_structured_intent.py
echo "compileall: OK"
echo

echo "=== Run Step 24.1 forensic analyzer ==="
PYTHONPATH=src python3 scripts/dev/analyze_step24_structured_intent.py
echo

test -f reports/local/step24_forensics/step24_structured_intent_forensics.json
test -f reports/local/step24_forensics/step24_structured_intent_forensics.md

python3 - <<'PY'
import json
from pathlib import Path

path = Path("reports/local/step24_forensics/step24_structured_intent_forensics.json")
data = json.loads(path.read_text())

assert data["schema_version"] == "forgeagent.step24_structured_intent_forensics.v0", data
assert data["task_count"] == 3, data
assert data["json_parse_success_count"] == 3, data
assert data["valid_intent_count"] == 0, data
assert data["canonical_patch_count"] == 0, data
assert data["patch_apply_success_count"] == 0, data
assert data["solved_tasks"] == 0, data
assert data["recommended_next_step"] == "intent_repair_and_normalization_v0", data

print("step24_forensics_json: OK")
print("task_count:", data["task_count"])
print("json_parse_success_count:", data["json_parse_success_count"])
print("valid_intent_count:", data["valid_intent_count"])
print("failure_categories:", data["failure_categories"])
print("validation_errors:", data["validation_errors"])
print("recommended_next_step:", data["recommended_next_step"])
PY

echo
echo "STEP24_1_DOCTOR_OK"

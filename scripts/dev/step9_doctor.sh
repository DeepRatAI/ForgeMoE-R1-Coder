#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 9 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/run_toy_patch_eval.py
echo "compileall: OK"
echo

echo "=== Run toy patch eval ==="
PYTHONPATH=src python3 scripts/dev/run_toy_patch_eval.py
echo

test -f results/local/toy_patch_eval_result.json

python3 - <<'PY'
import json
from pathlib import Path

path = Path("results/local/toy_patch_eval_result.json")
data = json.loads(path.read_text())

assert data["patch_applied"] is True, data
assert data["post_test"]["passed"] is True, data
assert data["reward"] > 0, data

print("result_json: OK")
print("task_id:", data["task_id"])
print("reward:", data["reward"])
PY

echo
echo "STEP9_DOCTOR_OK"

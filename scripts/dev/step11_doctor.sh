#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 11 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/run_toy_self_repair.py
echo "compileall: OK"
echo

echo "=== Run toy self-repair ==="
PYTHONPATH=src python3 scripts/dev/run_toy_self_repair.py
echo

test -f results/local/toy_self_repair_v0/trajectory.json

python3 - <<'PY'
import json
from pathlib import Path

path = Path("results/local/toy_self_repair_v0/trajectory.json")
data = json.loads(path.read_text())

assert data["solved"] is True, data
assert data["iterations_used"] == 2, data
assert data["best_patch_id"] == "good_patch_multiplication", data
assert len(data["trajectory"]) == 2, data
assert data["trajectory"][0]["post_tests_passed"] is False, data
assert data["trajectory"][1]["post_tests_passed"] is True, data

print("trajectory_json: OK")
print("iterations_used:", data["iterations_used"])
print("best_patch_id:", data["best_patch_id"])
print("best_reward:", data["best_reward"])
PY

echo
echo "STEP11_DOCTOR_OK"

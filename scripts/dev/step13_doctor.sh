#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 13 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/run_toy_executable_verifier.py
echo "compileall: OK"
echo

echo "=== Run toy executable verifier ==="
PYTHONPATH=src python3 scripts/dev/run_toy_executable_verifier.py
echo

test -f results/local/toy_executable_verifier_v0/verification.json

python3 - <<'PY'
import json
from pathlib import Path

path = Path("results/local/toy_executable_verifier_v0/verification.json")
data = json.loads(path.read_text())

assert data["solved"] is True, data
assert data["candidate_count"] == 3, data
assert data["selected_patch_id"] == "good_patch_modulo", data
assert data["ranked_candidates"][0]["patch_id"] == "good_patch_modulo", data
assert data["ranked_candidates"][0]["post_tests_passed"] is True, data

print("verification_json: OK")
print("candidate_count:", data["candidate_count"])
print("selected_patch_id:", data["selected_patch_id"])
print("selected_reward:", data["selected_reward"])
PY

echo
echo "STEP13_DOCTOR_OK"

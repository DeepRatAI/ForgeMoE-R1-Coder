#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 15 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/run_toy_candidate_generation_pipeline.py
echo "compileall: OK"
echo

echo "=== Run toy candidate generation pipeline ==="
PYTHONPATH=src python3 scripts/dev/run_toy_candidate_generation_pipeline.py
echo

test -f results/local/toy_candidate_pipeline_v0/generation_pipeline_result.json
test -f results/local/toy_candidate_pipeline_v0/prompt_messages.json

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/toy_candidate_pipeline_v0")
data = json.loads((root / "generation_pipeline_result.json").read_text())

assert data["solved"] is True, data
assert data["raw_response_count"] == 3, data
assert data["parsed_candidate_count"] == 2, data
assert data["parse_failure_count"] == 1, data
assert data["selected_patch_id"] == "raw_good_2_candidate_2", data
assert data["verifier_result"]["ranked_candidates"][0]["patch_id"] == "raw_good_2_candidate_2", data

print("generation_pipeline_result: OK")
print("raw_response_count:", data["raw_response_count"])
print("parsed_candidate_count:", data["parsed_candidate_count"])
print("parse_failure_count:", data["parse_failure_count"])
print("selected_patch_id:", data["selected_patch_id"])
PY

echo
echo "STEP15_DOCTOR_OK"

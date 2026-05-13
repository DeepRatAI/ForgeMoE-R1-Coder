#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 18 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/run_toy_model_adapter.py
echo "compileall: OK"
echo

echo "=== Run toy model adapter ==="
PYTHONPATH=src python3 scripts/dev/run_toy_model_adapter.py
echo

test -f results/local/toy_model_adapter_v0/prompt_messages.json
test -f results/local/toy_model_adapter_v0/generated_responses.jsonl
test -f results/local/toy_model_adapter_v0/candidate_pipeline_result.json
test -f results/local/toy_model_adapter_v0/model_adapter_result.json

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/toy_model_adapter_v0")
result = json.loads((root / "model_adapter_result.json").read_text())
generated_rows = (root / "generated_responses.jsonl").read_text().strip().splitlines()

pipeline = result["candidate_pipeline_result"]

assert result["schema_version"] == "forgeagent.model_adapter_result.v0", result
assert result["generated_response_count"] == 3, result
assert len(generated_rows) == 3, generated_rows
assert pipeline["solved"] is True, pipeline
assert pipeline["selected_patch_id"] == "mock_good_max2_candidate_2", pipeline
assert pipeline["parse_failure_count"] == 1, pipeline
assert result["local_transformers_skeleton_metadata"]["runtime"] == "local_transformers", result

print("model_adapter_result: OK")
print("generated_response_rows:", len(generated_rows))
print("selected_patch_id:", pipeline["selected_patch_id"])
print("parse_failure_count:", pipeline["parse_failure_count"])
print("skeleton_runtime:", result["local_transformers_skeleton_metadata"]["runtime"])
PY

echo
echo "STEP18_DOCTOR_OK"

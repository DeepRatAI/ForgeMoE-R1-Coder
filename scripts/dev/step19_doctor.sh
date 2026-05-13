#!/usr/bin/env bash
set -euo pipefail

VENV="${FORGEMOE_STEP19_VENV:-/tmp/forgemoe-step19-venv}"

echo "=== Step 19 doctor ==="
"${VENV}/bin/python" --version
echo

echo "=== Dependency check ==="
"${VENV}/bin/python" - <<'PY'
import torch
import transformers
print("torch:", torch.__version__)
print("transformers:", transformers.__version__)
print("cuda_available:", torch.cuda.is_available())
PY
echo

echo "=== Compile source ==="
"${VENV}/bin/python" -m compileall -q src scripts/dev/run_tiny_real_model_smoke.py
echo "compileall: OK"
echo

echo "=== Run tiny real model smoke ==="
PYTHONPATH=src \
HF_HOME="${HF_HOME:-/tmp/forgemoe-hf-cache}" \
HF_HUB_CACHE="${HF_HUB_CACHE:-/tmp/forgemoe-hf-cache/hub}" \
"${VENV}/bin/python" scripts/dev/run_tiny_real_model_smoke.py
echo

RESULT_DIR="results/local/tiny_real_model_smoke_v0/sshleifer_tiny-gpt2"

test -f "${RESULT_DIR}/prompt_messages.json"
test -f "${RESULT_DIR}/generated_responses.jsonl"
test -f "${RESULT_DIR}/parse_failures.json"
test -f "${RESULT_DIR}/tiny_real_model_smoke_result.json"

"${VENV}/bin/python" - <<'PY'
import json
from pathlib import Path

root = Path("results/local/tiny_real_model_smoke_v0/sshleifer_tiny-gpt2")
result = json.loads((root / "tiny_real_model_smoke_result.json").read_text())
generated_rows = (root / "generated_responses.jsonl").read_text().strip().splitlines()

assert result["schema_version"] == "forgeagent.tiny_real_model_smoke.v0", result
assert result["model_load_ok"] is True, result
assert result["real_generation_ok"] is True, result
assert result["generated_response_count"] >= 1, result
assert len(generated_rows) == result["generated_response_count"], generated_rows
assert result["solve_required"] is False, result
assert result["runtime"] == "local_transformers", result

print("tiny_real_model_smoke_result: OK")
print("model_id:", result["model_id"])
print("generated_response_count:", result["generated_response_count"])
print("parsed_candidate_count:", result["parsed_candidate_count"])
print("parse_failure_count:", result["parse_failure_count"])
print("candidate_pipeline_attempted:", result["candidate_pipeline_attempted"])
PY

echo
echo "STEP19_DOCTOR_OK"

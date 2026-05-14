#!/usr/bin/env bash
set -euo pipefail

VENV="${FORGEMOE_STEP20_VENV:-/tmp/forgemoe-step20-venv}"

echo "=== Step 20 doctor ==="
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
"${VENV}/bin/python" -m compileall -q src scripts/dev/run_qwen2_5_coder_0_5b_baseline.py
echo "compileall: OK"
echo

echo "=== Run Qwen2.5-Coder 0.5B baseline ==="
PYTHONPATH=src \
HF_HOME="${HF_HOME:-/tmp/forgemoe-hf-cache}" \
HF_HUB_CACHE="${HF_HUB_CACHE:-/tmp/forgemoe-hf-cache/hub}" \
FORGEMOE_STEP20_MODEL_ID="${FORGEMOE_STEP20_MODEL_ID:-Qwen/Qwen2.5-Coder-0.5B-Instruct}" \
"${VENV}/bin/python" scripts/dev/run_qwen2_5_coder_0_5b_baseline.py
echo

RESULT_DIR="results/local/qwen2_5_coder_0_5b_baseline_v0"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/task_results.jsonl"
test -f "${RESULT_DIR}/all_generated_responses.jsonl"

"${VENV}/bin/python" - <<'PY'
import json
from pathlib import Path

root = Path("results/local/qwen2_5_coder_0_5b_baseline_v0")
summary = json.loads((root / "summary.json").read_text())
rows = (root / "task_results.jsonl").read_text().strip().splitlines()

assert summary["schema_version"] == "forgeagent.real_code_model_baseline.v0", summary
assert summary["model_id"] == "Qwen/Qwen2.5-Coder-0.5B-Instruct", summary
assert summary["model_load_ok"] is True, summary
assert summary["real_generation_ok"] is True, summary
assert summary["total_tasks"] == 3, summary
assert summary["generated_response_count"] == 3, summary
assert len(rows) == 3, rows
assert 0.0 <= summary["solve_rate"] <= 1.0, summary

print("qwen_baseline_summary: OK")
print("total_tasks:", summary["total_tasks"])
print("generated_response_count:", summary["generated_response_count"])
print("parsed_candidate_count:", summary["parsed_candidate_count"])
print("parse_failure_count:", summary["parse_failure_count"])
print("candidate_pipeline_attempted_count:", summary["candidate_pipeline_attempted_count"])
print("solved_tasks:", summary["solved_tasks"])
print("solve_rate:", summary["solve_rate"])
print("elapsed_seconds:", summary["elapsed_seconds"])
PY

echo
echo "STEP20_DOCTOR_OK"

#!/usr/bin/env bash
set -euo pipefail

VENV="${FORGEMOE_STEP20_VENV:-/tmp/forgemoe-step20-venv}"

echo "=== Step 21 doctor ==="
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
"${VENV}/bin/python" -m compileall -q \
  src/forgeagentcoder/agent/prompt_contract.py \
  scripts/dev/run_qwen2_5_coder_prompt_contract_v1.py

echo "compileall: OK"
echo

echo "=== Run Qwen2.5-Coder Prompt Contract v1 baseline ==="
PYTHONPATH=src \
HF_HOME="${HF_HOME:-/tmp/forgemoe-hf-cache}" \
HF_HUB_CACHE="${HF_HUB_CACHE:-/tmp/forgemoe-hf-cache/hub}" \
FORGEMOE_STEP21_MODEL_ID="${FORGEMOE_STEP21_MODEL_ID:-Qwen/Qwen2.5-Coder-0.5B-Instruct}" \
"${VENV}/bin/python" scripts/dev/run_qwen2_5_coder_prompt_contract_v1.py
echo

RESULT_DIR="results/local/qwen2_5_coder_0_5b_prompt_contract_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/task_results.jsonl"
test -f "${RESULT_DIR}/all_generated_responses.jsonl"

"${VENV}/bin/python" - <<'PY'
import json
from pathlib import Path

root = Path("results/local/qwen2_5_coder_0_5b_prompt_contract_v1")
summary = json.loads((root / "summary.json").read_text())
rows = (root / "task_results.jsonl").read_text().strip().splitlines()

assert summary["schema_version"] == "forgeagent.prompt_contract_baseline.v0", summary
assert summary["model_id"] == "Qwen/Qwen2.5-Coder-0.5B-Instruct", summary
assert summary["model_load_ok"] is True, summary
assert summary["real_generation_ok"] is True, summary
assert summary["total_tasks"] == 3, summary
assert summary["generated_response_count"] == 3, summary
assert len(rows) == 3, rows
assert 0 <= summary["patch_apply_success_count"] <= 3, summary
assert 0 <= summary["solved_tasks"] <= 3, summary

print("prompt_contract_summary: OK")
print("total_tasks:", summary["total_tasks"])
print("generated_response_count:", summary["generated_response_count"])
print("parsed_candidate_count:", summary["parsed_candidate_count"])
print("parse_failure_count:", summary["parse_failure_count"])
print("candidate_pipeline_attempted_count:", summary["candidate_pipeline_attempted_count"])
print("patch_apply_success_count:", summary["patch_apply_success_count"])
print("solved_tasks:", summary["solved_tasks"])
print("solve_rate:", summary["solve_rate"])
print("patch_apply_success_delta:", summary["comparison_against_step20"]["patch_apply_success_delta"])
print("solved_tasks_delta:", summary["comparison_against_step20"]["solved_tasks_delta"])
print("elapsed_seconds:", summary["elapsed_seconds"])
PY

echo
echo "STEP21_DOCTOR_OK"

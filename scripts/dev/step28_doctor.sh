#!/usr/bin/env bash
set -euo pipefail

VENV="${FORGEMOE_STEP28_VENV:-/tmp/forgemoe-step28-venv}"

echo "=== Step 28 doctor ==="
"${VENV}/bin/python" --version
echo

echo "=== Dependency check ==="
"${VENV}/bin/python" - <<'PY'
import torch
import transformers
import peft
import accelerate

print("torch:", torch.__version__)
print("transformers:", transformers.__version__)
print("peft:", peft.__version__)
print("accelerate:", accelerate.__version__)
print("cuda_available:", torch.cuda.is_available())
PY
echo

echo "=== Compile source ==="
"${VENV}/bin/python" -m compileall -q \
  scripts/dev/run_local_lora_sft_dry_run.py \
  src/forgeagentcoder/training
echo "compileall: OK"
echo

echo "=== Run memory-safe local LoRA SFT dry run ==="
PYTHONPATH=src \
HF_HOME="${HF_HOME:-/tmp/forgemoe-hf-cache}" \
HF_HUB_CACHE="${HF_HUB_CACHE:-/tmp/forgemoe-hf-cache/hub}" \
FORGEMOE_STEP28_MODEL_ID="${FORGEMOE_STEP28_MODEL_ID:-Qwen/Qwen2.5-Coder-0.5B-Instruct}" \
"${VENV}/bin/python" scripts/dev/run_local_lora_sft_dry_run.py
echo

RESULT_DIR="results/local/local_lora_sft_dry_run_v0"

test -f "${RESULT_DIR}/dry_run_report.json"
test -f "${RESULT_DIR}/architecture_report.json"
test -f "${RESULT_DIR}/training_job_spec_sagemaker.json"

"${VENV}/bin/python" - <<'PY'
import json
from pathlib import Path

root = Path("results/local/local_lora_sft_dry_run_v0")

report = json.loads((root / "dry_run_report.json").read_text())
arch = json.loads((root / "architecture_report.json").read_text())
job = json.loads((root / "training_job_spec_sagemaker.json").read_text())

assert report["schema_version"] == "forgeagent.local_lora_sft_dry_run.v0", report
assert report["mode"] == "memory_safe_architecture_dry_run", report
assert report["model_id"] == "Qwen/Qwen2.5-Coder-0.5B-Instruct", report
assert report["full_weight_load_attempted"] is False, report
assert report["lora_attached"] is True, report
assert report["trains_model"] is False, report
assert report["parameter_counts"]["trainable_parameters"] > 0, report
assert len(report["target_modules"]) == 7, report
assert report["dataset"]["train_rows"] == 2, report
assert report["dataset"]["eval_rows"] == 1, report
assert report["dataset"]["all_rows"] == 3, report
assert report["tokenization"]["any_truncated"] is False, report
assert report["forward_pass"]["ran"] is True, report

assert arch["schema_version"] == "forgeagent.lora_architecture_report.v0", arch
assert arch["real_config_model_type"] == "qwen2", arch
assert arch["parameter_counts"]["trainable_parameters"] == report["parameter_counts"]["trainable_parameters"], arch

assert job["schema_version"] == "forgeagent.lora_training_job_spec.v0", job
assert job["hyperparameters"]["target_modules"] == report["target_modules"], job

print("memory_safe_local_lora_sft_dry_run: OK")
print("target_modules:", ",".join(report["target_modules"]))
print("trainable_parameters:", report["parameter_counts"]["trainable_parameters"])
print("trainable_percent:", report["parameter_counts"]["trainable_percent"])
print("train_rows:", report["dataset"]["train_rows"])
print("eval_rows:", report["dataset"]["eval_rows"])
print("any_truncated:", report["tokenization"]["any_truncated"])
print("forward_pass_ran:", report["forward_pass"]["ran"])
print("elapsed_seconds:", report["elapsed_seconds"])
PY

echo
echo "STEP28_DOCTOR_OK"

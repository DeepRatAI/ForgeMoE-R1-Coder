#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.0 doctor ==="
python3 --version
echo

echo "=== Compile launch plan builder ==="
python3 -m compileall -q scripts/dev/build_gpu_lora_sft_launch_plan.py
echo "compileall: OK"
echo

echo "=== Build GPU LoRA SFT launch plan ==="
PYTHONPATH=src python3 scripts/dev/build_gpu_lora_sft_launch_plan.py
echo

test -f reports/local/step29_0_gpu_training_preflight/launch_plan.json
test -f reports/local/step29_0_gpu_training_preflight/risk_register.json

python3 - <<'PY'
import json
from pathlib import Path

root = Path("reports/local/step29_0_gpu_training_preflight")
plan = json.loads((root / "launch_plan.json").read_text())
risk = json.loads((root / "risk_register.json").read_text())

assert plan["schema_version"] == "forgeagent.gpu_lora_sft_launch_plan.v0", plan
assert plan["launch_training_job"] is False, plan
assert plan["requires_explicit_approval_before_launch"] is True, plan
assert plan["reason_training_not_launched"] == "cost_gate_active", plan
assert plan["model"]["base_model_id"] == "Qwen/Qwen2.5-Coder-0.5B-Instruct", plan
assert len(plan["model"]["target_modules"]) == 7, plan
assert plan["dataset"]["train_rows"] == 2, plan
assert plan["dataset"]["eval_rows"] == 1, plan
assert plan["aws"]["sagemaker_api_probe_ok"] is True, plan

assert risk["schema_version"] == "forgeagent.gpu_training_risk_register.v0", risk
assert len(risk["risks"]) >= 4, risk

print("launch_plan: OK")
print("training_launch_blocked_by_cost_gate:", not plan["launch_training_job"])
print("requires_explicit_approval_before_launch:", plan["requires_explicit_approval_before_launch"])
print("model:", plan["model"]["base_model_id"])
print("target_modules:", ",".join(plan["model"]["target_modules"]))
print("train_rows:", plan["dataset"]["train_rows"])
print("eval_rows:", plan["dataset"]["eval_rows"])
print("sagemaker_api_probe_ok:", plan["aws"]["sagemaker_api_probe_ok"])
PY

echo
echo "STEP29_0_DOCTOR_OK"

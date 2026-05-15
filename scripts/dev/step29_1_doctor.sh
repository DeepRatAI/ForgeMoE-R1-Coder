#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.1 doctor ==="
python3 --version
echo

echo "=== Compile registry and launch-plan builders ==="
python3 -m compileall -q \
  scripts/dev/build_manifest_run_registry.py \
  scripts/dev/build_gpu_lora_sft_launch_plan.py
echo "compileall: OK"
echo

echo "=== Validate Step 29.0 launch plan ==="
test -f reports/local/step29_0_gpu_training_preflight/launch_plan.json
test -f reports/local/step29_0_gpu_training_preflight/risk_register.json

python3 - <<'PY'
import json
from pathlib import Path

plan = json.loads(Path("reports/local/step29_0_gpu_training_preflight/launch_plan.json").read_text())

assert plan["schema_version"] == "forgeagent.gpu_lora_sft_launch_plan.v0", plan
assert plan["launch_training_job"] is False, plan
assert plan["requires_explicit_approval_before_launch"] is True, plan
assert plan["aws"]["sagemaker_api_probe_ok"] is True, plan

print("step29_0_launch_plan: OK")
print("launch_training_job:", plan["launch_training_job"])
print("requires_explicit_approval_before_launch:", plan["requires_explicit_approval_before_launch"])
PY

echo

echo "=== Rebuild manifest-derived registry ==="
python3 scripts/dev/build_manifest_run_registry.py
echo

test -f reports/local/run_registry.json
test -f reports/local/run_registry.md

python3 - <<'PY'
import json
from pathlib import Path

registry = json.loads(Path("reports/local/run_registry.json").read_text())

assert registry["project"] == "ForgeMoE-R1-Agent-Coder", registry
assert registry["registry_version"] == "manifest_derived_v1", registry
assert registry["entry_count"] >= 28, registry

stages = {entry["stage"]: entry for entry in registry["entries"]}
assert "step29_0_gpu_training_preflight_v0" in stages, registry
assert "step28_1_registry_docs_refresh_v0" in stages, registry
assert "step28_memory_safe_local_lora_sft_dry_run_v0" in stages, registry

step29 = stages["step29_0_gpu_training_preflight_v0"]
assert step29["result"] == "STEP29_0_DOCTOR_OK", step29
assert step29["gpu_required"] is False, step29
assert step29["h100_purchase_required"] is False, step29
assert step29["local_test"]["launch_training_job"] is False, step29
assert step29["local_test"]["requires_explicit_approval_before_launch"] is True, step29

print("manifest_registry: OK")
print("entry_count:", registry["entry_count"])
print("contains_step29_0:", True)
print("step29_0_result:", step29["result"])
print("step29_0_cost_gate:", step29["local_test"]["requires_explicit_approval_before_launch"])
PY

echo

grep -q "Step 29.1 Registry Refresh" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.1 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md

echo "docs: OK"
echo
echo "STEP29_1_DOCTOR_OK"

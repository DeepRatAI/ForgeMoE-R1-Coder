#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 28.1 doctor ==="
python3 --version
echo

echo "=== Compile registry builder ==="
python3 -m compileall -q scripts/dev/build_manifest_run_registry.py
echo "compileall: OK"
echo

echo "=== Validate manifest cache ==="
test -d reports/local/manifest_cache
find reports/local/manifest_cache -name "*manifest.json" | wc -l
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
assert registry["entry_count"] >= 20, registry
assert any(entry["stage"] == "step28_memory_safe_local_lora_sft_dry_run_v0" for entry in registry["entries"]), registry
assert any(entry["stage"] == "step27_local_adapter_training_plan_v0" for entry in registry["entries"]), registry
assert any(entry["stage"] == "step20_qwen_code_model_baseline_v0" for entry in registry["entries"]), registry

step28 = [entry for entry in registry["entries"] if entry["stage"] == "step28_memory_safe_local_lora_sft_dry_run_v0"][0]

assert step28["result"] == "STEP28_DOCTOR_OK", step28
assert step28["gpu_required"] is False, step28
assert step28["h100_purchase_required"] is False, step28

print("manifest_registry: OK")
print("entry_count:", registry["entry_count"])
print("contains_step28:", True)
print("step28_result:", step28["result"])
print("step28_gpu_required:", step28["gpu_required"])
PY

echo

test -f docs/engineering/ADR_0027_CLOUDSHELL_CONTROL_PLANE_NOT_COMPUTE_PLANE.md
grep -q "CloudShell Is Control Plane" docs/engineering/ADR_0027_CLOUDSHELL_CONTROL_PLANE_NOT_COMPUTE_PLANE.md
grep -q "Step 28.1 Manifest-Derived Registry" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 28.1 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md

echo "docs: OK"
echo
echo "STEP28_1_DOCTOR_OK"

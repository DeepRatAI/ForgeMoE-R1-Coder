#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.4 doctor ==="
python3 --version
echo

echo "=== Compile registry builder ==="
python3 -m compileall -q scripts/dev/build_manifest_run_registry.py
echo "compileall: OK"
echo

echo "=== Validate Step 29.2 and Step 29.3 local reports ==="
test -f results/local/structured_sft_dataset_expansion_v0/summary.json
test -f results/local/structured_sft_tokenization_refresh_v0/tokenization_report.json
test -f results/local/structured_sft_tokenization_refresh_v0/training_manifest.json

python3 - <<'PY'
import json
from pathlib import Path

dataset_summary = json.loads(Path("results/local/structured_sft_dataset_expansion_v0/summary.json").read_text())
token_report = json.loads(Path("results/local/structured_sft_tokenization_refresh_v0/tokenization_report.json").read_text())
training_manifest = json.loads(Path("results/local/structured_sft_tokenization_refresh_v0/training_manifest.json").read_text())

assert dataset_summary["total_rows"] == 48, dataset_summary
assert dataset_summary["train_rows"] == 40, dataset_summary
assert dataset_summary["eval_rows"] == 8, dataset_summary

assert token_report["model_id"] == "Qwen/Qwen2.5-Coder-0.5B-Instruct", token_report
assert token_report["all"]["row_count"] == 48, token_report
assert token_report["all"]["would_truncate_count"] == 0, token_report
assert token_report["full_weight_load_attempted"] is False, token_report

assert training_manifest["tokenization_gate"]["passed"] is True, training_manifest
assert training_manifest["cost_gate"]["requires_explicit_approval_before_launch"] is True, training_manifest

print("local_reports: OK")
print("total_rows:", dataset_summary["total_rows"])
print("max_tokens:", token_report["all"]["max_tokens"])
print("p95_tokens:", token_report["all"]["p95_tokens"])
print("would_truncate_count:", token_report["all"]["would_truncate_count"])
print("tokenization_gate_passed:", training_manifest["tokenization_gate"]["passed"])
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
assert registry["entry_count"] >= 30, registry

stages = {entry["stage"]: entry for entry in registry["entries"]}

assert "step29_2_structured_sft_dataset_expansion_v0" in stages, registry
assert "step29_3_structured_sft_tokenization_refresh_v0" in stages, registry

step29_2 = stages["step29_2_structured_sft_dataset_expansion_v0"]
step29_3 = stages["step29_3_structured_sft_tokenization_refresh_v0"]

assert step29_2["result"] == "STEP29_2_DOCTOR_OK", step29_2
assert step29_2["local_test"]["total_rows"] == 48, step29_2

assert step29_3["result"] == "STEP29_3_DOCTOR_OK", step29_3
assert step29_3["local_test"]["total_rows"] == 48, step29_3
assert step29_3["local_test"]["would_truncate_count"] == 0, step29_3
assert step29_3["local_test"]["tokenization_gate_passed"] is True, step29_3

print("manifest_registry: OK")
print("entry_count:", registry["entry_count"])
print("contains_step29_2:", True)
print("contains_step29_3:", True)
print("step29_3_result:", step29_3["result"])
print("step29_3_tokenization_gate_passed:", step29_3["local_test"]["tokenization_gate_passed"])
PY

echo

grep -q "Step 29.4 Registry Refresh" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.4 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md

echo "docs: OK"
echo
echo "STEP29_4_DOCTOR_OK"

#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.26 doctor ==="
python3 --version
echo

echo "=== Compile training data schema normalization scaleout plan ==="
python3 -m compileall -q scripts/dev/run_training_data_schema_normalization_scaleout_plan_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.25 source artifacts ==="
./scripts/dev/step29_25_doctor.sh
echo

echo "=== Enforce no local model, training, large dataset download, or remote inference execution for this gate ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|torchrun|deepspeed|accelerate launch|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_26_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_26_forbidden_runtime_processes.txt
  echo "forbidden model runtime, training, or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run training data schema normalization scaleout plan v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_training_data_schema_normalization_scaleout_plan_v1.py
echo

RESULT_DIR="results/local/training_data_schema_normalization_scaleout_plan_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/canonical_schema_registry.json"
test -f "${RESULT_DIR}/source_to_canonical_schema_map.json"
test -f "${RESULT_DIR}/row_schema_mapping.jsonl"
test -f "${RESULT_DIR}/normalized_scaffold_manifest.jsonl"
test -f "${RESULT_DIR}/schema_gap_report.json"
test -f "${RESULT_DIR}/generator_scaleout_plan.json"
test -f "${RESULT_DIR}/training_data_schema_normalization_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_training_data_schema_normalization_report.json"
test -f "${RESULT_DIR}/training_data_schema_normalization_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/training_data_schema_normalization_scaleout_plan_v1")
summary = json.loads((root / "summary.json").read_text())
registry = json.loads((root / "canonical_schema_registry.json").read_text())
schema_map = json.loads((root / "source_to_canonical_schema_map.json").read_text())
mappings = [json.loads(line) for line in (root / "row_schema_mapping.jsonl").read_text().splitlines()]
normalized = [json.loads(line) for line in (root / "normalized_scaffold_manifest.jsonl").read_text().splitlines()]
gap_report = json.loads((root / "schema_gap_report.json").read_text())
scaleout_plan = json.loads((root / "generator_scaleout_plan.json").read_text())
gate = json.loads((root / "training_data_schema_normalization_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_training_data_schema_normalization_report.json").read_text())
privacy = json.loads((root / "training_data_schema_normalization_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.training_data_schema_normalization_scaleout_plan_summary.v1", summary
assert summary["gate_name"] == "training_data_schema_normalization_scaleout_plan_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["source_row_count"] == 10, summary
assert summary["canonical_schema_count"] == 5, summary
assert summary["mapped_source_row_count"] == 10, summary
assert summary["unmapped_source_row_count"] == 0, summary
assert summary["all_current_schemas_mapped"] is True, summary
assert summary["normalized_scaffold_row_count"] == 6, summary
assert summary["training_grade_row_count"] == 0, summary
assert summary["scaleout_phase_count"] == 5, summary
assert summary["canonical_schema_registry_ready"] is True, summary
assert summary["generator_scaleout_plan_ready"] is True, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary

assert registry["schema_version"] == "forgeagent.training_data_canonical_schema_registry.v1", registry
assert registry["canonical_schema_count"] == 5, registry
assert registry["training_payloads_in_registry"] is False, registry
assert len(registry["canonical_schemas"]) == 5, registry
assert len(schema_map) == 8, schema_map
assert len(mappings) == 10, mappings
assert len(normalized) == 6, normalized
assert all(row["mapping_status"] == "mapped" for row in mappings), mappings
assert all(row["training_grade_admitted"] is False for row in mappings), mappings
assert all(row["contains_training_payload"] is False for row in normalized), normalized
assert all(row["training_grade_admitted"] is False for row in normalized), normalized

assert gap_report["all_current_schemas_mapped"] is True, gap_report
assert gap_report["training_grade_normalization_ready"] is False, gap_report
assert "training_grade_rows_absent" in gap_report["blocking_gaps"], gap_report
assert "contamination_scan_not_complete_for_all_rows" in gap_report["blocking_gaps"], gap_report

assert scaleout_plan["schema_version"] == "forgeagent.generator_scaleout_plan.v1", scaleout_plan
assert scaleout_plan["phase_count"] == 5, scaleout_plan
assert scaleout_plan["default_training_launch_allowed"] is False, scaleout_plan
assert scaleout_plan["default_remote_inference_invoked"] is False, scaleout_plan
assert scaleout_plan["default_local_model_execution_used"] is False, scaleout_plan
assert scaleout_plan["requires_explicit_approval_before_training"] is True, scaleout_plan

assert gate["all_current_schemas_mapped"] is True, gate
assert gate["canonical_schema_registry_ready"] is True, gate
assert gate["normalized_scaffold_manifest_ready"] is True, gate
assert gate["generator_scaleout_plan_ready"] is True, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert gate["training_launch_allowed"] is False, gate
assert "large_scale_generator_not_yet_executed" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_training_data_schema_normalization_report.v1", public_report
assert public_report["canonical_schema_count"] == 5, public_report
assert public_report["source_row_count"] == 10, public_report
assert public_report["mapped_source_row_count"] == 10, public_report
assert public_report["unmapped_source_row_count"] == 0, public_report
assert public_report["normalized_scaffold_row_count"] == 6, public_report
assert public_report["training_grade_row_count"] == 0, public_report
assert public_report["scaleout_phase_count"] == 5, public_report
assert public_report["training_launch_allowed"] is False, public_report
assert public_report["remote_inference_invoked"] is False, public_report
assert public_report["redaction_policy"]["raw_rows_included"] is False, public_report
assert public_report["redaction_policy"]["private_identifiers_included"] is False, public_report
assert public_report["redaction_policy"]["patch_content_included"] is False, public_report
assert public_report["redaction_policy"]["withheld_eval_content_included"] is False, public_report

public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "forge-micro-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob
assert "hidden_tests" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("training_data_schema_normalization_scaleout_plan_v1: OK")
print("source_row_count:", summary["source_row_count"])
print("canonical_schema_count:", summary["canonical_schema_count"])
print("mapped_source_row_count:", summary["mapped_source_row_count"])
print("normalized_scaffold_row_count:", summary["normalized_scaffold_row_count"])
print("training_grade_row_count:", summary["training_grade_row_count"])
print("scaleout_phase_count:", summary["scaleout_phase_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.26 Training Data Schema Normalization" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.26 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Training Data Schema Normalization" docs/data/TRAINING_DATA_SCHEMA_NORMALIZATION_AND_SCALEOUT_PLAN.md
grep -q "ADR-0052" docs/engineering/ADR_0052_TRAINING_DATA_SCHEMA_NORMALIZATION_SCALEOUT_PLAN.md

echo
echo "STEP29_26_DOCTOR_OK"

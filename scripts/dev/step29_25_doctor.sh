#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.25 doctor ==="
python3 --version
echo

echo "=== Compile training data governance scaleout gate ==="
python3 -m compileall -q scripts/dev/run_training_data_governance_scaleout_v1.py
echo "compileall: OK"
echo

echo "=== Refresh prerequisite source-matrix and private-heldout gates ==="
./scripts/dev/step29_5_doctor.sh
./scripts/dev/step29_6_doctor.sh
./scripts/dev/step29_7_doctor.sh
./scripts/dev/step29_24_doctor.sh
echo

echo "=== Enforce no local model, training, or remote inference execution for this gate ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|torchrun|deepspeed|accelerate launch|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_25_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_25_forbidden_runtime_processes.txt
  echo "forbidden model runtime, training, or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run training data governance scaleout gate v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_training_data_governance_scaleout_v1.py
echo

RESULT_DIR="results/local/training_data_governance_scaleout_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/dataset_export_inventory.json"
test -f "${RESULT_DIR}/row_admission_results.jsonl"
test -f "${RESULT_DIR}/admitted_scaffold_manifest.jsonl"
test -f "${RESULT_DIR}/rejected_rows.jsonl"
test -f "${RESULT_DIR}/split_integrity_report.json"
test -f "${RESULT_DIR}/license_provenance_report.json"
test -f "${RESULT_DIR}/contamination_report.json"
test -f "${RESULT_DIR}/public_safe_training_data_governance_report.json"
test -f "${RESULT_DIR}/training_data_governance_gate_decision.json"
test -f "${RESULT_DIR}/training_data_governance_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/training_data_governance_scaleout_v1")
summary = json.loads((root / "summary.json").read_text())
inventory = json.loads((root / "dataset_export_inventory.json").read_text())
admissions = [json.loads(line) for line in (root / "row_admission_results.jsonl").read_text().splitlines()]
scaffold = [json.loads(line) for line in (root / "admitted_scaffold_manifest.jsonl").read_text().splitlines()]
rejected = [json.loads(line) for line in (root / "rejected_rows.jsonl").read_text().splitlines()]
split_report = json.loads((root / "split_integrity_report.json").read_text())
license_report = json.loads((root / "license_provenance_report.json").read_text())
contamination_report = json.loads((root / "contamination_report.json").read_text())
public_report = json.loads((root / "public_safe_training_data_governance_report.json").read_text())
gate = json.loads((root / "training_data_governance_gate_decision.json").read_text())
privacy = json.loads((root / "training_data_governance_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.training_data_governance_scaleout_summary.v1", summary
assert summary["gate_name"] == "training_data_governance_scaleout_v1", summary
assert summary["source_matrix_ready"] is True, summary
assert summary["private_heldout_gate_ready"] is True, summary
assert summary["export_file_count"] == 10, summary
assert summary["raw_row_count"] == 10, summary
assert summary["train_split_row_count"] == 6, summary
assert summary["eval_split_row_count"] == 2, summary
assert summary["private_heldout_row_count"] == 2, summary
assert summary["scaffold_admitted_row_count"] == 6, summary
assert summary["training_grade_admitted_row_count"] == 0, summary
assert summary["private_identifier_present_row_count"] == 2, summary
assert summary["split_integrity_passed"] is True, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary

assert len(inventory) == summary["export_file_count"], inventory
assert len(admissions) == summary["raw_row_count"], admissions
assert len(scaffold) == summary["scaffold_admitted_row_count"], scaffold
assert len(rejected) == summary["raw_row_count"], rejected
assert all(row["split"] == "train" for row in scaffold), scaffold
assert all(not row["training_grade_admitted"] for row in admissions), admissions
assert all(row["split"] == "train" for row in admissions if row["scaffold_admitted"]), admissions
assert all(not row["scaffold_admitted"] for row in admissions if row["split"] != "train"), admissions

assert split_report["passed"] is True, split_report
assert split_report["private_rows_seen"] == 2, split_report
assert split_report["private_rows_admitted_to_scaffold"] == 0, split_report
assert split_report["private_rows_admitted_to_training_grade"] == 0, split_report
assert split_report["eval_rows_admitted_to_training_grade"] == 0, split_report
assert split_report["non_train_rows_admitted_to_training_grade"] == 0, split_report

assert license_report["passed_for_training_grade_release"] is False, license_report
assert contamination_report["passed_for_training_grade_release"] is False, contamination_report
assert contamination_report["private_identifier_present_count"] == 2, contamination_report

assert public_report["schema_version"] == "forgeagent.public_safe_training_data_governance_report.v1", public_report
assert public_report["raw_row_count"] == 10, public_report
assert public_report["training_grade_admitted_row_count"] == 0, public_report
assert public_report["private_rows_rejected_for_training"] == 2, public_report
assert public_report["eval_rows_rejected_for_training"] == 2, public_report
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

assert gate["training_grade_data_release_allowed"] is False, gate
assert gate["training_launch_allowed"] is False, gate
assert "training_grade_row_count_zero" in gate["blocked_reasons"], gate
assert "license_provenance_incomplete" in gate["blocked_reasons"], gate
assert "contamination_scan_incomplete" in gate["blocked_reasons"], gate

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["private_identifier_leak_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("training_data_governance_scaleout_v1: OK")
print("export_file_count:", summary["export_file_count"])
print("raw_row_count:", summary["raw_row_count"])
print("scaffold_admitted_row_count:", summary["scaffold_admitted_row_count"])
print("training_grade_admitted_row_count:", summary["training_grade_admitted_row_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.25 Training Data Governance Scaleout" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.25 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Training Data Governance Scaleout" docs/data/TRAINING_DATA_GOVERNANCE_SCALEOUT.md
grep -q "ADR-0051" docs/engineering/ADR_0051_TRAINING_DATA_GOVERNANCE_SCALEOUT.md

echo
echo "STEP29_25_DOCTOR_OK"

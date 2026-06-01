#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.27 doctor ==="
python3 --version
echo

echo "=== Compile provenance/license/contamination scanner ==="
python3 -m compileall -q scripts/dev/run_provenance_license_contamination_scanner_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.26 source artifacts ==="
./scripts/dev/step29_26_doctor.sh
echo

echo "=== Enforce no local model, training, large dataset download, or remote inference execution for this gate ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|torchrun|deepspeed|accelerate launch|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_27_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_27_forbidden_runtime_processes.txt
  echo "forbidden model runtime, training, or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run provenance/license/contamination scanner v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_provenance_license_contamination_scanner_v1.py
echo

RESULT_DIR="results/local/provenance_license_contamination_scanner_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/provenance_scan_results.jsonl"
test -f "${RESULT_DIR}/license_scan_results.jsonl"
test -f "${RESULT_DIR}/contamination_scan_results.jsonl"
test -f "${RESULT_DIR}/row_scanner_decisions.jsonl"
test -f "${RESULT_DIR}/fingerprint_index.json"
test -f "${RESULT_DIR}/scan_summary.json"
test -f "${RESULT_DIR}/provenance_license_contamination_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_provenance_license_contamination_report.json"
test -f "${RESULT_DIR}/provenance_license_contamination_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/provenance_license_contamination_scanner_v1")
summary = json.loads((root / "summary.json").read_text())
provenance = [json.loads(line) for line in (root / "provenance_scan_results.jsonl").read_text().splitlines()]
licenses = [json.loads(line) for line in (root / "license_scan_results.jsonl").read_text().splitlines()]
contamination = [json.loads(line) for line in (root / "contamination_scan_results.jsonl").read_text().splitlines()]
decisions = [json.loads(line) for line in (root / "row_scanner_decisions.jsonl").read_text().splitlines()]
fingerprints = json.loads((root / "fingerprint_index.json").read_text())
scan_summary = json.loads((root / "scan_summary.json").read_text())
gate = json.loads((root / "provenance_license_contamination_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_provenance_license_contamination_report.json").read_text())
privacy = json.loads((root / "provenance_license_contamination_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.provenance_license_contamination_scanner_summary.v1", summary
assert summary["gate_name"] == "provenance_license_contamination_scanner_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["source_row_count"] == 10, summary
assert summary["training_row_count"] == 6, summary
assert summary["eval_row_count"] == 2, summary
assert summary["private_heldout_row_count"] == 2, summary
assert summary["provenance_scanned_row_count"] == 10, summary
assert summary["license_scanned_row_count"] == 10, summary
assert summary["contamination_scanned_row_count"] == 10, summary
assert summary["training_grade_provenance_pass_count"] == 0, summary
assert summary["training_grade_license_pass_count"] == 0, summary
assert summary["train_private_identifier_overlap_count"] == 0, summary
assert summary["train_eval_identifier_overlap_count"] == 0, summary
assert summary["public_benchmark_scan_complete_count"] == 0, summary
assert summary["near_duplicate_scanner_complete"] is False, summary
assert summary["training_grade_pass_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary

assert len(provenance) == 10, provenance
assert len(licenses) == 10, licenses
assert len(contamination) == 10, contamination
assert len(decisions) == 10, decisions
assert all(row["training_grade_provenance_pass"] is False for row in provenance), provenance
assert all(row["training_grade_license_pass"] is False for row in licenses), licenses
assert all(row["training_grade_contamination_pass"] is False for row in contamination), contamination
assert all(row["training_grade_pass"] is False for row in decisions), decisions
assert all(not row["train_private_identifier_overlap"] for row in contamination), contamination
assert all(not row["train_eval_identifier_overlap"] for row in contamination), contamination
assert all(row["secret_finding_count"] == 0 for row in contamination), contamination

assert fingerprints["schema_version"] == "forgeagent.training_data_fingerprint_index.v1", fingerprints
assert fingerprints["contains_raw_text"] is False, fingerprints
assert fingerprints["contains_private_identifiers"] is False, fingerprints
assert fingerprints["same_task_multi_product_group_count"] >= 1, fingerprints

assert scan_summary["source_row_count"] == summary["source_row_count"], scan_summary
assert gate["provenance_scanner_ready"] is True, gate
assert gate["license_scanner_ready"] is True, gate
assert gate["contamination_scanner_ready"] is True, gate
assert gate["fingerprint_index_ready"] is True, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert "near_duplicate_scanner_incomplete" in gate["blocked_reasons"], gate
assert "public_benchmark_scan_incomplete" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_provenance_license_contamination_report.v1", public_report
assert public_report["source_row_count"] == 10, public_report
assert public_report["training_grade_pass_count"] == 0, public_report
assert public_report["private_identifier_values_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["prompt_content_included"] is False, public_report
assert public_report["withheld_eval_content_included"] is False, public_report
assert public_report["model_outputs_included"] is False, public_report
assert public_report["training_launch_allowed"] is False, public_report
assert public_report["remote_inference_invoked"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "forge-micro-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob
assert "hidden_tests" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["private_identifier_leak_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("provenance_license_contamination_scanner_v1: OK")
print("source_row_count:", summary["source_row_count"])
print("training_row_count:", summary["training_row_count"])
print("training_grade_pass_count:", summary["training_grade_pass_count"])
print("train_private_identifier_overlap_count:", summary["train_private_identifier_overlap_count"])
print("train_eval_identifier_overlap_count:", summary["train_eval_identifier_overlap_count"])
print("same_task_multi_product_group_count:", summary["same_task_multi_product_group_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.27 Provenance, License and Contamination Scanner" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.27 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Provenance, License and Contamination Scanner" docs/data/PROVENANCE_LICENSE_CONTAMINATION_SCANNER.md
grep -q "ADR-0053" docs/engineering/ADR_0053_PROVENANCE_LICENSE_CONTAMINATION_SCANNER.md

echo
echo "STEP29_27_DOCTOR_OK"

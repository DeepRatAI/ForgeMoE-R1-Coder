#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.15 doctor ==="
python3 --version
echo

echo "=== Compile candidate eval runner dry run ==="
python3 -m compileall -q scripts/dev/run_candidate_eval_runner_dry_run_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.14 model candidate eval contract artifacts ==="
./scripts/dev/step29_14_doctor.sh
echo

echo "=== Run candidate eval runner dry run v1 ==="
PYTHONPATH=src python3 scripts/dev/run_candidate_eval_runner_dry_run_v1.py
echo

RESULT_DIR="results/local/candidate_eval_runner_dry_run_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/candidate_packages/candidate_eval_runner_dry_run_reference.json"
test -f "${RESULT_DIR}/candidate_validation_result.json"
test -f "${RESULT_DIR}/candidate_eval_trace.json"
test -f "${RESULT_DIR}/public_safe_candidate_eval_report.json"
test -f "${RESULT_DIR}/candidate_eval_runner_gate_decision.json"
test -f "${RESULT_DIR}/runner_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/candidate_eval_runner_dry_run_v1")
summary = json.loads((root / "summary.json").read_text())
package = json.loads((root / "candidate_packages/candidate_eval_runner_dry_run_reference.json").read_text())
validation = json.loads((root / "candidate_validation_result.json").read_text())
trace = json.loads((root / "candidate_eval_trace.json").read_text())
public_report = json.loads((root / "public_safe_candidate_eval_report.json").read_text())
gate = json.loads((root / "candidate_eval_runner_gate_decision.json").read_text())
privacy = json.loads((root / "runner_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.candidate_eval_runner_dry_run_summary.v1", summary
assert summary["runner_name"] == "candidate_eval_runner_dry_run_v1", summary
assert summary["candidate_contract_ready"] is True, summary
assert summary["heldout_protocol_ready"] is True, summary
assert summary["candidate_package_count"] == 1, summary
assert summary["candidate_package_valid_count"] == 1, summary
assert summary["release_gate_passed_count"] == 0, summary
assert summary["dry_run_candidate_release_blocked"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["public_safe_private_task_id_leak_count"] == 0, summary
assert summary["public_safe_private_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_16_remote_candidate_smoke_preflight", summary

assert package["candidate_identity"]["candidate_id"] == "candidate-eval-runner-dry-run-reference", package
assert package["candidate_identity"]["is_real_model_candidate"] is False, package
assert package["privacy_attestation"]["private_heldout_used_for_training"] is False, package
assert package["privacy_attestation"]["private_heldout_used_for_prompt_iteration"] is False, package
assert package["eval_scope"]["private_heldout_aggregate_only"] is True, package
assert package["eval_scope"]["private_heldout_task_ids_exposed"] is False, package
assert package["aggregate_metrics"]["parse_validity_rate"] == 1.0, package
assert package["aggregate_metrics"]["public_overfit_detection_rate"] == 1.0, package

assert validation["contract_valid"] is True, validation
assert validation["release_gate_passed"] is False, validation
assert validation["training_launch_allowed"] is False, validation
assert validation["model_release_allowed"] is False, validation
assert "fixture_candidate_not_release_eligible" in validation["warnings"], validation

assert len(trace["events"]) >= 5, trace
assert trace["events"][-1]["type"] == "gate_decision", trace

assert public_report["contract_valid"] is True, public_report
assert public_report["release_gate_passed"] is False, public_report
assert public_report["redaction_policy"]["private_task_ids_included"] is False, public_report
assert public_report["redaction_policy"]["private_patch_content_included"] is False, public_report
assert public_report["redaction_policy"]["private_hidden_test_content_included"] is False, public_report

public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob

assert gate["candidate_package_valid"] is True, gate
assert gate["release_gate_passed"] is False, gate
assert gate["training_launch_allowed"] is False, gate
assert gate["model_release_allowed"] is False, gate

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_safe_private_task_id_leak_count"] == 0, privacy
assert privacy["public_safe_private_content_leak_count"] == 0, privacy

print("candidate_eval_runner_dry_run_v1: OK")
print("candidate_package_count:", summary["candidate_package_count"])
print("candidate_package_valid_count:", summary["candidate_package_valid_count"])
print("release_gate_passed_count:", summary["release_gate_passed_count"])
print("dry_run_candidate_release_blocked:", summary["dry_run_candidate_release_blocked"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_15_DOCTOR_OK"

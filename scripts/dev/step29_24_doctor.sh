#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.24 doctor ==="
python3 --version
echo

echo "=== Compile private heldout aggregate candidate eval gate ==="
python3 -m compileall -q scripts/dev/run_private_heldout_aggregate_candidate_eval_gate_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.23 public eval remote batch execution artifacts ==="
./scripts/dev/step29_23_doctor.sh
echo

echo "=== Enforce no local model or remote inference execution for this gate ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_24_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_24_forbidden_runtime_processes.txt
  echo "forbidden model runtime or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run private heldout aggregate candidate eval gate v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_private_heldout_aggregate_candidate_eval_gate_v1.py
echo

RESULT_DIR="results/local/private_heldout_aggregate_candidate_eval_gate_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/private_heldout_aggregate_evidence_requirement.json"
test -f "${RESULT_DIR}/private_heldout_aggregate_evidence_observed.json"
test -f "${RESULT_DIR}/private_heldout_aggregate_evidence_validation.json"
test -f "${RESULT_DIR}/candidate_packages/private_heldout_aggregate_candidate.json"
test -f "${RESULT_DIR}/candidate_validation_result.json"
test -f "${RESULT_DIR}/private_heldout_aggregate_candidate_eval_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_private_heldout_aggregate_candidate_eval_report.json"
test -f "${RESULT_DIR}/private_heldout_aggregate_candidate_eval_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/private_heldout_aggregate_candidate_eval_gate_v1")
summary = json.loads((root / "summary.json").read_text())
requirement = json.loads((root / "private_heldout_aggregate_evidence_requirement.json").read_text())
observed = json.loads((root / "private_heldout_aggregate_evidence_observed.json").read_text())
evidence_validation = json.loads((root / "private_heldout_aggregate_evidence_validation.json").read_text())
package = json.loads((root / "candidate_packages/private_heldout_aggregate_candidate.json").read_text())
candidate_validation = json.loads((root / "candidate_validation_result.json").read_text())
gate = json.loads((root / "private_heldout_aggregate_candidate_eval_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_private_heldout_aggregate_candidate_eval_report.json").read_text())
privacy = json.loads((root / "private_heldout_aggregate_candidate_eval_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.private_heldout_aggregate_candidate_eval_gate_summary.v1", summary
assert summary["gate_name"] == "private_heldout_aggregate_candidate_eval_gate_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["heldout_protocol_ready"] is True, summary
assert summary["private_isolation_passed"] is True, summary
assert summary["candidate_id"] == "public-eval-remote-batch-execution-v1", summary
assert len(summary["candidate_package_sha256"]) == 64, summary
assert len(summary["public_batch_request_sha256"]) == 64, summary
assert summary["public_eval_task_count"] == 6, summary
assert summary["private_heldout_task_count"] == 3, summary
assert summary["public_gate_ready"] is False, summary
assert summary["private_heldout_aggregate_evidence_present"] is False, summary
assert summary["private_heldout_aggregate_evidence_valid"] is False, summary
assert summary["aggregate_only_policy_passed"] is False, summary
assert summary["private_heldout_evaluated"] is False, summary
assert summary["private_heldout_pass_rate"] == 0.0, summary
assert summary["candidate_contract_valid_before_private_gate"] is False, summary
assert summary["candidate_contract_valid_after_private_gate"] is False, summary
assert summary["release_gate_passed"] is False, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["private_task_id_leak_count"] == 0, summary
assert summary["public_report_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary

assert requirement["required_candidate_id"] == summary["candidate_id"], requirement
assert requirement["required_candidate_package_sha256"] == summary["candidate_package_sha256"], requirement
assert requirement["required_public_batch_request_sha256"] == summary["public_batch_request_sha256"], requirement
assert requirement["aggregate_only_required"] is True, requirement
assert requirement["task_ids_allowed"] is False, requirement
assert requirement["task_level_results_allowed"] is False, requirement
assert requirement["patch_content_allowed"] is False, requirement
assert requirement["hidden_test_content_allowed"] is False, requirement
assert requirement["raw_model_outputs_allowed"] is False, requirement

assert observed["evidence_present"] is False, observed
assert evidence_validation["evidence_present"] is False, evidence_validation
assert evidence_validation["evidence_valid"] is False, evidence_validation
assert evidence_validation["failed_checks"] == ["evidence_present"], evidence_validation

assert package["eval_scope"]["private_heldout_aggregate_only"] is True, package
assert package["eval_scope"]["private_heldout_evaluated"] is False, package
assert package["eval_scope"]["private_heldout_task_ids_exposed"] is False, package
assert package["aggregate_metrics"]["private_heldout_pass_rate"] == 0.0, package
assert candidate_validation["contract_valid"] is False, candidate_validation
assert candidate_validation["release_gate_passed"] is False, candidate_validation

assert gate["public_gate_ready"] is False, gate
assert gate["private_heldout_aggregate_evidence_present"] is False, gate
assert gate["private_heldout_aggregate_evidence_valid"] is False, gate
assert gate["private_heldout_evaluated"] is False, gate
assert gate["release_gate_passed"] is False, gate
assert "public_eval_candidate_not_ready" in gate["blocked_reasons"], gate
assert "private_aggregate_evidence_missing_or_invalid" in gate["blocked_reasons"], gate
assert gate["remote_inference_invoked"] is False, gate
assert gate["local_model_execution_used"] is False, gate

assert public_report["private_heldout_task_count"] == 3, public_report
assert public_report["private_heldout_aggregate_evidence_present"] is False, public_report
assert public_report["release_gate_passed"] is False, public_report
assert public_report["redaction_policy"]["private_task_ids_included"] is False, public_report
assert public_report["redaction_policy"]["task_level_results_included"] is False, public_report
assert public_report["redaction_policy"]["patch_content_included"] is False, public_report
assert public_report["redaction_policy"]["hidden_test_content_included"] is False, public_report
assert public_report["redaction_policy"]["model_outputs_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob
assert "hidden_tests" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["private_task_id_leak_count"] == 0, privacy
assert privacy["public_report_content_leak_count"] == 0, privacy

print("private_heldout_aggregate_candidate_eval_gate_v1: OK")
print("candidate_id:", summary["candidate_id"])
print("private_heldout_task_count:", summary["private_heldout_task_count"])
print("private_heldout_aggregate_evidence_present:", summary["private_heldout_aggregate_evidence_present"])
print("release_gate_passed:", summary["release_gate_passed"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_24_DOCTOR_OK"

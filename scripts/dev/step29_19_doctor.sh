#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.19 doctor ==="
python3 --version
echo

echo "=== Compile remote inference execution candidate eval runner ==="
python3 -m compileall -q scripts/dev/run_remote_inference_execution_candidate_eval_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.18 remote inference cost approval gate artifacts ==="
./scripts/dev/step29_18_doctor.sh
echo

echo "=== Enforce no local model or unauthorized remote inference execution for this step ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_19_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_19_forbidden_runtime_processes.txt
  echo "forbidden model runtime or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run remote inference execution candidate eval v1 in fail-closed mode ==="
AWS_PROFILE="${AWS_PROFILE:-forgemoe}" AWS_REGION="${AWS_REGION:-us-west-2}" \
  FORGEMOE_EXECUTE_REMOTE_INFERENCE=0 \
  PYTHONPATH=src python3 scripts/dev/run_remote_inference_execution_candidate_eval_v1.py
echo

RESULT_DIR="results/local/remote_inference_execution_candidate_eval_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/approval_evidence_requirement.json"
test -f "${RESULT_DIR}/pricing_evidence_requirement.json"
test -f "${RESULT_DIR}/approval_record_observed.json"
test -f "${RESULT_DIR}/execution_authorization_check.json"
test -f "${RESULT_DIR}/remote_inference_invocation_plan.json"
test -f "${RESULT_DIR}/remote_inference_response_status.json"
test -f "${RESULT_DIR}/candidate_response_parse_result.json"
test -f "${RESULT_DIR}/patch_validation_result.json"
test -f "${RESULT_DIR}/candidate_packages/remote_inference_execution_candidate.json"
test -f "${RESULT_DIR}/candidate_validation_result.json"
test -f "${RESULT_DIR}/remote_inference_execution_candidate_eval_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_remote_inference_execution_candidate_eval_report.json"
test -f "${RESULT_DIR}/remote_inference_execution_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/remote_inference_execution_candidate_eval_v1")
summary = json.loads((root / "summary.json").read_text())
approval_req = json.loads((root / "approval_evidence_requirement.json").read_text())
pricing_req = json.loads((root / "pricing_evidence_requirement.json").read_text())
approval_observed = json.loads((root / "approval_record_observed.json").read_text())
auth = json.loads((root / "execution_authorization_check.json").read_text())
plan = json.loads((root / "remote_inference_invocation_plan.json").read_text())
response = json.loads((root / "remote_inference_response_status.json").read_text())
parse = json.loads((root / "candidate_response_parse_result.json").read_text())
patch = json.loads((root / "patch_validation_result.json").read_text())
package = json.loads((root / "candidate_packages/remote_inference_execution_candidate.json").read_text())
validation = json.loads((root / "candidate_validation_result.json").read_text())
gate = json.loads((root / "remote_inference_execution_candidate_eval_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_remote_inference_execution_candidate_eval_report.json").read_text())
privacy = json.loads((root / "remote_inference_execution_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.remote_inference_execution_candidate_eval_summary.v1", summary
assert summary["runner_name"] == "remote_inference_execution_candidate_eval_v1", summary
assert summary["step29_17_ready"] is True, summary
assert summary["step29_18_ready"] is True, summary
assert summary["request_hash_verified"] is True, summary
assert summary["pricing_evidence_present"] is False, summary
assert summary["execute_flag_set"] is False, summary
assert summary["approval_record_approved"] is False, summary
assert summary["execution_authorized"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["remote_response_present"] is False, summary
assert summary["patch_extracted"] is False, summary
assert summary["git_apply_check_passed"] is False, summary
assert summary["public_tests_passed"] is False, summary
assert summary["candidate_package_count"] == 1, summary
assert summary["candidate_package_valid_count"] == 0, summary
assert summary["release_gate_passed_count"] == 0, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["public_safe_private_task_id_leak_count"] == 0, summary
assert summary["public_safe_private_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary

assert approval_req["required"] is True, approval_req
assert approval_req["required_model_id"] == summary["selected_model_id"], approval_req
assert approval_req["required_request_sha256"] == summary["request_sha256"], approval_req
assert approval_observed["approved"] is False, approval_observed

assert pricing_req["required"] is True, pricing_req
assert pricing_req["required_model_id"] == summary["selected_model_id"], pricing_req
assert pricing_req["required_request_sha256"] == summary["request_sha256"], pricing_req

assert auth["execution_authorized"] is False, auth
assert auth["approval_source"].endswith("results/local/remote_inference_cost_approval_gate_v1/approval_record.json"), auth
assert "execute_flag_set" in auth["failed_checks"], auth
assert "approval_record_approved" in auth["failed_checks"], auth
assert "pricing_evidence_present" in auth["failed_checks"], auth

assert plan["execution_authorized"] is False, plan
assert plan["remote_inference_invoked"] is False, plan
assert plan["local_model_execution_used"] is False, plan
assert "bedrock-runtime" in plan["command"], plan
assert "converse" in plan["command"], plan

assert response["remote_inference_invoked"] is False, response
assert response["response_json_parse_ok"] is False, response
assert response["blocked_reason"] == "authorization_or_pricing_gate_failed", response

assert parse["response_text_present"] is False, parse
assert parse["patch_extracted"] is False, parse
assert parse["raw_response_in_public_report"] is False, parse
assert parse["patch_content_in_public_report"] is False, parse

assert patch["patch_present"] is False, patch
assert patch["git_apply_check_passed"] is False, patch
assert patch["git_apply_executed"] is False, patch
assert patch["public_tests_executed"] is False, patch
assert patch["public_tests_passed"] is False, patch

assert package["candidate_identity"]["is_real_model_candidate"] is False, package
assert package["eval_scope"]["remote_inference_executed"] is False, package
assert package["eval_scope"]["local_model_execution_used"] is False, package
assert package["privacy_attestation"]["private_heldout_used_for_training"] is False, package

assert validation["contract_valid"] is False, validation
assert validation["release_gate_passed"] is False, validation

assert gate["execution_authorized"] is False, gate
assert gate["remote_inference_invoked"] is False, gate
assert gate["remote_response_present"] is False, gate
assert gate["local_model_execution_used"] is False, gate
assert gate["training_launch_allowed"] is False, gate
assert gate["model_release_allowed"] is False, gate

assert public_report["execution_authorized"] is False, public_report
assert public_report["remote_inference_invoked"] is False, public_report
assert public_report["redaction_policy"]["raw_response_included"] is False, public_report
assert public_report["redaction_policy"]["patch_content_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_safe_private_task_id_leak_count"] == 0, privacy
assert privacy["public_safe_private_content_leak_count"] == 0, privacy

print("remote_inference_execution_candidate_eval_v1: OK")
print("selected_model_id:", summary["selected_model_id"])
print("request_sha256:", summary["request_sha256"])
print("execution_authorized:", summary["execution_authorized"])
print("remote_inference_invoked:", summary["remote_inference_invoked"])
print("candidate_package_valid_count:", summary["candidate_package_valid_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_19_DOCTOR_OK"

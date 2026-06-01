#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.23 doctor ==="
python3 --version
echo

echo "=== Compile public eval remote batch execution harness ==="
python3 -m compileall -q scripts/dev/run_public_eval_remote_batch_execution_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.22 public eval remote batch adapter artifacts ==="
./scripts/dev/step29_22_doctor.sh
echo

echo "=== Enforce no local model or remote inference execution before this fail-closed run ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_23_forbidden_runtime_processes_before.txt; then
  cat /tmp/forgemoe_step29_23_forbidden_runtime_processes_before.txt
  echo "forbidden model runtime or remote inference process detected before run"
  exit 1
fi
echo "forbidden_runtime_processes_before: none"
echo

echo "=== Run public eval remote batch execution v1 in fail-closed mode ==="
FORGEMOE_EXECUTE_PUBLIC_EVAL_REMOTE_BATCH=0 PYTHONPATH=src python3 scripts/dev/run_public_eval_remote_batch_execution_v1.py
echo

echo "=== Enforce no local model or remote inference execution after this fail-closed run ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_23_forbidden_runtime_processes_after.txt; then
  cat /tmp/forgemoe_step29_23_forbidden_runtime_processes_after.txt
  echo "forbidden model runtime or remote inference process detected after run"
  exit 1
fi
echo "forbidden_runtime_processes_after: none"
echo

RESULT_DIR="results/local/public_eval_remote_batch_execution_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/approval_evidence_requirement.json"
test -f "${RESULT_DIR}/pricing_evidence_requirement.json"
test -f "${RESULT_DIR}/approval_record_observed.json"
test -f "${RESULT_DIR}/execution_authorization_check.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_execution_runtime_plan.json"
test -f "${RESULT_DIR}/remote_response_statuses.jsonl"
test -f "${RESULT_DIR}/candidate_response_parse_results.jsonl"
test -f "${RESULT_DIR}/patch_validation_results.jsonl"
test -f "${RESULT_DIR}/candidate_packages/public_eval_remote_batch_execution_candidate.json"
test -f "${RESULT_DIR}/candidate_validation_result.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_execution_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_public_eval_remote_batch_execution_report.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_execution_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/public_eval_remote_batch_execution_v1")
summary = json.loads((root / "summary.json").read_text())
approval_req = json.loads((root / "approval_evidence_requirement.json").read_text())
pricing_req = json.loads((root / "pricing_evidence_requirement.json").read_text())
approval = json.loads((root / "approval_record_observed.json").read_text())
authorization = json.loads((root / "execution_authorization_check.json").read_text())
runtime_plan = json.loads((root / "public_eval_remote_batch_execution_runtime_plan.json").read_text())
response_rows = [json.loads(line) for line in (root / "remote_response_statuses.jsonl").read_text().splitlines() if line.strip()]
parse_rows = [json.loads(line) for line in (root / "candidate_response_parse_results.jsonl").read_text().splitlines() if line.strip()]
patch_rows = [json.loads(line) for line in (root / "patch_validation_results.jsonl").read_text().splitlines() if line.strip()]
package = json.loads((root / "candidate_packages/public_eval_remote_batch_execution_candidate.json").read_text())
validation = json.loads((root / "candidate_validation_result.json").read_text())
gate = json.loads((root / "public_eval_remote_batch_execution_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_public_eval_remote_batch_execution_report.json").read_text())
privacy = json.loads((root / "public_eval_remote_batch_execution_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.public_eval_remote_batch_execution_summary.v1", summary
assert summary["runner_name"] == "public_eval_remote_batch_execution_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["selected_model_id"] == "mistral.mistral-7b-instruct-v0:2", summary
assert summary["public_eval_task_count"] == 6, summary
assert summary["request_count"] == 6, summary
assert summary["request_hashes_verified"] is True, summary
assert summary["pricing_evidence_present"] is False, summary
assert summary["execute_flag_set"] is False, summary
assert summary["approval_record_approved"] is False, summary
assert summary["execution_authorized"] is False, summary
assert summary["remote_inference_invoked_count"] == 0, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["remote_response_present_count"] == 0, summary
assert summary["patch_extracted_count"] == 0, summary
assert summary["git_apply_check_passed_count"] == 0, summary
assert summary["public_tests_passed_count"] == 0, summary
assert summary["hidden_oracle_passed_count"] == 0, summary
assert summary["solved_task_count"] == 0, summary
assert summary["candidate_package_count"] == 1, summary
assert summary["candidate_package_valid_count"] == 0, summary
assert summary["release_gate_passed_count"] == 0, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["private_task_id_leak_count"] == 0, summary
assert summary["public_report_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary

assert approval_req["required_model_id"] == summary["selected_model_id"], approval_req
assert approval_req["required_batch_request_sha256"] == summary["batch_request_sha256"], approval_req
assert len(approval_req["required_request_sha256_values"]) == 6, approval_req
assert pricing_req["required_batch_request_sha256"] == summary["batch_request_sha256"], pricing_req
assert pricing_req["required_region"] == "us-west-2", pricing_req
assert approval["approved"] is False, approval
assert authorization["execution_authorized"] is False, authorization
assert authorization["remote_inference_invoked"] is False, authorization
assert authorization["local_model_execution_used"] is False, authorization
assert "execute_flag_set" in authorization["failed_checks"], authorization
assert "approval_record_approved" in authorization["failed_checks"], authorization
assert "pricing_evidence_present" in authorization["failed_checks"], authorization
assert runtime_plan["execution_authorized"] is False, runtime_plan
assert runtime_plan["remote_inference_invoked"] is False, runtime_plan

assert len(response_rows) == 6, response_rows
assert len(parse_rows) == 6, parse_rows
assert len(patch_rows) == 6, patch_rows
assert all(row["remote_inference_invoked"] is False for row in response_rows), response_rows
assert all(row["response_json_parse_ok"] is False for row in response_rows), response_rows
assert all(row["patch_extracted"] is False for row in parse_rows), parse_rows
assert all(row["patch_present"] is False for row in patch_rows), patch_rows
assert all(row["post_public_passed"] is False for row in patch_rows), patch_rows
assert all(row["post_hidden_passed"] is False for row in patch_rows), patch_rows

assert package["candidate_identity"]["is_real_model_candidate"] is False, package
assert package["model_metadata"]["runtime"] == "bedrock_on_demand", package
assert package["eval_scope"]["public_eval_task_count"] == 6, package
assert package["eval_scope"]["remote_inference_executed"] is False, package
assert package["eval_scope"]["local_model_execution_used"] is False, package
assert package["aggregate_metrics"]["raw_response_count"] == 0, package
assert package["aggregate_metrics"]["public_eval_solve_rate"] == 0.0, package
assert package["aggregate_metrics"]["private_heldout_pass_rate"] == 0.0, package
assert validation["contract_valid"] is False, validation
assert validation["release_gate_passed"] is False, validation

assert gate["source_step_ready"] is True, gate
assert gate["request_hashes_verified"] is True, gate
assert gate["execution_authorized"] is False, gate
assert gate["remote_inference_invoked_count"] == 0, gate
assert gate["remote_inference_invoked"] is False, gate
assert gate["local_model_execution_used"] is False, gate
assert gate["candidate_package_valid"] is False, gate
assert gate["release_gate_passed"] is False, gate

assert public_report["public_eval_task_count"] == 6, public_report
assert public_report["execution_authorized"] is False, public_report
assert public_report["remote_inference_invoked_count"] == 0, public_report
assert public_report["remote_inference_invoked"] is False, public_report
assert public_report["local_model_execution_used"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob
assert "def " not in public_blob, public_blob
assert "hidden_tests" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["private_task_id_leak_count"] == 0, privacy
assert privacy["public_report_content_leak_count"] == 0, privacy

print("public_eval_remote_batch_execution_v1: OK")
print("public_eval_task_count:", summary["public_eval_task_count"])
print("request_count:", summary["request_count"])
print("batch_request_sha256:", summary["batch_request_sha256"])
print("execution_authorized:", summary["execution_authorized"])
print("remote_inference_invoked_count:", summary["remote_inference_invoked_count"])
print("patch_extracted_count:", summary["patch_extracted_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_23_DOCTOR_OK"

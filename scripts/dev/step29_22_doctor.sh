#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.22 doctor ==="
python3 --version
echo

echo "=== Compile public eval remote batch adapter ==="
python3 -m compileall -q scripts/dev/run_public_eval_remote_batch_adapter_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.21 public eval candidate runner artifacts ==="
./scripts/dev/step29_21_doctor.sh
echo

echo "=== Enforce no local model or remote inference execution for this step ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_22_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_22_forbidden_runtime_processes.txt
  echo "forbidden model runtime or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run public eval remote batch adapter v1 ==="
PYTHONPATH=src python3 scripts/dev/run_public_eval_remote_batch_adapter_v1.py
echo

RESULT_DIR="results/local/public_eval_remote_batch_adapter_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/public_eval_batch_request_manifest.json"
test -f "${RESULT_DIR}/public_eval_batch_pretest_results.jsonl"
test -f "${RESULT_DIR}/public_eval_remote_batch_cost_policy.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_approval_record.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_pricing_evidence_requirement.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_authorization_check.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_execution_plan.json"
test -f "${RESULT_DIR}/candidate_packages/public_eval_remote_batch_prepared.json"
test -f "${RESULT_DIR}/candidate_validation_result.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_adapter_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_public_eval_remote_batch_adapter_report.json"
test -f "${RESULT_DIR}/public_eval_remote_batch_adapter_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/public_eval_remote_batch_adapter_v1")
summary = json.loads((root / "summary.json").read_text())
manifest = json.loads((root / "public_eval_batch_request_manifest.json").read_text())
pretests = [json.loads(line) for line in (root / "public_eval_batch_pretest_results.jsonl").read_text().splitlines() if line.strip()]
cost_policy = json.loads((root / "public_eval_remote_batch_cost_policy.json").read_text())
approval = json.loads((root / "public_eval_remote_batch_approval_record.json").read_text())
pricing_req = json.loads((root / "public_eval_remote_batch_pricing_evidence_requirement.json").read_text())
authorization = json.loads((root / "public_eval_remote_batch_authorization_check.json").read_text())
execution_plan = json.loads((root / "public_eval_remote_batch_execution_plan.json").read_text())
package = json.loads((root / "candidate_packages/public_eval_remote_batch_prepared.json").read_text())
validation = json.loads((root / "candidate_validation_result.json").read_text())
gate = json.loads((root / "public_eval_remote_batch_adapter_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_public_eval_remote_batch_adapter_report.json").read_text())
privacy = json.loads((root / "public_eval_remote_batch_adapter_privacy_report.json").read_text())
request_paths = sorted((root / "bedrock_converse_requests").glob("*.json"))
message_paths = sorted((root / "bedrock_converse_messages").glob("*.json"))

assert summary["schema_version"] == "forgeagent.public_eval_remote_batch_adapter_summary.v1", summary
assert summary["runner_name"] == "public_eval_remote_batch_adapter_v1", summary
assert summary["public_eval_suite_ready"] is True, summary
assert summary["public_eval_candidate_runner_ready"] is True, summary
assert summary["public_eval_task_count"] == 6, summary
assert summary["bedrock_converse_request_count"] == 6, summary
assert summary["all_public_pretests_failed"] is True, summary
assert summary["request_manifest_ready"] is True, summary
assert summary["cost_policy_ready"] is True, summary
assert summary["approval_record_present"] is True, summary
assert summary["approval_record_approved"] is False, summary
assert summary["pricing_evidence_present"] is False, summary
assert summary["execution_authorized"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["candidate_package_count"] == 1, summary
assert summary["candidate_package_valid_count"] == 0, summary
assert summary["release_gate_passed_count"] == 0, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["private_task_id_leak_count"] == 0, summary
assert summary["public_report_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary

assert len(request_paths) == 6, request_paths
assert len(message_paths) == 6, message_paths
assert len(pretests) == 6, pretests
assert all(row["passed"] is False for row in pretests), pretests

assert manifest["public_eval_task_count"] == 6, manifest
assert manifest["request_count"] == 6, manifest
assert len(manifest["request_hashes"]) == 6, manifest
assert len(set(manifest["request_hashes"])) == 6, manifest
assert manifest["batch_request_sha256"] == summary["batch_request_sha256"], manifest
assert manifest["estimated_total_token_ceiling"] == summary["estimated_total_token_ceiling"], manifest
assert manifest["remote_inference_invoked"] is False, manifest
assert manifest["local_model_execution_used"] is False, manifest

for path in request_paths:
    request = json.loads(path.read_text())
    assert request["modelId"] == summary["selected_model_id"], request
    assert request["requestMetadata"]["execution_mode"] == "prepared_not_invoked", request
    assert request["requestMetadata"]["forge_step"] == "step29_22_public_eval_remote_batch_adapter", request

assert cost_policy["pricing_quote_required"] is True, cost_policy
assert cost_policy["approval_required"] is True, cost_policy
assert cost_policy["execution_authorized"] is False, cost_policy
assert cost_policy["max_remote_inference_calls"] == 6, cost_policy
assert approval["approved"] is False, approval
assert approval["approved_max_remote_inference_calls"] == 0, approval
assert pricing_req["required"] is True, pricing_req
assert pricing_req["required_batch_request_sha256"] == summary["batch_request_sha256"], pricing_req
assert authorization["execution_authorized"] is False, authorization
assert authorization["remote_inference_invoked"] is False, authorization
assert authorization["local_model_execution_used"] is False, authorization
assert "approval_record_approved" in authorization["failed_checks"], authorization
assert execution_plan["request_count"] == 6, execution_plan
assert execution_plan["execution_authorized"] is False, execution_plan
assert execution_plan["remote_inference_invoked"] is False, execution_plan

assert package["candidate_identity"]["is_real_model_candidate"] is False, package
assert package["model_metadata"]["runtime"] == "bedrock_on_demand", package
assert package["eval_scope"]["public_eval_task_count"] == 6, package
assert package["eval_scope"]["remote_inference_executed"] is False, package
assert package["eval_scope"]["local_model_execution_used"] is False, package
assert package["privacy_attestation"]["private_heldout_used_for_training"] is False, package
assert package["cost_profile"]["remote_inference_invoked"] is False, package
assert package["cost_profile"]["local_model_execution_used"] is False, package
assert validation["contract_valid"] is False, validation
assert validation["release_gate_passed"] is False, validation

assert gate["public_eval_task_count"] == 6, gate
assert gate["all_public_pretests_failed"] is True, gate
assert gate["request_manifest_ready"] is True, gate
assert gate["execution_authorized"] is False, gate
assert gate["remote_inference_invoked"] is False, gate
assert gate["local_model_execution_used"] is False, gate
assert gate["training_launch_allowed"] is False, gate
assert gate["model_release_allowed"] is False, gate

assert public_report["public_eval_task_count"] == 6, public_report
assert public_report["bedrock_converse_request_count"] == 6, public_report
assert public_report["execution_authorized"] is False, public_report
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

print("public_eval_remote_batch_adapter_v1: OK")
print("public_eval_task_count:", summary["public_eval_task_count"])
print("bedrock_converse_request_count:", summary["bedrock_converse_request_count"])
print("all_public_pretests_failed:", summary["all_public_pretests_failed"])
print("batch_request_sha256:", summary["batch_request_sha256"])
print("execution_authorized:", summary["execution_authorized"])
print("remote_inference_invoked:", summary["remote_inference_invoked"])
print("local_model_execution_used:", summary["local_model_execution_used"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_22_DOCTOR_OK"

#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.17 doctor ==="
python3 --version
echo

echo "=== Compile remote code-model candidate smoke eval runner ==="
python3 -m compileall -q scripts/dev/run_remote_code_model_candidate_smoke_eval_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.16 remote candidate smoke preflight artifacts ==="
./scripts/dev/step29_16_doctor.sh
echo

echo "=== Enforce no local model or remote inference execution for this step ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_17_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_17_forbidden_runtime_processes.txt
  echo "forbidden model runtime or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run remote code-model candidate smoke eval v1 ==="
AWS_PROFILE="${AWS_PROFILE:-forgemoe}" AWS_REGION="${AWS_REGION:-us-west-2}" \
  PYTHONPATH=src python3 scripts/dev/run_remote_code_model_candidate_smoke_eval_v1.py
echo

RESULT_DIR="results/local/remote_code_model_candidate_smoke_eval_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/bedrock_converse_messages.json"
test -f "${RESULT_DIR}/bedrock_converse_request.json"
test -f "${RESULT_DIR}/bedrock_converse_command_plan.json"
test -f "${RESULT_DIR}/execution_authorization.json"
test -f "${RESULT_DIR}/public_smoke_pretest_result.json"
test -f "${RESULT_DIR}/candidate_packages/remote_code_model_candidate_smoke_eval_prepared.json"
test -f "${RESULT_DIR}/candidate_validation_result.json"
test -f "${RESULT_DIR}/remote_code_model_candidate_smoke_eval_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_remote_code_model_candidate_smoke_eval_report.json"
test -f "${RESULT_DIR}/remote_code_model_candidate_smoke_eval_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/remote_code_model_candidate_smoke_eval_v1")
summary = json.loads((root / "summary.json").read_text())
messages = json.loads((root / "bedrock_converse_messages.json").read_text())
request = json.loads((root / "bedrock_converse_request.json").read_text())
command = json.loads((root / "bedrock_converse_command_plan.json").read_text())
authorization = json.loads((root / "execution_authorization.json").read_text())
pretest = json.loads((root / "public_smoke_pretest_result.json").read_text())
package = json.loads((root / "candidate_packages/remote_code_model_candidate_smoke_eval_prepared.json").read_text())
validation = json.loads((root / "candidate_validation_result.json").read_text())
gate = json.loads((root / "remote_code_model_candidate_smoke_eval_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_remote_code_model_candidate_smoke_eval_report.json").read_text())
privacy = json.loads((root / "remote_code_model_candidate_smoke_eval_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.remote_code_model_candidate_smoke_eval_summary.v1", summary
assert summary["runner_name"] == "remote_code_model_candidate_smoke_eval_v1", summary
assert summary["candidate_contract_ready"] is True, summary
assert summary["heldout_protocol_ready"] is True, summary
assert summary["remote_preflight_ready"] is True, summary
assert summary["public_smoke_task_count"] == 1, summary
assert summary["public_smoke_pretest_failed_count"] == 1, summary
assert summary["bedrock_model_inventory_ok"] is True, summary
assert summary["bedrock_converse_request_ready"] is True, summary
assert summary["execution_authorized"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["candidate_package_count"] == 1, summary
assert summary["release_gate_passed_count"] == 0, summary
assert summary["remote_code_candidate_release_blocked"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["public_safe_private_task_id_leak_count"] == 0, summary
assert summary["public_safe_private_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_18_remote_inference_cost_approval_and_candidate_eval", summary

assert len(messages) == 2, messages
assert request["modelId"] == summary["selected_model_id"], request
assert request["messages"][0]["role"] == "user", request
assert request["inferenceConfig"]["maxTokens"] == 1024, request
assert request["requestMetadata"]["execution_mode"] == "prepared_not_invoked", request

assert command["status"] == "prepared_not_executed", command
assert command["requires_explicit_cost_approval"] is True, command
assert command["remote_inference_invoked"] is False, command
assert "converse" in command["command"], command

assert authorization["authorized"] is False, authorization
assert authorization["remote_inference_invoked"] is False, authorization
assert authorization["local_model_execution_allowed"] is False, authorization

assert pretest["passed"] is False, pretest
assert pretest["exit_code"] != 0, pretest

assert package["candidate_identity"]["candidate_kind"] == "remote_code_model_smoke_eval_prepared", package
assert package["candidate_identity"]["is_real_model_candidate"] is False, package
assert package["model_metadata"]["runtime"] == "bedrock_on_demand", package
assert package["eval_scope"]["private_heldout_aggregate_only"] is True, package
assert package["eval_scope"]["private_heldout_task_ids_exposed"] is False, package
assert package["eval_scope"]["private_heldout_evaluated"] is False, package
assert package["eval_scope"]["remote_inference_executed"] is False, package
assert package["eval_scope"]["local_model_execution_used"] is False, package
assert package["cost_profile"]["remote_inference_invoked"] is False, package
assert package["cost_profile"]["local_model_execution_used"] is False, package

assert validation["release_gate_passed"] is False, validation
assert validation["training_launch_allowed"] is False, validation
assert validation["model_release_allowed"] is False, validation
assert "fixture_candidate_not_release_eligible" in validation["warnings"], validation
assert any(item.startswith("release_threshold_failed:") for item in validation["errors"]), validation

assert gate["execution_authorized"] is False, gate
assert gate["remote_inference_invoked"] is False, gate
assert gate["local_model_execution_used"] is False, gate
assert gate["release_gate_passed"] is False, gate

assert public_report["remote_inference_invoked"] is False, public_report
assert public_report["local_model_execution_used"] is False, public_report
assert public_report["redaction_policy"]["prompt_content_included"] is False, public_report
assert public_report["redaction_policy"]["candidate_raw_outputs_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_safe_private_task_id_leak_count"] == 0, privacy
assert privacy["public_safe_private_content_leak_count"] == 0, privacy

print("remote_code_model_candidate_smoke_eval_v1: OK")
print("selected_model_id:", summary["selected_model_id"])
print("public_smoke_pretest_failed_count:", summary["public_smoke_pretest_failed_count"])
print("execution_authorized:", summary["execution_authorized"])
print("remote_inference_invoked:", summary["remote_inference_invoked"])
print("local_model_execution_used:", summary["local_model_execution_used"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_17_DOCTOR_OK"

#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.18 doctor ==="
python3 --version
echo

echo "=== Compile remote inference cost approval gate ==="
python3 -m compileall -q scripts/dev/run_remote_inference_cost_approval_gate_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.17 remote code-model candidate smoke eval artifacts ==="
./scripts/dev/step29_17_doctor.sh
echo

echo "=== Enforce no local model or remote inference execution for this step ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_18_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_18_forbidden_runtime_processes.txt
  echo "forbidden model runtime or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run remote inference cost approval gate v1 ==="
AWS_PROFILE="${AWS_PROFILE:-forgemoe}" AWS_REGION="${AWS_REGION:-us-west-2}" \
  PYTHONPATH=src python3 scripts/dev/run_remote_inference_cost_approval_gate_v1.py
echo

RESULT_DIR="results/local/remote_inference_cost_approval_gate_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/token_budget.json"
test -f "${RESULT_DIR}/cost_approval_policy.json"
test -f "${RESULT_DIR}/remote_inference_execution_plan.json"
test -f "${RESULT_DIR}/approval_record.json"
test -f "${RESULT_DIR}/remote_inference_cost_approval_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_remote_inference_cost_approval_report.json"
test -f "${RESULT_DIR}/remote_inference_cost_approval_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/remote_inference_cost_approval_gate_v1")
summary = json.loads((root / "summary.json").read_text())
token_budget = json.loads((root / "token_budget.json").read_text())
policy = json.loads((root / "cost_approval_policy.json").read_text())
plan = json.loads((root / "remote_inference_execution_plan.json").read_text())
approval = json.loads((root / "approval_record.json").read_text())
gate = json.loads((root / "remote_inference_cost_approval_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_remote_inference_cost_approval_report.json").read_text())
privacy = json.loads((root / "remote_inference_cost_approval_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.remote_inference_cost_approval_gate_summary.v1", summary
assert summary["gate_name"] == "remote_inference_cost_approval_gate_v1", summary
assert summary["step29_17_ready"] is True, summary
assert summary["request_ready"] is True, summary
assert summary["token_budget_ready"] is True, summary
assert summary["estimated_input_tokens"] > 0, summary
assert summary["max_output_tokens"] == 1024, summary
assert summary["estimated_total_token_ceiling"] == summary["estimated_input_tokens"] + 1024, summary
assert summary["cost_policy_ready"] is True, summary
assert summary["pricing_quote_required"] is True, summary
assert summary["approval_record_present"] is True, summary
assert summary["execution_authorized"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_response_present"] is False, summary
assert summary["candidate_eval_executed"] is False, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["public_safe_private_task_id_leak_count"] == 0, summary
assert summary["public_safe_private_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_19_remote_inference_execution_candidate_eval", summary

assert token_budget["schema_version"] == "forgeagent.remote_inference_token_budget.v1", token_budget
assert token_budget["estimated_input_tokens"] == summary["estimated_input_tokens"], token_budget
assert token_budget["max_output_tokens"] == summary["max_output_tokens"], token_budget

assert policy["approval_status"] == "not_approved", policy
assert policy["approved_by_user"] is False, policy
assert policy["max_remote_inference_calls"] == 1, policy
assert policy["pricing_quote_status"] == "required_before_execution", policy
assert "approval_status_is_not_approved" in policy["abort_conditions"], policy

assert plan["status"] == "blocked_until_user_cost_approval", plan
assert plan["request_sha256"] == summary["request_sha256"], plan
assert plan["remote_inference_invoked"] is False, plan
assert plan["local_model_execution_used"] is False, plan
assert "converse" in plan["command"], plan
assert "git_apply_check" in plan["post_execution_required_checks"], plan

assert approval["approved"] is False, approval
assert approval["approved_max_remote_inference_calls"] == 0, approval
assert approval["remote_inference_invoked"] is False, approval

assert gate["execution_authorized"] is False, gate
assert gate["remote_inference_invoked"] is False, gate
assert gate["local_model_execution_used"] is False, gate
assert gate["training_launch_allowed"] is False, gate
assert gate["model_release_allowed"] is False, gate

assert public_report["execution_authorized"] is False, public_report
assert public_report["remote_inference_invoked"] is False, public_report
assert public_report["local_model_execution_used"] is False, public_report
assert public_report["redaction_policy"]["request_prompt_included"] is False, public_report
assert public_report["redaction_policy"]["candidate_raw_outputs_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_safe_private_task_id_leak_count"] == 0, privacy
assert privacy["public_safe_private_content_leak_count"] == 0, privacy

print("remote_inference_cost_approval_gate_v1: OK")
print("selected_model_id:", summary["selected_model_id"])
print("estimated_input_tokens:", summary["estimated_input_tokens"])
print("max_output_tokens:", summary["max_output_tokens"])
print("execution_authorized:", summary["execution_authorized"])
print("remote_inference_invoked:", summary["remote_inference_invoked"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_18_DOCTOR_OK"

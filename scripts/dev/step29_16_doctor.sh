#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.16 doctor ==="
python3 --version
echo

echo "=== Compile remote candidate smoke preflight runner ==="
python3 -m compileall -q scripts/dev/run_remote_candidate_smoke_preflight_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.15 candidate eval runner dry run artifacts ==="
./scripts/dev/step29_15_doctor.sh
echo

echo "=== Enforce no local model execution for this step ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|api/generate" >/tmp/forgemoe_step29_16_local_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_16_local_runtime_processes.txt
  echo "local model runtime process detected"
  exit 1
fi
echo "local_model_runtime_processes: none"
echo

echo "=== Run remote candidate smoke preflight v1 ==="
AWS_PROFILE="${AWS_PROFILE:-forgemoe}" AWS_REGION="${AWS_REGION:-us-west-2}" \
  PYTHONPATH=src python3 scripts/dev/run_remote_candidate_smoke_preflight_v1.py
echo

RESULT_DIR="results/local/remote_candidate_smoke_preflight_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/cloud_preflight.json"
test -f "${RESULT_DIR}/remote_execution_plan.json"
test -f "${RESULT_DIR}/candidate_packages/remote_candidate_smoke_preflight.json"
test -f "${RESULT_DIR}/candidate_validation_result.json"
test -f "${RESULT_DIR}/public_safe_remote_candidate_smoke_preflight_report.json"
test -f "${RESULT_DIR}/remote_candidate_smoke_preflight_gate_decision.json"
test -f "${RESULT_DIR}/remote_candidate_smoke_preflight_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/remote_candidate_smoke_preflight_v1")
summary = json.loads((root / "summary.json").read_text())
cloud = json.loads((root / "cloud_preflight.json").read_text())
plan = json.loads((root / "remote_execution_plan.json").read_text())
package = json.loads((root / "candidate_packages/remote_candidate_smoke_preflight.json").read_text())
validation = json.loads((root / "candidate_validation_result.json").read_text())
public_report = json.loads((root / "public_safe_remote_candidate_smoke_preflight_report.json").read_text())
gate = json.loads((root / "remote_candidate_smoke_preflight_gate_decision.json").read_text())
privacy = json.loads((root / "remote_candidate_smoke_preflight_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.remote_candidate_smoke_preflight_summary.v1", summary
assert summary["runner_name"] == "remote_candidate_smoke_preflight_v1", summary
assert summary["candidate_contract_ready"] is True, summary
assert summary["heldout_protocol_ready"] is True, summary
assert summary["aws_preflight_ready"] is True, summary
assert summary["sts_ok"] is True, summary
assert summary["s3_bucket_access_ok"] is True, summary
assert summary["bedrock_text_model_count"] > 0, summary
assert summary["candidate_package_count"] == 1, summary
assert summary["real_model_candidate_evaluated"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["release_gate_passed_count"] == 0, summary
assert summary["remote_candidate_release_blocked"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["public_safe_private_task_id_leak_count"] == 0, summary
assert summary["public_safe_private_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_17_remote_code_model_candidate_smoke_eval", summary

assert cloud["schema_version"] == "forgeagent.remote_candidate_smoke_cloud_preflight.v1", cloud
assert cloud["sts_ok"] is True, cloud
assert cloud["s3_bucket_access_ok"] is True, cloud
assert cloud["bedrock_list_foundation_models_ok"] is True, cloud
assert cloud["remote_inference_invoked"] is False, cloud
assert cloud["local_model_execution_used"] is False, cloud

assert plan["schema_version"] == "forgeagent.remote_candidate_smoke_execution_plan.v1", plan
assert plan["status"] == "blocked_until_explicit_remote_inference_approval", plan
assert "ollama_local" in plan["disallowed_execution_surfaces"], plan
assert "local_transformers" in plan["disallowed_execution_surfaces"], plan

assert package["candidate_identity"]["candidate_kind"] == "remote_runtime_preflight", package
assert package["candidate_identity"]["is_real_model_candidate"] is False, package
assert package["model_metadata"]["runtime"] == "bedrock_on_demand", package
assert package["privacy_attestation"]["private_heldout_used_for_training"] is False, package
assert package["privacy_attestation"]["private_heldout_used_for_prompt_iteration"] is False, package
assert package["eval_scope"]["private_heldout_aggregate_only"] is True, package
assert package["eval_scope"]["private_heldout_task_ids_exposed"] is False, package
assert package["eval_scope"]["private_heldout_evaluated"] is False, package
assert package["eval_scope"]["remote_inference_executed"] is False, package
assert package["cost_profile"]["local_model_execution_used"] is False, package
assert package["cost_profile"]["remote_inference_invoked"] is False, package

assert validation["release_gate_passed"] is False, validation
assert validation["training_launch_allowed"] is False, validation
assert validation["model_release_allowed"] is False, validation
assert "fixture_candidate_not_release_eligible" in validation["warnings"], validation
assert any(
    item.startswith("release_threshold_failed:") for item in validation["errors"]
), validation

assert public_report["remote_inference_invoked"] is False, public_report
assert public_report["local_model_execution_used"] is False, public_report
assert public_report["release_gate_passed"] is False, public_report
assert public_report["redaction_policy"]["aws_account_id_included"] is False, public_report
assert public_report["redaction_policy"]["private_task_ids_included"] is False, public_report
assert public_report["redaction_policy"]["private_patch_content_included"] is False, public_report
assert public_report["redaction_policy"]["private_hidden_test_content_included"] is False, public_report
assert public_report["redaction_policy"]["candidate_raw_outputs_included"] is False, public_report

public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob

assert gate["aws_preflight_ready"] is True, gate
assert gate["remote_inference_invoked"] is False, gate
assert gate["local_model_execution_used"] is False, gate
assert gate["release_gate_passed"] is False, gate
assert gate["training_launch_allowed"] is False, gate
assert gate["model_release_allowed"] is False, gate

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_safe_private_task_id_leak_count"] == 0, privacy
assert privacy["public_safe_private_content_leak_count"] == 0, privacy

print("remote_candidate_smoke_preflight_v1: OK")
print("aws_preflight_ready:", summary["aws_preflight_ready"])
print("sagemaker_endpoint_count:", summary["sagemaker_endpoint_count"])
print("bedrock_text_model_count:", summary["bedrock_text_model_count"])
print("remote_inference_invoked:", summary["remote_inference_invoked"])
print("local_model_execution_used:", summary["local_model_execution_used"])
print("release_gate_passed_count:", summary["release_gate_passed_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_16_DOCTOR_OK"

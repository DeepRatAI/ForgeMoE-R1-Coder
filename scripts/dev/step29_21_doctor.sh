#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.21 doctor ==="
python3 --version
echo

echo "=== Compile public eval candidate runner scaleout ==="
python3 -m compileall -q scripts/dev/run_public_eval_candidate_runner_scaleout_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.20 public eval suite scaleout artifacts ==="
./scripts/dev/step29_20_doctor.sh
echo

echo "=== Enforce no local model or remote inference execution for this step ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_21_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_21_forbidden_runtime_processes.txt
  echo "forbidden model runtime or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run public eval candidate runner scaleout v1 ==="
PYTHONPATH=src python3 scripts/dev/run_public_eval_candidate_runner_scaleout_v1.py
echo

RESULT_DIR="results/local/public_eval_candidate_runner_scaleout_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/reference_candidate_scorecards.jsonl"
test -f "${RESULT_DIR}/candidate_validation_results.jsonl"
test -f "${RESULT_DIR}/candidate_packages/public-eval-reference-golden.json"
test -f "${RESULT_DIR}/candidate_packages/public-eval-reference-rejected.json"
test -f "${RESULT_DIR}/candidate_packages/public-eval-reference-public-overfit.json"
test -f "${RESULT_DIR}/public_eval_candidate_runner_trace.json"
test -f "${RESULT_DIR}/public_eval_candidate_runner_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_public_eval_candidate_runner_report.json"
test -f "${RESULT_DIR}/public_eval_candidate_runner_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/public_eval_candidate_runner_scaleout_v1")
summary = json.loads((root / "summary.json").read_text())
scorecards = [json.loads(line) for line in (root / "reference_candidate_scorecards.jsonl").read_text().splitlines() if line.strip()]
validations = [json.loads(line) for line in (root / "candidate_validation_results.jsonl").read_text().splitlines() if line.strip()]
golden_pkg = json.loads((root / "candidate_packages/public-eval-reference-golden.json").read_text())
rejected_pkg = json.loads((root / "candidate_packages/public-eval-reference-rejected.json").read_text())
overfit_pkg = json.loads((root / "candidate_packages/public-eval-reference-public-overfit.json").read_text())
trace = json.loads((root / "public_eval_candidate_runner_trace.json").read_text())
gate = json.loads((root / "public_eval_candidate_runner_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_public_eval_candidate_runner_report.json").read_text())
privacy = json.loads((root / "public_eval_candidate_runner_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.public_eval_candidate_runner_scaleout_summary.v1", summary
assert summary["runner_name"] == "public_eval_candidate_runner_scaleout_v1", summary
assert summary["public_eval_suite_ready"] is True, summary
assert summary["public_eval_task_count"] == 6, summary
assert summary["reference_candidate_count"] == 3, summary
assert summary["golden_reference_public_eval_gate_passed"] is True, summary
assert summary["golden_reference_public_eval_solve_rate"] == 1.0, summary
assert summary["golden_reference_hidden_oracle_pass_rate"] == 1.0, summary
assert summary["rejected_reference_failed"] is True, summary
assert 0.0 <= summary["rejected_reference_public_eval_solve_rate"] < 1.0, summary
assert 0.0 <= summary["rejected_reference_hidden_oracle_pass_rate"] < 1.0, summary
assert summary["rejected_reference_regression_free_patch_rate"] == 0.0, summary
assert summary["public_overfit_reference_detected"] is True, summary
assert summary["public_overfit_reference_public_eval_solve_rate"] == 1.0, summary
assert summary["public_overfit_reference_hidden_oracle_pass_rate"] == 0.0, summary
assert summary["model_candidate_contract_valid_count"] == 0, summary
assert summary["release_gate_passed_count"] == 0, summary
assert summary["candidate_eval_runner_ready"] is True, summary
assert summary["real_model_candidate_evaluated"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["public_safe_private_task_id_leak_count"] == 0, summary
assert summary["public_safe_patch_or_test_content_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary

assert len(scorecards) == 3, scorecards
by_id = {row["candidate_id"]: row for row in scorecards}
assert by_id["public-eval-reference-golden"]["public_eval_gate_passed"] is True, by_id
assert by_id["public-eval-reference-golden"]["hidden_oracle_pass_rate"] == 1.0, by_id
assert by_id["public-eval-reference-rejected"]["rejected_gate_failed"] is True, by_id
assert by_id["public-eval-reference-rejected"]["regression_free_patch_rate"] == 0.0, by_id
assert by_id["public-eval-reference-rejected"]["hidden_oracle_pass_rate"] < 1.0, by_id
assert by_id["public-eval-reference-public-overfit"]["public_overfit_gate_failed"] is True, by_id
assert by_id["public-eval-reference-public-overfit"]["public_overfit_detected_task_count"] == 6, by_id

assert len(validations) == 3, validations
for row in validations:
    assert row["contract_valid"] is False, row
    assert row["release_gate_passed"] is False, row
    assert row["training_launch_allowed"] is False, row
    assert row["model_release_allowed"] is False, row

for package in [golden_pkg, rejected_pkg, overfit_pkg]:
    assert package["candidate_identity"]["is_real_model_candidate"] is False, package
    assert package["eval_scope"]["private_heldout_aggregate_only"] is True, package
    assert package["eval_scope"]["private_heldout_task_ids_exposed"] is False, package
    assert package["eval_scope"]["remote_inference_executed"] is False, package
    assert package["eval_scope"]["local_model_execution_used"] is False, package
    assert package["privacy_attestation"]["private_heldout_used_for_training"] is False, package
    assert package["privacy_attestation"]["private_heldout_used_for_prompt_iteration"] is False, package
    assert package["cost_profile"]["remote_inference_invoked"] is False, package
    assert package["cost_profile"]["local_model_execution_used"] is False, package

assert golden_pkg["aggregate_metrics"]["public_eval_solve_rate"] == 1.0, golden_pkg
assert golden_pkg["aggregate_metrics"]["private_heldout_pass_rate"] == 0.0, golden_pkg
assert 0.0 <= rejected_pkg["aggregate_metrics"]["public_eval_solve_rate"] < 1.0, rejected_pkg
assert rejected_pkg["aggregate_metrics"]["regression_free_patch_rate"] == 0.0, rejected_pkg
assert overfit_pkg["aggregate_metrics"]["public_eval_solve_rate"] == 1.0, overfit_pkg
assert overfit_pkg["aggregate_metrics"]["regression_free_patch_rate"] == 0.0, overfit_pkg

assert trace["events"][0]["type"] == "load_public_eval_suite", trace
assert gate["candidate_eval_runner_ready"] is True, gate
assert gate["golden_reference_public_eval_gate_passed"] is True, gate
assert gate["public_overfit_reference_detected"] is True, gate
assert gate["model_candidate_contract_valid_count"] == 0, gate
assert gate["release_gate_passed_count"] == 0, gate

assert public_report["reference_candidate_count"] == 3, public_report
assert public_report["public_eval_gate_passed_candidate_count"] == 1, public_report
assert public_report["public_overfit_candidate_detected_count"] == 1, public_report
assert public_report["release_gate_passed_count"] == 0, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob
assert "def " not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_safe_private_task_id_leak_count"] == 0, privacy
assert privacy["public_safe_patch_or_test_content_leak_count"] == 0, privacy

print("public_eval_candidate_runner_scaleout_v1: OK")
print("public_eval_task_count:", summary["public_eval_task_count"])
print("reference_candidate_count:", summary["reference_candidate_count"])
print("golden_reference_public_eval_gate_passed:", summary["golden_reference_public_eval_gate_passed"])
print("public_overfit_reference_detected:", summary["public_overfit_reference_detected"])
print("release_gate_passed_count:", summary["release_gate_passed_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_21_DOCTOR_OK"

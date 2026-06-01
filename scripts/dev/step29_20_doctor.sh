#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.20 doctor ==="
python3 --version
echo

echo "=== Compile public eval suite scaleout generator ==="
python3 -m compileall -q scripts/dev/run_public_eval_suite_scaleout_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.19 remote inference execution harness artifacts ==="
./scripts/dev/step29_19_doctor.sh
echo

echo "=== Enforce no local model or remote inference execution for this step ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_20_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_20_forbidden_runtime_processes.txt
  echo "forbidden model runtime or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run public eval suite scaleout v1 ==="
PYTHONPATH=src python3 scripts/dev/run_public_eval_suite_scaleout_v1.py
echo

RESULT_DIR="results/local/public_eval_suite_scaleout_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/public_eval_task_scores.jsonl"
test -f "${RESULT_DIR}/public_eval_oracle_results.jsonl"
test -f "${RESULT_DIR}/dataset_exports/public_eval_suite_manifest.jsonl"
test -f "${RESULT_DIR}/public_safe_public_eval_suite_report.json"
test -f "${RESULT_DIR}/public_eval_suite_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/public_eval_suite_scaleout_v1")
summary = json.loads((root / "summary.json").read_text())
scores = [json.loads(line) for line in (root / "public_eval_task_scores.jsonl").read_text().splitlines() if line.strip()]
oracle_rows = [json.loads(line) for line in (root / "public_eval_oracle_results.jsonl").read_text().splitlines() if line.strip()]
manifest_rows = [json.loads(line) for line in (root / "dataset_exports/public_eval_suite_manifest.jsonl").read_text().splitlines() if line.strip()]
public_report = json.loads((root / "public_safe_public_eval_suite_report.json").read_text())
privacy = json.loads((root / "public_eval_suite_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.public_eval_suite_scaleout_summary.v1", summary
assert summary["suite_name"] == "public_eval_suite_scaleout_v1", summary
assert summary["public_eval_task_count"] == 6, summary
assert summary["verified_public_eval_task_count"] == 6, summary
assert summary["split_counts"] == {"public_eval": 6}, summary
assert summary["task_family_count"] >= 6, summary
assert summary["behavioral_axis_count"] >= 10, summary
assert summary["golden_patch_pass_count"] == 6, summary
assert summary["rejected_patch_fail_count"] == 6, summary
assert summary["public_overfit_hidden_catch_count"] == 6, summary
assert summary["pre_public_fail_count"] == 6, summary
assert summary["edit_scope_pass_count"] == 6, summary
assert summary["manifest_rows"] == 6, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["hidden_or_test_content_leak_count"] == 0, summary
assert summary["patch_content_leak_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["candidate_eval_executed"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_21_public_eval_candidate_runner_scaleout", summary

assert len(scores) == 6, scores
for row in scores:
    assert row["split"] == "public_eval", row
    assert row["verified"] is True, row
    assert row["pre_public_failed"] is True, row
    assert row["golden_patch_passed"] is True, row
    assert row["rejected_patch_failed"] is True, row
    assert row["public_overfit_caught_by_hidden"] is True, row
    assert row["edit_scope_passed"] is True, row
    for key in ["public_test_sha256", "hidden_test_sha256", "golden_patch_sha256"]:
        assert len(row[key]) == 64, row
        int(row[key], 16)

assert len(oracle_rows) == 18, oracle_rows
for task_id in {row["task_id"] for row in scores}:
    task_rows = [row for row in oracle_rows if row["task_id"] == task_id]
    assert len(task_rows) == 3, task_rows
    by_challenge = {row["challenge"]: row for row in task_rows}
    assert by_challenge["golden"]["solved"] is True, by_challenge
    assert by_challenge["rejected"]["solved"] is False, by_challenge
    assert by_challenge["public_overfit"]["post_public_passed"] is True, by_challenge
    assert by_challenge["public_overfit"]["post_hidden_passed"] is False, by_challenge
    assert by_challenge["golden"]["edit_scope_passed"] is True, by_challenge

assert len(manifest_rows) == 6, manifest_rows
manifest_blob = "\n".join(json.dumps(row, sort_keys=True) for row in manifest_rows)
assert "diff --git" not in manifest_blob, manifest_blob
assert "assertEqual" not in manifest_blob, manifest_blob
assert "def " not in manifest_blob, manifest_blob
for row in manifest_rows:
    assert row["split"] == "public_eval", row
    assert row["verified"] is True, row
    assert row["hidden_test_content_exported"] is False, row
    assert row["patch_content_exported"] is False, row
    assert row["training_export_allowed"] is False, row

assert public_report["public_eval_task_count"] == 6, public_report
assert public_report["verified_public_eval_task_count"] == 6, public_report
assert public_report["redaction_policy"]["test_content_included"] is False, public_report
assert public_report["redaction_policy"]["patch_content_included"] is False, public_report

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["hidden_or_test_content_leak_count"] == 0, privacy
assert privacy["patch_content_leak_count"] == 0, privacy

print("public_eval_suite_scaleout_v1: OK")
print("public_eval_task_count:", summary["public_eval_task_count"])
print("verified_public_eval_task_count:", summary["verified_public_eval_task_count"])
print("task_family_count:", summary["task_family_count"])
print("behavioral_axis_count:", summary["behavioral_axis_count"])
print("public_overfit_hidden_catch_count:", summary["public_overfit_hidden_catch_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_20_DOCTOR_OK"

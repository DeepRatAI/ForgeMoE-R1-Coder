#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.36 doctor ==="
python3 --version
echo

echo "=== Compile training payload materialization authorization ==="
python3 -m compileall -q scripts/dev/run_training_payload_materialization_authorization_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.35 source artifacts ==="
./scripts/dev/step29_35_doctor.sh
echo

echo "=== Enforce no local model or local training runtime for this gate ==="
if pgrep -af "ollama runner|local_transformers|torchrun|deepspeed|accelerate launch" >/tmp/forgemoe_step29_36_forbidden_local_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_36_forbidden_local_runtime_processes.txt
  echo "forbidden local model or local training runtime process detected"
  exit 1
fi
echo "forbidden_local_runtime_processes: none"
echo

echo "=== Run training payload materialization authorization v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_training_payload_materialization_authorization_v1.py
echo

RESULT_DIR="results/local/training_payload_materialization_authorization_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/training_payload_authorization_decisions.jsonl"
test -f "${RESULT_DIR}/payload_validation_results.jsonl"
test -f "${RESULT_DIR}/payload_split_isolation_report.json"
test -f "${RESULT_DIR}/training_release_policy_v2.json"
test -f "${RESULT_DIR}/training_payload_materialization_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_training_payload_materialization_report.json"
test -f "${RESULT_DIR}/training_payload_materialization_privacy_report.json"
test -f "${RESULT_DIR}/dataset_exports/patch_sft_training_payload.jsonl"
test -f "${RESULT_DIR}/dataset_exports/patch_sft_training_payload_manifest.jsonl"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/training_payload_materialization_authorization_v1")
summary = json.loads((root / "summary.json").read_text())
decisions = [
    json.loads(line)
    for line in (root / "training_payload_authorization_decisions.jsonl").read_text().splitlines()
    if line.strip()
]
validations = [
    json.loads(line)
    for line in (root / "payload_validation_results.jsonl").read_text().splitlines()
    if line.strip()
]
split_report = json.loads((root / "payload_split_isolation_report.json").read_text())
policy = json.loads((root / "training_release_policy_v2.json").read_text())
gate = json.loads((root / "training_payload_materialization_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_training_payload_materialization_report.json").read_text())
privacy = json.loads((root / "training_payload_materialization_privacy_report.json").read_text())
payload_rows = [
    json.loads(line)
    for line in (root / "dataset_exports/patch_sft_training_payload.jsonl").read_text().splitlines()
    if line.strip()
]
manifest_rows = [
    json.loads(line)
    for line in (root / "dataset_exports/patch_sft_training_payload_manifest.jsonl").read_text().splitlines()
    if line.strip()
]

assert summary["schema_version"] == "forgeagent.training_payload_materialization_authorization_summary.v1", summary
assert summary["gate_name"] == "training_payload_materialization_authorization_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["source_task_count"] == 12, summary
assert summary["oracle_certified_train_candidate_count"] == 4, summary
assert summary["authorized_train_candidate_count"] == 4, summary
assert summary["materialized_training_payload_row_count"] == 4, summary
assert summary["excluded_non_train_task_count"] == 8, summary
assert summary["payload_validation_pass_count"] == 4, summary
assert summary["payload_hidden_test_export_count"] == 0, summary
assert summary["payload_negative_patch_export_count"] == 0, summary
assert summary["payload_public_benchmark_exact_collision_count"] == 0, summary
assert summary["release_policy_passed_requirement_count"] == 12, summary
assert summary["release_policy_failed_requirement_count"] == 0, summary
assert summary["training_payload_materialization_authorized"] is True, summary
assert summary["training_grade_data_release_allowed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["next_recommended_step"] == "step29_37_training_payload_schema_quality_and_tokenization_gate_v1", summary

assert len(decisions) == 12, decisions
allowed = [row for row in decisions if row["training_payload_materialization_authorized"]]
blocked = [row for row in decisions if not row["training_payload_materialization_authorized"]]
assert len(allowed) == 4, allowed
assert len(blocked) == 8, blocked
assert all(row["split"] == "train" for row in allowed), allowed
assert all(row["release_class"] == "training_grade_patch_sft_materialized" for row in allowed), allowed
assert all("not_train_split" in row["blocked_reasons"] for row in blocked), blocked

assert len(validations) == 4, validations
for row in validations:
    assert row["payload_valid"] is True, row
    assert row["pre_public_failed_as_expected"] is True, row
    assert row["git_apply_check_passed"] is True, row
    assert row["patch_applied"] is True, row
    assert row["post_public_passed"] is True, row
    assert row["post_hidden_passed"] is True, row
    assert row["edit_scope_passed"] is True, row
    assert row["changed_files"] == row["expected_patch_files"], row
    assert row["patch_files"] == row["expected_patch_files"], row

assert split_report["passed"] is True, split_report
assert split_report["materialized_training_payload_row_count"] == 4, split_report
assert split_report["excluded_non_train_task_count"] == 8, split_report
assert split_report["non_train_rows_materialized"] == 0, split_report
assert split_report["private_heldout_leakage_to_training_payload"] is False, split_report
assert split_report["public_eval_leakage_to_training_payload"] is False, split_report
assert split_report["eval_leakage_to_training_payload"] is False, split_report

assert policy["schema_version"] == "forgeagent.training_payload_release_policy_v2.v1", policy
assert policy["passed_requirement_count"] == 12, policy
assert policy["failed_requirement_count"] == 0, policy
assert all(item["passed"] is True for item in policy["requirements"]), policy
assert policy["training_grade_data_release_allowed"] is True, policy
assert policy["training_launch_allowed"] is False, policy
assert policy["model_release_allowed"] is False, policy

assert gate["schema_version"] == "forgeagent.training_payload_materialization_gate_decision.v1", gate
assert gate["training_payload_materialization_authorized"] is True, gate
assert gate["training_grade_data_release_allowed"] is True, gate
assert gate["training_launch_allowed"] is False, gate
assert gate["model_release_allowed"] is False, gate
assert gate["blocked_reasons"] == [], gate
assert "training_payload_materialization_not_authorized" in gate["resolved_previous_blockers"], gate

assert len(payload_rows) == 4, payload_rows
assert len(manifest_rows) == 4, manifest_rows
payload_blob = "\n".join(json.dumps(row, sort_keys=True) for row in payload_rows)
for marker in ("test_hidden.py", "rejected.patch", "public_overfit.patch", "wrong_file.patch", "semantic_noop.patch"):
    assert marker not in payload_blob, (marker, payload_blob[:500])
for row in payload_rows:
    assert row["schema_version"] == "forgeagent.patch_sft_training_payload_row.v1", row
    assert row["split"] == "train", row
    assert row["training_export_allowed"] is True, row
    assert row["training_grade"] is True, row
    assert row["hidden_tests_exported"] is False, row
    assert row["negative_patches_exported"] is False, row
    assert row["eval_private_or_public_eval_exported"] is False, row
    assert row["target_patch"].startswith("diff --git "), row
    assert len(row["messages"]) == 2, row
    assert row["messages"][1]["content"] == row["target_patch"], row
    assert row["public_tests"], row
    assert row["repo_files"], row
    assert all(not item["path"].startswith("tests/") for item in row["repo_files"]), row
    assert all(item["path"].startswith("test_") or item["path"].startswith("tests/") for item in row["public_tests"]), row

for row in manifest_rows:
    assert row["schema_version"] == "forgeagent.patch_sft_training_payload_manifest_row.v1", row
    assert row["split"] == "train", row
    assert row["training_export_allowed"] is True, row
    assert row["hidden_tests_exported"] is False, row
    assert row["negative_patches_exported"] is False, row
    for key in ("payload_id_sha256", "task_id_sha256", "target_patch_sha256", "payload_row_sha256"):
        assert len(row[key]) == 64, row
        int(row[key], 16)

assert public_report["schema_version"] == "forgeagent.public_safe_training_payload_materialization_report.v1", public_report
assert public_report["materialized_training_payload_row_count"] == 4, public_report
assert public_report["raw_task_ids_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["raw_text_included"] is False, public_report
assert public_report["repo_content_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["hidden_test_content_included"] is False, public_report
assert public_report["negative_patch_content_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
for marker in ("diff --git", "assertEqual", "hidden_tests", "target_patch", "repo_files", "messages"):
    assert marker not in public_blob, (marker, public_blob)

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("training_payload_materialization_authorization_v1: OK")
print("authorized_train_candidate_count:", summary["authorized_train_candidate_count"])
print("materialized_training_payload_row_count:", summary["materialized_training_payload_row_count"])
print("excluded_non_train_task_count:", summary["excluded_non_train_task_count"])
print("payload_validation_pass_count:", summary["payload_validation_pass_count"])
print("release_policy_passed_requirement_count:", summary["release_policy_passed_requirement_count"])
print("training_grade_data_release_allowed:", summary["training_grade_data_release_allowed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.36 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Step 29.36 Training Payload Materialization Authorization" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Training Payload Materialization Authorization" docs/data/TRAINING_PAYLOAD_MATERIALIZATION_AUTHORIZATION.md
grep -q "ADR-0062" docs/engineering/ADR_0062_TRAINING_PAYLOAD_MATERIALIZATION_AUTHORIZATION.md

echo
echo "STEP29_36_DOCTOR_OK"

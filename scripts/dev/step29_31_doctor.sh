#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.31 doctor ==="
python3 --version
echo

echo "=== Compile hardened executable task generator ==="
python3 -m compileall -q scripts/dev/run_hardened_executable_task_generator_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.30 source artifacts ==="
./scripts/dev/step29_30_doctor.sh
echo

echo "=== Enforce no local model, training, large dataset download, or remote inference execution for this gate ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|torchrun|deepspeed|accelerate launch|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_31_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_31_forbidden_runtime_processes.txt
  echo "forbidden model runtime, training, or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run hardened executable task generator v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_hardened_executable_task_generator_v1.py
echo

RESULT_DIR="results/local/hardened_executable_task_generator_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/task_results.jsonl"
test -f "${RESULT_DIR}/patch_challenge_results.jsonl"
test -f "${RESULT_DIR}/dataset_exports/hardened_executable_task_manifest.jsonl"
test -f "${RESULT_DIR}/dataset_exports/patch_sft_train_scaffold_manifest.jsonl"
test -f "${RESULT_DIR}/hardened_executable_task_generator_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_hardened_executable_task_generator_report.json"
test -f "${RESULT_DIR}/hardened_executable_task_generator_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/hardened_executable_task_generator_v1")
run_root = Path("tmp/hardened_executable_task_generator_v1_runs")
summary = json.loads((root / "summary.json").read_text())
task_results = [json.loads(line) for line in (root / "task_results.jsonl").read_text().splitlines()]
challenge_rows = [json.loads(line) for line in (root / "patch_challenge_results.jsonl").read_text().splitlines()]
manifest_rows = [json.loads(line) for line in (root / "dataset_exports/hardened_executable_task_manifest.jsonl").read_text().splitlines()]
train_scaffold = [json.loads(line) for line in (root / "dataset_exports/patch_sft_train_scaffold_manifest.jsonl").read_text().splitlines()]
gate = json.loads((root / "hardened_executable_task_generator_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_hardened_executable_task_generator_report.json").read_text())
privacy = json.loads((root / "hardened_executable_task_generator_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.hardened_executable_task_generator_summary.v1", summary
assert summary["gate_name"] == "hardened_executable_task_generator_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["task_count"] == 12, summary
assert summary["verified_task_count"] == 12, summary
assert summary["split_counts"] == {"train": 4, "eval": 3, "private_heldout": 3, "public_eval": 2}, summary
assert summary["task_family_count"] == 12, summary
assert summary["behavioral_axis_count"] >= 30, summary
assert summary["multi_file_task_count"] == 12, summary
assert summary["challenge_result_count"] == 60, summary
assert summary["patch_build_temp_git_repo_count"] == 60, summary
assert summary["verification_temp_git_repo_count"] == 60, summary
assert summary["pre_public_fail_count"] == 12, summary
assert summary["git_apply_check_pass_count"] == 12, summary
assert summary["post_public_pass_count"] == 12, summary
assert summary["post_hidden_pass_count"] == 12, summary
assert summary["rejected_patch_fail_count"] == 12, summary
assert summary["public_overfit_hidden_catch_count"] == 12, summary
assert summary["wrong_file_negative_fail_count"] == 12, summary
assert summary["semantic_noop_negative_fail_count"] == 12, summary
assert summary["train_scaffold_manifest_rows"] == 4, summary
assert summary["training_grade_candidate_count"] == 0, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary

assert len(task_results) == 12, task_results
for row in task_results:
    assert row["verified"] is True, row
    assert row["repo_shape"] == "temporary_git_repository", row
    assert row["patch_format"] == "git_diff", row
    assert row["multi_file_patch"] is True, row
    assert row["golden_patch_check_passed"] is True, row
    assert row["golden_patch_applied"] is True, row
    assert row["pre_public_failed_as_expected"] is True, row
    assert row["post_public_passed"] is True, row
    assert row["post_hidden_passed"] is True, row
    assert row["golden_edit_scope_passed"] is True, row
    assert row["rejected_patch_failed"] is True, row
    assert row["public_overfit_caught_by_hidden"] is True, row
    assert row["wrong_file_negative_failed"] is True, row
    assert row["semantic_noop_negative_failed"] is True, row
    assert row["training_grade_candidate"] is False, row
    task_dir = root / "tasks" / row["task_id"]
    for patch_name in ("golden.patch", "rejected.patch", "public_overfit.patch", "wrong_file.patch", "semantic_noop.patch"):
        patch_text = (task_dir / patch_name).read_text()
        assert patch_text.startswith("diff --git "), patch_text
        assert "\nindex " in patch_text, patch_text
        int(row["patch_sha256s"][patch_name[:-6]], 16)

assert len(challenge_rows) == 60, challenge_rows
for task_id in {row["task_id"] for row in task_results}:
    rows = [row for row in challenge_rows if row["task_id"] == task_id]
    assert len(rows) == 5, rows
    by_label = {row["challenge"]: row for row in rows}
    assert by_label["golden"]["solved"] is True, by_label
    assert by_label["golden"]["patch_file_count"] == 2, by_label
    assert by_label["golden"]["edit_scope_passed"] is True, by_label
    assert by_label["rejected"]["patch_check_passed"] is True, by_label
    assert by_label["rejected"]["solved"] is False, by_label
    assert by_label["public_overfit"]["patch_check_passed"] is True, by_label
    assert by_label["public_overfit"]["post_public_passed"] is True, by_label
    assert by_label["public_overfit"]["post_hidden_passed"] is False, by_label
    assert by_label["wrong_file"]["patch_check_passed"] is True, by_label
    assert by_label["wrong_file"]["solved"] is False, by_label
    assert by_label["wrong_file"]["edit_scope_passed"] is False, by_label
    assert by_label["semantic_noop"]["patch_check_passed"] is True, by_label
    assert by_label["semantic_noop"]["solved"] is False, by_label

assert len(manifest_rows) == 12, manifest_rows
manifest_blob = "\n".join(json.dumps(row, sort_keys=True) for row in manifest_rows)
assert "diff --git" not in manifest_blob, manifest_blob
assert "assertEqual" not in manifest_blob, manifest_blob
assert "hidden_tests" not in manifest_blob, manifest_blob
for row in manifest_rows:
    assert row["verified"] is True, row
    assert row["training_grade_candidate"] is False, row
    assert row["training_export_allowed"] is False, row
    assert row["hidden_test_content_exported"] is False, row
    assert row["patch_content_exported"] is False, row
    assert row["raw_instruction_exported"] is False, row

assert len(train_scaffold) == 4, train_scaffold
assert all(row["training_grade_candidate"] is False for row in train_scaffold), train_scaffold
assert all(row["training_export_allowed"] is False for row in train_scaffold), train_scaffold

assert gate["schema_version"] == "forgeagent.hardened_executable_task_generator_gate_decision.v1", gate
assert gate["hardened_executable_generation_complete"] is True, gate
assert gate["task_count"] == 12, gate
assert gate["verified_task_count"] == 12, gate
assert gate["all_required_oracle_negatives_passed"] is True, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert "new_hardened_tasks_require_oracle_quality_certification_gate" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_hardened_executable_task_generator_report.v1", public_report
assert public_report["verified_task_count"] == 12, public_report
assert public_report["raw_task_ids_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["raw_text_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["hidden_test_content_included"] is False, public_report
assert public_report["private_identifier_values_included"] is False, public_report
assert public_report["model_outputs_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-hard-private-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob
assert "hidden_tests" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

assert len(list((run_root / "patch_build_repos").glob("*/.git"))) == 60
assert len(list((run_root / "verification").glob("*/*/.git"))) == 60

print("hardened_executable_task_generator_v1: OK")
print("task_count:", summary["task_count"])
print("verified_task_count:", summary["verified_task_count"])
print("split_counts:", summary["split_counts"])
print("challenge_result_count:", summary["challenge_result_count"])
print("public_overfit_hidden_catch_count:", summary["public_overfit_hidden_catch_count"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.31 Hardened Executable Task Generator" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.31 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Hardened Executable Task Generator" docs/data/HARDENED_EXECUTABLE_TASK_GENERATOR.md
grep -q "ADR-0057" docs/engineering/ADR_0057_HARDENED_EXECUTABLE_TASK_GENERATOR.md

echo
echo "STEP29_31_DOCTOR_OK"

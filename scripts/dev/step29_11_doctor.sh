#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.11 doctor ==="
python3 --version
echo

echo "=== Compile agentic trajectory recorder ==="
python3 -m compileall -q scripts/dev/run_agentic_trajectory_recorder_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.10 oracle gate artifacts ==="
./scripts/dev/step29_10_doctor.sh
echo

echo "=== Run agentic trajectory recorder v1 ==="
PYTHONPATH=src python3 scripts/dev/run_agentic_trajectory_recorder_v1.py
echo

RESULT_DIR="results/local/agentic_trajectory_recorder_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/trajectory_records.jsonl"
test -f "${RESULT_DIR}/privacy_report.json"
test -f "${RESULT_DIR}/dataset_exports/trajectory_sft_train.jsonl"
test -f "${RESULT_DIR}/dataset_exports/repair_trace_train.jsonl"
test -f "${RESULT_DIR}/dataset_exports/trajectory_preference_train.jsonl"
test -f "${RESULT_DIR}/dataset_exports/eval_trajectories.jsonl"
test -f "${RESULT_DIR}/dataset_exports/private_heldout_trajectories.jsonl"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/agentic_trajectory_recorder_v1")
summary = json.loads((root / "summary.json").read_text())
privacy = json.loads((root / "privacy_report.json").read_text())
trajectories = [json.loads(line) for line in (root / "trajectory_records.jsonl").read_text().splitlines() if line.strip()]
train_sft = [json.loads(line) for line in (root / "dataset_exports/trajectory_sft_train.jsonl").read_text().splitlines() if line.strip()]
repair_rows = [json.loads(line) for line in (root / "dataset_exports/repair_trace_train.jsonl").read_text().splitlines() if line.strip()]
preference_rows = [json.loads(line) for line in (root / "dataset_exports/trajectory_preference_train.jsonl").read_text().splitlines() if line.strip()]
eval_rows = [json.loads(line) for line in (root / "dataset_exports/eval_trajectories.jsonl").read_text().splitlines() if line.strip()]
private_rows = [json.loads(line) for line in (root / "dataset_exports/private_heldout_trajectories.jsonl").read_text().splitlines() if line.strip()]

assert summary["schema_version"] == "forgeagent.agentic_trajectory_recorder_summary.v1", summary
assert summary["recorder_name"] == "agentic_trajectory_recorder_v1", summary
assert summary["source_step"] == "step29_10_oracle_hidden_test_gate_v0", summary
assert summary["trajectory_count"] == 3, summary
assert summary["solved_trajectory_count"] == 3, summary
assert summary["split_counts"]["train"] == 1, summary
assert summary["split_counts"]["eval"] == 1, summary
assert summary["split_counts"]["private_heldout"] == 1, summary
assert summary["event_type_count"] >= 13, summary
assert summary["min_event_count"] >= 17, summary
assert summary["public_overfit_caught_by_hidden_count"] == 3, summary
assert summary["trajectory_sft_train_rows"] == 1, summary
assert summary["repair_trace_train_rows"] == 1, summary
assert summary["trajectory_preference_train_rows"] == 1, summary
assert summary["eval_trajectory_rows"] == 1, summary
assert summary["private_heldout_trajectory_rows"] == 1, summary
assert summary["private_heldout_exported_to_training"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["hidden_test_leak_count"] == 0, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_12_private_heldout_seed_set", summary

required_event_types = {
    "read_task",
    "list_files",
    "read_file",
    "inspect_public_tests",
    "run_public_tests",
    "plan",
    "generate_patch",
    "git_apply_check",
    "apply_patch",
    "run_hidden_tests",
    "observe_failure",
    "repair",
    "final_answer",
}
assert required_event_types.issubset(set(summary["event_types"])), summary["event_types"]

assert len(trajectories) == 3, trajectories
for row in trajectories:
    assert row["schema_version"] == "forgeagent.agentic_trajectory_record.v1", row
    assert row["metrics"]["solved"] is True, row
    assert row["metrics"]["public_overfit_caught_by_hidden"] is True, row
    assert row["metrics"]["event_count"] >= 17, row
    assert row["attempts"][0]["label"] == "negative", row
    assert row["attempts"][0]["public_passed"] is True, row
    assert row["attempts"][0]["hidden_passed"] is False, row
    assert row["attempts"][1]["label"] == "positive", row
    assert row["attempts"][1]["public_passed"] is True, row
    assert row["attempts"][1]["hidden_passed"] is True, row
    assert row["privacy"]["hidden_test_content_exported"] is False, row

assert len(train_sft) == 1, train_sft
assert train_sft[0]["split"] == "train", train_sft
assert train_sft[0]["metadata"]["hidden_tests_included"] is False, train_sft
assert len(repair_rows) == 1, repair_rows
assert repair_rows[0]["negative_attempt"]["hidden_passed"] is False, repair_rows
assert repair_rows[0]["positive_attempt"]["hidden_passed"] is True, repair_rows
assert len(preference_rows) == 1, preference_rows
assert preference_rows[0]["rejected_reason"] == "passes_public_tests_but_fails_hidden_tests", preference_rows
assert len(eval_rows) == 1, eval_rows
assert eval_rows[0]["training_export_allowed"] is False, eval_rows
assert len(private_rows) == 1, private_rows
assert private_rows[0]["training_export_allowed"] is False, private_rows
assert private_rows[0]["patch_content_withheld_from_training"] is True, private_rows

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["hidden_test_leak_count"] == 0, privacy

train_blob = "\n".join(
    (root / "dataset_exports" / name).read_text()
    for name in [
        "trajectory_sft_train.jsonl",
        "repair_trace_train.jsonl",
        "trajectory_preference_train.jsonl",
    ]
)
assert "forge-micro-private-heldout-max2" not in train_blob, train_blob

print("agentic_trajectory_recorder_v1: OK")
print("trajectory_count:", summary["trajectory_count"])
print("solved_trajectory_count:", summary["solved_trajectory_count"])
print("event_type_count:", summary["event_type_count"])
print("trajectory_sft_train_rows:", summary["trajectory_sft_train_rows"])
print("repair_trace_train_rows:", summary["repair_trace_train_rows"])
print("trajectory_preference_train_rows:", summary["trajectory_preference_train_rows"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_11_DOCTOR_OK"

#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.10 doctor ==="
python3 --version
echo

echo "=== Compile oracle hidden-test gate ==="
python3 -m compileall -q scripts/dev/run_oracle_hidden_test_gate.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.9 source artifacts ==="
./scripts/dev/step29_9_doctor.sh
echo

echo "=== Run oracle hidden-test gate ==="
PYTHONPATH=src python3 scripts/dev/run_oracle_hidden_test_gate.py
echo

RESULT_DIR="results/local/oracle_hidden_test_gate_v0"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/task_oracle_scores.jsonl"
test -f "${RESULT_DIR}/patch_challenge_results.jsonl"
test -f "${RESULT_DIR}/hidden_test_isolation_report.json"
test -d "${RESULT_DIR}/challenge_patches"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/oracle_hidden_test_gate_v0")
summary = json.loads((root / "summary.json").read_text())
scores = [json.loads(line) for line in (root / "task_oracle_scores.jsonl").read_text().splitlines() if line.strip()]
challenges = [json.loads(line) for line in (root / "patch_challenge_results.jsonl").read_text().splitlines() if line.strip()]
isolation = json.loads((root / "hidden_test_isolation_report.json").read_text())

assert summary["schema_version"] == "forgeagent.oracle_hidden_test_gate_summary.v0", summary
assert summary["gate_name"] == "oracle_hidden_test_gate_v0", summary
assert summary["source_step"] == "step29_9_internal_synthetic_micro_generator_v0", summary
assert summary["source_verified_task_count"] == 3, summary
assert summary["task_count"] == 3, summary
assert summary["passed_task_count"] == 3, summary
assert summary["golden_patch_pass_count"] == 3, summary
assert summary["rejected_patch_fail_count"] == 3, summary
assert summary["semantic_noop_patch_fail_count"] == 3, summary
assert summary["empty_patch_fail_count"] == 3, summary
assert summary["wrong_file_patch_fail_count"] == 3, summary
assert summary["public_overfit_hidden_catch_count"] == 3, summary
assert summary["minimum_observed_oracle_strength_score"] >= 0.95, summary
assert summary["hidden_test_isolation_passed"] is True, summary
assert summary["private_heldout_isolation_passed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_11_agentic_trajectory_recorder_v1", summary

assert len(scores) == 3, scores
for row in scores:
    assert row["gate_passed"] is True, row
    assert row["oracle_strength_score"] >= 0.95, row
    assert row["hidden_coverage_score"] == 1.0, row
    assert row["anti_overfit_score"] == 1.0, row
    assert row["edit_scope_score"] == 1.0, row
    for check_name, passed in row["checks"].items():
        assert passed is True, (check_name, row)

assert len(challenges) == 18, len(challenges)

for task_id in {row["task_id"] for row in scores}:
    task_challenges = [row for row in challenges if row["task_id"] == task_id]
    assert {row["challenge"] for row in task_challenges} == {
        "golden",
        "rejected",
        "semantic_noop",
        "empty",
        "wrong_file",
        "public_overfit",
    }, task_challenges

    public_overfit = [row for row in task_challenges if row["challenge"] == "public_overfit"][0]
    assert public_overfit["patch_check_passed"] is True, public_overfit
    assert public_overfit["patch_applied"] is True, public_overfit
    assert public_overfit["post_public_passed"] is True, public_overfit
    assert public_overfit["post_hidden_passed"] is False, public_overfit

    wrong_file = [row for row in task_challenges if row["challenge"] == "wrong_file"][0]
    assert wrong_file["patch_check_passed"] is True, wrong_file
    assert wrong_file["patch_applied"] is True, wrong_file
    assert wrong_file["edit_scope_ok"] is False, wrong_file
    assert wrong_file["solved"] is False, wrong_file

    empty = [row for row in task_challenges if row["challenge"] == "empty"][0]
    assert empty["patch_check_passed"] is False, empty
    assert empty["solved"] is False, empty

assert isolation["hidden_test_leak_count"] == 0, isolation
assert isolation["private_patch_leak_count"] == 0, isolation
assert isolation["private_task_id_leak_count"] == 0, isolation
assert isolation["private_export_withholds_patch"] is True, isolation

print("oracle_hidden_test_gate: OK")
print("task_count:", summary["task_count"])
print("passed_task_count:", summary["passed_task_count"])
print("public_overfit_hidden_catch_count:", summary["public_overfit_hidden_catch_count"])
print("minimum_observed_oracle_strength_score:", summary["minimum_observed_oracle_strength_score"])
print("hidden_test_isolation_passed:", summary["hidden_test_isolation_passed"])
print("private_heldout_isolation_passed:", summary["private_heldout_isolation_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_10_DOCTOR_OK"

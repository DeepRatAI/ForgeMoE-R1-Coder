#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.9 doctor ==="
python3 --version
echo

echo "=== Compile micro-generator ==="
python3 -m compileall -q scripts/dev/run_internal_synthetic_micro_generator.py
echo "compileall: OK"
echo

echo "=== Run deterministic internal synthetic micro-generator ==="
PYTHONPATH=src python3 scripts/dev/run_internal_synthetic_micro_generator.py
echo

RESULT_DIR="results/local/internal_synthetic_micro_generator_v0"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/task_results.jsonl"
test -f "${RESULT_DIR}/dataset_exports/patch_sft_train.jsonl"
test -f "${RESULT_DIR}/dataset_exports/trajectory_sft_train_seed.jsonl"
test -f "${RESULT_DIR}/dataset_exports/preference_pairs_train_seed.jsonl"
test -f "${RESULT_DIR}/dataset_exports/eval_tasks.jsonl"
test -f "${RESULT_DIR}/dataset_exports/private_heldout_tasks.jsonl"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/internal_synthetic_micro_generator_v0")
run_root = Path("tmp/internal_synthetic_micro_generator_runs")
summary = json.loads((root / "summary.json").read_text())
task_rows = [json.loads(line) for line in (root / "task_results.jsonl").read_text().splitlines() if line.strip()]

assert summary["schema_version"] == "forgeagent.internal_synthetic_micro_generator_summary.v0", summary
assert summary["task_count"] == 3, summary
assert summary["verified_task_count"] == 3, summary
assert summary["split_counts"]["train"] == 1, summary
assert summary["split_counts"]["eval"] == 1, summary
assert summary["split_counts"]["private_heldout"] == 1, summary
assert summary["patch_sft_train_rows"] == 1, summary
assert summary["trajectory_sft_train_seed_rows"] == 1, summary
assert summary["preference_pair_train_seed_rows"] == 1, summary
assert summary["eval_task_rows"] == 1, summary
assert summary["private_heldout_task_rows"] == 1, summary
assert summary["private_heldout_exported_to_training"] is False, summary
assert summary["launches_training_job"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_10_oracle_hidden_test_gate", summary

assert len(task_rows) == 3, task_rows

for row in task_rows:
    assert row["verified"] is True, row
    assert row["pre_public_failed_as_expected"] is True, row
    assert row["golden_patch_check_passed"] is True, row
    assert row["golden_patch_applied"] is True, row
    assert row["post_public_passed"] is True, row
    assert row["post_hidden_passed"] is True, row
    task_dir = root / "tasks" / row["task_id"]
    for patch_name in ("golden.patch", "rejected.patch"):
        patch_text = (task_dir / patch_name).read_text()
        assert patch_text.startswith("diff --git a/app/utils.py b/app/utils.py\n"), patch_text
        assert "\nindex " in patch_text, patch_text
        assert "\n--- a/app/utils.py\n" in patch_text, patch_text
        assert "\n+++ b/app/utils.py\n" in patch_text, patch_text

patch_build_repos = sorted((run_root / "patch_build_repos").glob("*/.git"))
assert len(patch_build_repos) == 6, patch_build_repos

private_rows = [row for row in task_rows if row["split"] == "private_heldout"]
assert len(private_rows) == 1, private_rows
assert private_rows[0]["never_train_on"] is True, private_rows

private_export = Path("results/local/internal_synthetic_micro_generator_v0/dataset_exports/private_heldout_tasks.jsonl").read_text()
assert "withheld_from_training_exports" in private_export, private_export

print("internal_synthetic_micro_generator: OK")
print("task_count:", summary["task_count"])
print("verified_task_count:", summary["verified_task_count"])
print("split_counts:", summary["split_counts"])
print("patch_sft_train_rows:", summary["patch_sft_train_rows"])
print("trajectory_sft_train_seed_rows:", summary["trajectory_sft_train_seed_rows"])
print("preference_pair_train_seed_rows:", summary["preference_pair_train_seed_rows"])
print("private_heldout_exported_to_training:", summary["private_heldout_exported_to_training"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_9_DOCTOR_OK"

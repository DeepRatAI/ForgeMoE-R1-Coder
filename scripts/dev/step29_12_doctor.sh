#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.12 doctor ==="
python3 --version
echo

echo "=== Compile private heldout seed set generator ==="
python3 -m compileall -q scripts/dev/run_private_heldout_seed_set_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.11 source artifacts ==="
./scripts/dev/step29_11_doctor.sh
echo

echo "=== Run private heldout seed set v1 ==="
PYTHONPATH=src python3 scripts/dev/run_private_heldout_seed_set_v1.py
echo

RESULT_DIR="results/local/private_heldout_seed_set_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/private_heldout_seed_scores.jsonl"
test -f "${RESULT_DIR}/private_heldout_oracle_results.jsonl"
test -f "${RESULT_DIR}/isolation_report.json"
test -f "${RESULT_DIR}/dataset_exports/private_heldout_seed_manifest.jsonl"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/private_heldout_seed_set_v1")
summary = json.loads((root / "summary.json").read_text())
isolation = json.loads((root / "isolation_report.json").read_text())
scores = [json.loads(line) for line in (root / "private_heldout_seed_scores.jsonl").read_text().splitlines() if line.strip()]
oracle_rows = [json.loads(line) for line in (root / "private_heldout_oracle_results.jsonl").read_text().splitlines() if line.strip()]
manifest_rows = [json.loads(line) for line in (root / "dataset_exports/private_heldout_seed_manifest.jsonl").read_text().splitlines() if line.strip()]

assert summary["schema_version"] == "forgeagent.private_heldout_seed_set_summary.v1", summary
assert summary["seed_set_name"] == "private_heldout_seed_set_v1", summary
assert summary["private_heldout_task_count"] == 3, summary
assert summary["verified_private_heldout_task_count"] == 3, summary
assert summary["split_counts"] == {"private_heldout": 3}, summary
assert summary["task_family_count"] >= 3, summary
assert summary["behavioral_axis_count"] >= 6, summary
assert summary["golden_patch_pass_count"] == 3, summary
assert summary["rejected_patch_fail_count"] == 3, summary
assert summary["public_overfit_hidden_catch_count"] == 3, summary
assert summary["pre_public_fail_count"] == 3, summary
assert summary["edit_scope_pass_count"] == 3, summary
assert summary["manifest_rows"] == 3, summary
assert summary["training_export_rows"] == 0, summary
assert summary["private_seed_exported_to_training"] is False, summary
assert summary["hidden_test_content_exported_to_training"] is False, summary
assert summary["patch_content_exported_to_training"] is False, summary
assert summary["public_safe_manifest_contains_patch_content"] is False, summary
assert summary["public_safe_manifest_contains_hidden_content"] is False, summary
assert summary["isolation_scan_passed"] is True, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["hidden_test_leak_count"] == 0, summary
assert summary["private_patch_leak_count"] == 0, summary
assert summary["private_task_id_leak_count"] == 0, summary
assert summary["public_safe_content_leak_count"] == 0, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_13_heldout_aware_eval_protocol", summary

assert len(scores) == 3, scores
for row in scores:
    assert row["split"] == "private_heldout", row
    assert row["never_train_on"] is True, row
    assert row["verified"] is True, row
    assert row["golden_patch_passed"] is True, row
    assert row["rejected_patch_failed"] is True, row
    assert row["public_overfit_caught_by_hidden"] is True, row

assert len(oracle_rows) == 9, oracle_rows
for task_id in {row["task_id"] for row in scores}:
    task_rows = [row for row in oracle_rows if row["task_id"] == task_id]
    assert len(task_rows) == 3, task_rows
    by_challenge = {row["challenge"]: row for row in task_rows}
    assert by_challenge["golden"]["solved"] is True, by_challenge
    assert by_challenge["rejected"]["solved"] is False, by_challenge
    assert by_challenge["public_overfit"]["post_public_passed"] is True, by_challenge
    assert by_challenge["public_overfit"]["post_hidden_passed"] is False, by_challenge

assert len(manifest_rows) == 3, manifest_rows
manifest_blob = "\n".join(json.dumps(row, sort_keys=True) for row in manifest_rows)
for row in manifest_rows:
    assert row["split"] == "private_heldout", row
    assert row["never_train_on"] is True, row
    assert row["hidden_test_content_exported"] is False, row
    assert row["patch_content_exported"] is False, row
    assert row["training_export_allowed"] is False, row
    assert len(row["hidden_test_sha256"]) == 64, row
    int(row["hidden_test_sha256"], 16)
    assert "diff --git" not in json.dumps(row), row

assert "assertEqual" not in manifest_blob, manifest_blob
assert isolation["passed"] is True, isolation
assert isolation["secret_finding_count"] == 0, isolation
assert isolation["hidden_test_leak_count"] == 0, isolation
assert isolation["private_patch_leak_count"] == 0, isolation
assert isolation["private_task_id_leak_count"] == 0, isolation
assert isolation["public_safe_content_leak_count"] == 0, isolation

print("private_heldout_seed_set_v1: OK")
print("private_heldout_task_count:", summary["private_heldout_task_count"])
print("verified_private_heldout_task_count:", summary["verified_private_heldout_task_count"])
print("task_family_count:", summary["task_family_count"])
print("behavioral_axis_count:", summary["behavioral_axis_count"])
print("public_overfit_hidden_catch_count:", summary["public_overfit_hidden_catch_count"])
print("isolation_scan_passed:", summary["isolation_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_12_DOCTOR_OK"

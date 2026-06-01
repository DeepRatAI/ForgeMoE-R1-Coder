#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.28 doctor ==="
python3 --version
echo

echo "=== Compile dedup/near-duplicate scanner ==="
python3 -m compileall -q scripts/dev/run_dedup_near_duplicate_scanner_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.27 source artifacts ==="
./scripts/dev/step29_27_doctor.sh
echo

echo "=== Enforce no local model, training, large dataset download, or remote inference execution for this gate ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|torchrun|deepspeed|accelerate launch|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_28_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_28_forbidden_runtime_processes.txt
  echo "forbidden model runtime, training, or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run dedup/near-duplicate scanner v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_dedup_near_duplicate_scanner_v1.py
echo

RESULT_DIR="results/local/dedup_near_duplicate_scanner_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/dedup_row_features.jsonl"
test -f "${RESULT_DIR}/pairwise_similarity_results.jsonl"
test -f "${RESULT_DIR}/dedup_row_decisions.jsonl"
test -f "${RESULT_DIR}/exact_duplicate_groups.json"
test -f "${RESULT_DIR}/near_duplicate_groups.json"
test -f "${RESULT_DIR}/split_collision_matrix.json"
test -f "${RESULT_DIR}/scan_summary.json"
test -f "${RESULT_DIR}/dedup_near_duplicate_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_dedup_near_duplicate_report.json"
test -f "${RESULT_DIR}/dedup_near_duplicate_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/dedup_near_duplicate_scanner_v1")
summary = json.loads((root / "summary.json").read_text())
features = [json.loads(line) for line in (root / "dedup_row_features.jsonl").read_text().splitlines()]
pairs = [json.loads(line) for line in (root / "pairwise_similarity_results.jsonl").read_text().splitlines()]
decisions = [json.loads(line) for line in (root / "dedup_row_decisions.jsonl").read_text().splitlines()]
exact = json.loads((root / "exact_duplicate_groups.json").read_text())
near = json.loads((root / "near_duplicate_groups.json").read_text())
matrix = json.loads((root / "split_collision_matrix.json").read_text())
scan_summary = json.loads((root / "scan_summary.json").read_text())
gate = json.loads((root / "dedup_near_duplicate_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_dedup_near_duplicate_report.json").read_text())
privacy = json.loads((root / "dedup_near_duplicate_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.dedup_near_duplicate_scanner_summary.v1", summary
assert summary["gate_name"] == "dedup_near_duplicate_scanner_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["source_row_count"] == 10, summary
assert summary["training_row_count"] == 6, summary
assert summary["eval_row_count"] == 2, summary
assert summary["private_heldout_row_count"] == 2, summary
assert summary["pairwise_comparison_count"] == 45, summary
assert summary["dedup_row_feature_count"] == 10, summary
assert summary["exact_row_duplicate_group_count"] == 0, summary
assert summary["same_task_multi_product_group_count"] == 3, summary
assert summary["train_same_task_multi_product_group_count"] == 1, summary
assert summary["train_same_task_multi_product_row_count"] == 6, summary
assert summary["high_near_duplicate_pair_count"] >= 8, summary
assert summary["moderate_near_duplicate_pair_count"] >= summary["high_near_duplicate_pair_count"], summary
assert summary["cross_split_high_near_duplicate_pair_count"] == 2, summary
assert summary["train_eval_high_near_duplicate_pair_count"] == 0, summary
assert summary["train_private_high_near_duplicate_pair_count"] == 0, summary
assert summary["training_grade_dedup_pass_count"] == 0, summary
assert summary["near_duplicate_scanner_complete"] is True, summary
assert summary["split_isolation_high_similarity_passed"] is False, summary
assert summary["deduplication_passed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary

assert len(features) == 10, features
assert len(pairs) == 45, pairs
assert len(decisions) == 10, decisions
assert all(feature["contains_raw_text"] is False for feature in features), features
assert all(pair["contains_raw_text"] is False for pair in pairs), pairs
assert all(decision["contains_raw_text"] is False for decision in decisions), decisions
assert all(decision["training_grade_dedup_pass"] is False for decision in decisions), decisions

assert exact["schema_version"] == "forgeagent.exact_duplicate_groups.v1", exact
assert exact["contains_raw_text"] is False, exact
assert exact["contains_private_identifiers"] is False, exact
assert near["schema_version"] == "forgeagent.near_duplicate_groups.v1", near
assert near["contains_raw_text"] is False, near
assert near["contains_private_identifiers"] is False, near
assert len(near["same_task_multi_product_groups"]) == 3, near
assert matrix["schema_version"] == "forgeagent.dedup_split_collision_matrix.v1", matrix
assert scan_summary["source_row_count"] == summary["source_row_count"], scan_summary

assert gate["dedup_scanner_ready"] is True, gate
assert gate["near_duplicate_scanner_ready"] is True, gate
assert gate["pairwise_similarity_matrix_ready"] is True, gate
assert gate["split_collision_matrix_ready"] is True, gate
assert gate["hash_only_outputs"] is True, gate
assert gate["deduplication_passed"] is False, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert "same_task_multi_product_groups_require_bundle_policy" in gate["blocked_reasons"], gate
assert "public_benchmark_scan_incomplete" in gate["blocked_reasons"], gate
assert "cross_split_high_near_duplicate_pairs_present" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_dedup_near_duplicate_report.v1", public_report
assert public_report["source_row_count"] == 10, public_report
assert public_report["private_identifier_values_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["raw_text_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["prompt_content_included"] is False, public_report
assert public_report["withheld_eval_content_included"] is False, public_report
assert public_report["model_outputs_included"] is False, public_report
assert public_report["training_launch_allowed"] is False, public_report
assert public_report["remote_inference_invoked"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "forge-micro-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob
assert "hidden_tests" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["private_identifier_leak_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("dedup_near_duplicate_scanner_v1: OK")
print("source_row_count:", summary["source_row_count"])
print("pairwise_comparison_count:", summary["pairwise_comparison_count"])
print("same_task_multi_product_group_count:", summary["same_task_multi_product_group_count"])
print("train_same_task_multi_product_row_count:", summary["train_same_task_multi_product_row_count"])
print("high_near_duplicate_pair_count:", summary["high_near_duplicate_pair_count"])
print("training_grade_dedup_pass_count:", summary["training_grade_dedup_pass_count"])
print("deduplication_passed:", summary["deduplication_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.28 Dedup and Near-Duplicate Scanner" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.28 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Dedup and Near-Duplicate Scanner" docs/data/DEDUP_NEAR_DUPLICATE_SCANNER.md
grep -q "ADR-0054" docs/engineering/ADR_0054_DEDUP_NEAR_DUPLICATE_SCANNER.md

echo
echo "STEP29_28_DOCTOR_OK"

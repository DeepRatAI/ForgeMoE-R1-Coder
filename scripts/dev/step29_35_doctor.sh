#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.35 doctor ==="
python3 --version
echo

echo "=== Compile full public benchmark corpus materialization scan ==="
python3 -m compileall -q scripts/dev/run_full_public_benchmark_corpus_materialization_scan_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.34 source artifacts ==="
./scripts/dev/step29_34_doctor.sh
echo

echo "=== Enforce no local model or local training runtime for this gate ==="
if pgrep -af "ollama runner|local_transformers|torchrun|deepspeed|accelerate launch" >/tmp/forgemoe_step29_35_forbidden_local_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_35_forbidden_local_runtime_processes.txt
  echo "forbidden local model or local training runtime process detected"
  exit 1
fi
echo "forbidden_local_runtime_processes: none"
echo

echo "=== Run full public benchmark corpus materialization scan v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_full_public_benchmark_corpus_materialization_scan_v1.py
echo

RESULT_DIR="results/local/full_public_benchmark_corpus_materialization_scan_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/public_benchmark_full_corpus_source_manifest.jsonl"
test -f "${RESULT_DIR}/public_benchmark_full_corpus_file_fingerprints.jsonl"
test -f "${RESULT_DIR}/full_corpus_train_candidate_contamination_results.jsonl"
test -f "${RESULT_DIR}/full_corpus_streaming_budget_report.json"
test -f "${RESULT_DIR}/step29_35_training_release_policy_delta.json"
test -f "${RESULT_DIR}/full_public_benchmark_corpus_materialization_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_full_public_benchmark_corpus_materialization_report.json"
test -f "${RESULT_DIR}/full_public_benchmark_corpus_materialization_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/full_public_benchmark_corpus_materialization_scan_v1")
summary = json.loads((root / "summary.json").read_text())
sources = [
    json.loads(line)
    for line in (root / "public_benchmark_full_corpus_source_manifest.jsonl").read_text().splitlines()
]
files = [
    json.loads(line)
    for line in (root / "public_benchmark_full_corpus_file_fingerprints.jsonl").read_text().splitlines()
]
overlaps = [
    json.loads(line)
    for line in (root / "full_corpus_train_candidate_contamination_results.jsonl").read_text().splitlines()
]
budget = json.loads((root / "full_corpus_streaming_budget_report.json").read_text())
policy = json.loads((root / "step29_35_training_release_policy_delta.json").read_text())
gate = json.loads((root / "full_public_benchmark_corpus_materialization_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_full_public_benchmark_corpus_materialization_report.json").read_text())
privacy = json.loads((root / "full_public_benchmark_corpus_materialization_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.full_public_benchmark_corpus_materialization_summary.v1", summary
assert summary["gate_name"] == "full_public_benchmark_corpus_materialization_scan_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["benchmark_registry_entry_count"] == 12, summary
assert summary["benchmark_complete_scan_count"] == 12, summary
assert summary["source_file_count"] >= 100, summary
assert summary["ok_file_count"] == summary["source_file_count"], summary
assert summary["failed_file_count"] == 0, summary
assert summary["expected_total_bytes"] > 1_000_000_000, summary
assert summary["observed_total_bytes_hashed"] > 1_000_000_000, summary
assert summary["content_bytes_persisted"] == 0, summary
assert summary["full_public_benchmark_corpus_scan_complete"] is True, summary
assert summary["exact_full_public_benchmark_corpus_collision_count"] == 0, summary
assert summary["training_payload_materialization_authorized"] is False, summary
assert summary["training_grade_candidate_after_step29_35_count"] == 0, summary
assert summary["updated_release_policy_passed_requirement_count"] == 7, summary
assert summary["updated_release_policy_failed_requirement_count"] == 1, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["downloads_large_dataset"] is True, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["next_recommended_step"] == "step29_36_training_payload_materialization_authorization_v1", summary

assert len(sources) >= 12, sources
assert all(row["schema_version"] == "forgeagent.public_benchmark_full_corpus_source_manifest.v1" for row in sources), sources
assert all(row["metadata_ok"] is True for row in sources), sources
assert len(files) == summary["source_file_count"], (len(files), summary)
for row in files:
    assert row["schema_version"] == "forgeagent.public_benchmark_full_corpus_file_fingerprint.v1", row
    assert row["ok"] is True, row
    assert row["bytes_read"] >= 0, row
    assert row["content_sha256"], row
    assert row["content_persisted"] is False, row
    assert row["contains_raw_text"] is False, row
    assert row["contains_private_identifiers"] is False, row

assert len(overlaps) == 48, overlaps
assert all(row["exact_hash_collision"] is False for row in overlaps), overlaps
assert all(row["exact_hash_collision_count"] == 0 for row in overlaps), overlaps
assert all(row["contains_raw_text"] is False for row in overlaps), overlaps

assert budget["schema_version"] == "forgeagent.full_public_benchmark_corpus_streaming_budget_report.v1", budget
assert budget["budget_exceeded"] is False, budget
assert budget["ok_file_count"] == summary["source_file_count"], budget
assert budget["failed_file_count"] == 0, budget
assert budget["observed_total_bytes_hashed"] == summary["observed_total_bytes_hashed"], budget
assert budget["content_persisted"] is False, budget

assert policy["schema_version"] == "forgeagent.step29_35_training_release_policy_delta.v1", policy
assert policy["passed_requirement_count"] == 7, policy
assert policy["failed_requirement_count"] == 1, policy
assert policy["training_grade_data_release_allowed"] is False, policy

assert gate["schema_version"] == "forgeagent.full_public_benchmark_corpus_materialization_gate_decision.v1", gate
assert gate["full_public_benchmark_corpus_scan_complete"] is True, gate
assert gate["benchmark_complete_scan_count"] == 12, gate
assert gate["exact_full_public_benchmark_corpus_collision_count"] == 0, gate
assert gate["content_bytes_persisted"] == 0, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert "full_public_benchmark_corpus_scan_incomplete" in gate["resolved_previous_blockers"], gate
assert gate["blocked_reasons"] == ["training_payload_materialization_not_authorized"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_full_public_benchmark_corpus_materialization_report.v1", public_report
assert public_report["full_public_benchmark_corpus_scan_complete"] is True, public_report
assert public_report["raw_benchmark_tasks_included"] is False, public_report
assert public_report["raw_task_ids_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["raw_text_included"] is False, public_report
assert public_report["content_hashes_included"] is False, public_report
assert public_report["path_values_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["hidden_test_content_included"] is False, public_report
assert public_report["private_identifier_values_included"] is False, public_report
assert public_report["model_outputs_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
for marker in ("diff --git", "assertEqual", "hidden_tests", "golden.patch", "content_sha256", "path_sha256"):
    assert marker not in public_blob, (marker, public_blob)

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("full_public_benchmark_corpus_materialization_scan_v1: OK")
print("source_file_count:", summary["source_file_count"])
print("observed_total_bytes_hashed:", summary["observed_total_bytes_hashed"])
print("fresh_streamed_file_count:", summary["fresh_streamed_file_count"])
print("reused_cached_file_count:", summary["reused_cached_file_count"])
print("exact_full_public_benchmark_corpus_collision_count:", summary["exact_full_public_benchmark_corpus_collision_count"])
print("updated_release_policy_passed_requirement_count:", summary["updated_release_policy_passed_requirement_count"])
print("updated_release_policy_failed_requirement_count:", summary["updated_release_policy_failed_requirement_count"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.35 Full Public Benchmark Corpus Materialization" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.35 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Full Public Benchmark Corpus Materialization" docs/data/FULL_PUBLIC_BENCHMARK_CORPUS_MATERIALIZATION_SCAN.md
grep -q "ADR-0061" docs/engineering/ADR_0061_FULL_PUBLIC_BENCHMARK_CORPUS_MATERIALIZATION_SCAN.md

echo
echo "STEP29_35_DOCTOR_OK"

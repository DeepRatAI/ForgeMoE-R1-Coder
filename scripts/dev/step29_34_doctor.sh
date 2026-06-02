#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.34 doctor ==="
python3 --version
echo

echo "=== Compile bounded public benchmark snapshot fingerprinting ==="
python3 -m compileall -q scripts/dev/run_bounded_public_benchmark_snapshot_fingerprinting_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.33 source artifacts ==="
./scripts/dev/step29_33_doctor.sh
echo

echo "=== Network snapshot preflight ==="
python3 - <<'PY'
import os
import subprocess
import urllib.request
with urllib.request.urlopen("https://huggingface.co/api/datasets/openai/openai_humaneval", timeout=20) as response:
    assert response.status == 200, response.status
token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not token:
    try:
        token = subprocess.check_output(["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        token = ""
headers = {"User-Agent": "ForgeMoE-Coder-Step29.34/1.0"}
if token:
    headers["Authorization"] = f"Bearer {token}"
request = urllib.request.Request("https://api.github.com/repos/openai/human-eval", headers=headers)
with urllib.request.urlopen(request, timeout=20) as response:
    assert response.status == 200, response.status
print("snapshot_network_preflight: OK")
PY
echo

echo "=== Enforce no local model or local training runtime for this gate ==="
if pgrep -af "ollama runner|local_transformers|torchrun|deepspeed|accelerate launch" >/tmp/forgemoe_step29_34_forbidden_local_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_34_forbidden_local_runtime_processes.txt
  echo "forbidden local model or local training runtime process detected"
  exit 1
fi
echo "forbidden_local_runtime_processes: none"
echo

echo "=== Run bounded public benchmark snapshot fingerprinting v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_bounded_public_benchmark_snapshot_fingerprinting_v1.py
echo

RESULT_DIR="results/local/bounded_public_benchmark_snapshot_fingerprinting_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/public_benchmark_snapshot_fingerprints.jsonl"
test -f "${RESULT_DIR}/public_benchmark_content_prefix_fingerprints.jsonl"
test -f "${RESULT_DIR}/benchmark_snapshot_train_candidate_overlap_results.jsonl"
test -f "${RESULT_DIR}/bounded_snapshot_fingerprinting_budget_report.json"
test -f "${RESULT_DIR}/step29_34_training_release_policy_delta.json"
test -f "${RESULT_DIR}/public_benchmark_snapshot_fingerprinting_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_public_benchmark_snapshot_fingerprinting_report.json"
test -f "${RESULT_DIR}/public_benchmark_snapshot_fingerprinting_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/bounded_public_benchmark_snapshot_fingerprinting_v1")
summary = json.loads((root / "summary.json").read_text())
snapshots = [
    json.loads(line)
    for line in (root / "public_benchmark_snapshot_fingerprints.jsonl").read_text().splitlines()
]
prefixes = [
    json.loads(line)
    for line in (root / "public_benchmark_content_prefix_fingerprints.jsonl").read_text().splitlines()
]
overlaps = [
    json.loads(line)
    for line in (root / "benchmark_snapshot_train_candidate_overlap_results.jsonl").read_text().splitlines()
]
budget = json.loads((root / "bounded_snapshot_fingerprinting_budget_report.json").read_text())
policy = json.loads((root / "step29_34_training_release_policy_delta.json").read_text())
gate = json.loads((root / "public_benchmark_snapshot_fingerprinting_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_public_benchmark_snapshot_fingerprinting_report.json").read_text())
privacy = json.loads((root / "public_benchmark_snapshot_fingerprinting_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.bounded_public_benchmark_snapshot_fingerprinting_summary.v1", summary
assert summary["gate_name"] == "bounded_public_benchmark_snapshot_fingerprinting_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["benchmark_snapshot_count"] == 12, summary
assert summary["bounded_snapshot_complete_count"] == 12, summary
assert summary["bounded_snapshot_fingerprinting_complete"] is True, summary
assert summary["hf_revision_fingerprinted_count"] >= 11, summary
assert summary["hf_sibling_manifest_fingerprinted_count"] >= 11, summary
assert summary["github_tree_fingerprinted_count"] >= 9, summary
assert summary["content_prefix_fingerprint_count"] >= 12, summary
assert summary["successful_content_prefix_fingerprint_count"] >= 12, summary
assert summary["content_prefix_bytes_read"] > 0, summary
assert summary["content_prefix_bytes_persisted"] == 0, summary
assert summary["budget_exceeded"] is False, summary
assert summary["public_benchmark_direct_training_allowed_count"] == 0, summary
assert summary["snapshot_train_candidate_overlap_pair_count"] == 48, summary
assert summary["exact_public_benchmark_snapshot_collision_count"] == 0, summary
assert summary["high_public_benchmark_snapshot_similarity_count"] == 0, summary
assert summary["full_public_benchmark_corpus_scan_complete"] is False, summary
assert summary["training_payload_materialization_authorized"] is False, summary
assert summary["training_grade_candidate_after_step29_34_count"] == 0, summary
assert summary["updated_release_policy_passed_requirement_count"] == 8, summary
assert summary["updated_release_policy_failed_requirement_count"] == 2, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["next_recommended_step"] == "step29_35_full_public_benchmark_corpus_materialization_and_contamination_scan_v1", summary

assert len(snapshots) == 12, snapshots
for row in snapshots:
    assert row["schema_version"] == "forgeagent.public_benchmark_snapshot_fingerprint.v1", row
    assert row["policy"] == "reference_or_eval_only", row
    assert row["never_train_direct"] is True, row
    assert row["bounded_snapshot_complete"] is True, row
    assert row["selected_content_fingerprint_count"] >= 1, row
    assert row["successful_content_fingerprint_count"] >= 1, row
    assert row["content_persisted"] is False, row
    assert row["full_corpus_content_downloaded"] is False, row
    assert row["full_corpus_content_fingerprinted"] is False, row
    assert row["contains_raw_benchmark_tasks"] is False, row
    assert row["contains_private_identifiers"] is False, row

assert len(prefixes) >= 12, prefixes
for row in prefixes:
    assert row["schema_version"] == "forgeagent.public_benchmark_content_prefix_fingerprint.v1", row
    assert row["bytes_read"] >= 0, row
    assert row["max_prefix_bytes"] <= 32768, row
    assert row["content_persisted"] is False, row
    assert row["contains_raw_text"] is False, row
    assert row["contains_private_identifiers"] is False, row

assert len(overlaps) == 48, overlaps
assert all(row["exact_hash_collision"] is False for row in overlaps), overlaps
assert all(row["exact_hash_collision_count"] == 0 for row in overlaps), overlaps
assert all(row["high_token_similarity"] is False for row in overlaps), overlaps
assert all(row["contains_raw_text"] is False for row in overlaps), overlaps

assert budget["schema_version"] == "forgeagent.bounded_public_benchmark_snapshot_budget_report.v1", budget
assert budget["budget_exceeded"] is False, budget
assert budget["observed_total_content_bytes_read"] == summary["content_prefix_bytes_read"], budget
assert budget["observed_total_content_bytes_read"] <= budget["max_total_content_bytes"], budget
assert budget["content_persisted"] is False, budget

assert policy["schema_version"] == "forgeagent.step29_34_training_release_policy_delta.v1", policy
assert policy["passed_requirement_count"] == 8, policy
assert policy["failed_requirement_count"] == 2, policy
assert policy["training_grade_data_release_allowed"] is False, policy

assert gate["schema_version"] == "forgeagent.public_benchmark_snapshot_fingerprinting_gate_decision.v1", gate
assert gate["bounded_snapshot_fingerprinting_complete"] is True, gate
assert gate["benchmark_snapshot_count"] == 12, gate
assert gate["bounded_snapshot_complete_count"] == 12, gate
assert gate["exact_public_benchmark_snapshot_collision_count"] == 0, gate
assert gate["high_public_benchmark_snapshot_similarity_count"] == 0, gate
assert gate["content_prefix_bytes_persisted"] == 0, gate
assert gate["budget_exceeded"] is False, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert "full_public_benchmark_corpus_scan_incomplete" in gate["blocked_reasons"], gate
assert "training_payload_materialization_not_authorized" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_public_benchmark_snapshot_fingerprinting_report.v1", public_report
assert public_report["bounded_snapshot_fingerprinting_complete"] is True, public_report
assert public_report["raw_benchmark_tasks_included"] is False, public_report
assert public_report["raw_task_ids_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["raw_text_included"] is False, public_report
assert public_report["content_prefix_hashes_included"] is False, public_report
assert public_report["path_values_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["hidden_test_content_included"] is False, public_report
assert public_report["private_identifier_values_included"] is False, public_report
assert public_report["model_outputs_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
for marker in ("diff --git", "assertEqual", "hidden_tests", "golden.patch", "content_prefix_sha256"):
    assert marker not in public_blob, (marker, public_blob)

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("bounded_public_benchmark_snapshot_fingerprinting_v1: OK")
print("benchmark_snapshot_count:", summary["benchmark_snapshot_count"])
print("bounded_snapshot_complete_count:", summary["bounded_snapshot_complete_count"])
print("content_prefix_fingerprint_count:", summary["content_prefix_fingerprint_count"])
print("successful_content_prefix_fingerprint_count:", summary["successful_content_prefix_fingerprint_count"])
print("content_prefix_bytes_read:", summary["content_prefix_bytes_read"])
print("updated_release_policy_passed_requirement_count:", summary["updated_release_policy_passed_requirement_count"])
print("updated_release_policy_failed_requirement_count:", summary["updated_release_policy_failed_requirement_count"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.34 Public Benchmark Snapshot Fingerprinting" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.34 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Bounded Public Benchmark Snapshot Fingerprinting" docs/data/BOUNDED_PUBLIC_BENCHMARK_SNAPSHOT_FINGERPRINTING.md
grep -q "ADR-0060" docs/engineering/ADR_0060_BOUNDED_PUBLIC_BENCHMARK_SNAPSHOT_FINGERPRINTING.md

echo
echo "STEP29_34_DOCTOR_OK"

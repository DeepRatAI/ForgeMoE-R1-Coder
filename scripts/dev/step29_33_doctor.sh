#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.33 doctor ==="
python3 --version
echo

echo "=== Compile public benchmark corpus scan/license attestation ==="
python3 -m compileall -q scripts/dev/run_public_benchmark_corpus_scan_license_attestation_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.32 source artifacts ==="
./scripts/dev/step29_32_doctor.sh
echo

echo "=== Network metadata preflight ==="
python3 - <<'PY'
import urllib.request
with urllib.request.urlopen("https://huggingface.co/api/datasets/openai/openai_humaneval", timeout=20) as response:
    assert response.status == 200, response.status
print("metadata_network_preflight: OK")
PY
echo

echo "=== Enforce no local model or local training runtime for this gate ==="
if pgrep -af "ollama runner|local_transformers|torchrun|deepspeed|accelerate launch" >/tmp/forgemoe_step29_33_forbidden_local_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_33_forbidden_local_runtime_processes.txt
  echo "forbidden local model or local training runtime process detected"
  exit 1
fi
echo "forbidden_local_runtime_processes: none"
echo

echo "=== Run public benchmark corpus scan/license attestation v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_public_benchmark_corpus_scan_license_attestation_v1.py
echo

RESULT_DIR="results/local/public_benchmark_corpus_scan_license_attestation_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/public_benchmark_source_attestations.jsonl"
test -f "${RESULT_DIR}/benchmark_metadata_train_candidate_scan_results.jsonl"
test -f "${RESULT_DIR}/forge_internal_train_candidate_license_attestation.json"
test -f "${RESULT_DIR}/public_benchmark_full_corpus_scan_plan.json"
test -f "${RESULT_DIR}/step29_33_training_release_policy_delta.json"
test -f "${RESULT_DIR}/public_benchmark_corpus_scan_license_attestation_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_public_benchmark_corpus_scan_license_attestation_report.json"
test -f "${RESULT_DIR}/public_benchmark_corpus_scan_license_attestation_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/public_benchmark_corpus_scan_license_attestation_v1")
summary = json.loads((root / "summary.json").read_text())
attestations = [
    json.loads(line)
    for line in (root / "public_benchmark_source_attestations.jsonl").read_text().splitlines()
]
scan_rows = [
    json.loads(line)
    for line in (root / "benchmark_metadata_train_candidate_scan_results.jsonl").read_text().splitlines()
]
license_attestation = json.loads((root / "forge_internal_train_candidate_license_attestation.json").read_text())
corpus_plan = json.loads((root / "public_benchmark_full_corpus_scan_plan.json").read_text())
policy = json.loads((root / "step29_33_training_release_policy_delta.json").read_text())
gate = json.loads((root / "public_benchmark_corpus_scan_license_attestation_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_public_benchmark_corpus_scan_license_attestation_report.json").read_text())
privacy = json.loads((root / "public_benchmark_corpus_scan_license_attestation_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.public_benchmark_corpus_scan_license_attestation_summary.v1", summary
assert summary["gate_name"] == "public_benchmark_corpus_scan_license_attestation_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["benchmark_registry_entry_count"] == 12, summary
assert summary["official_metadata_source_count"] == 12, summary
assert summary["metadata_fetch_success_count"] == 12, summary
assert summary["official_metadata_attestation_complete"] is True, summary
assert summary["explicit_dataset_license_count"] >= 7, summary
assert summary["ambiguous_or_unresolved_dataset_license_count"] == 3, summary
assert summary["license_attestation_complete"] is True, summary
assert summary["train_candidate_license_attestation_passed"] is True, summary
assert summary["license_policy_upgraded_beyond_scaffold_only"] is True, summary
assert summary["public_benchmark_direct_training_allowed_count"] == 0, summary
assert summary["full_public_benchmark_corpus_scan_complete"] is False, summary
assert summary["full_corpus_downloaded_count"] == 0, summary
assert summary["full_corpus_fingerprinted_count"] == 0, summary
assert summary["bounded_metadata_scan_pair_count"] == 48, summary
assert summary["exact_metadata_collision_count"] == 0, summary
assert summary["high_metadata_similarity_count"] == 0, summary
assert summary["training_payload_materialization_authorized"] is False, summary
assert summary["training_grade_candidate_after_step29_33_count"] == 0, summary
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
assert summary["next_recommended_step"] == "step29_34_bounded_public_benchmark_snapshot_fingerprinting_v1", summary

assert len(attestations) == 12, attestations
for row in attestations:
    assert row["schema_version"] == "forgeagent.public_benchmark_source_attestation.v1", row
    assert row["official_metadata_verified"] is True, row
    assert row["bounded_metadata_scan_complete"] is True, row
    assert row["policy"] == "reference_or_eval_only", row
    assert row["never_train_direct"] is True, row
    assert row["direct_training_allowed"] is False, row
    assert row["full_corpus_content_downloaded"] is False, row
    assert row["full_corpus_content_fingerprinted"] is False, row
    assert row["contains_raw_benchmark_tasks"] is False, row
    assert row["contains_private_identifiers"] is False, row

assert len(scan_rows) == 48, scan_rows
assert all(row["exact_hash_collision"] is False for row in scan_rows), scan_rows
assert all(row["high_metadata_similarity"] is False for row in scan_rows), scan_rows
assert all(row["contains_raw_text"] is False for row in scan_rows), scan_rows

assert license_attestation["schema_version"] == "forgeagent.forge_internal_train_candidate_license_attestation.v1", license_attestation
assert license_attestation["oracle_certified_train_candidate_count"] == 4, license_attestation
assert license_attestation["uses_raw_public_benchmark_content"] is False, license_attestation
assert license_attestation["uses_external_repository_snapshot"] is False, license_attestation
assert license_attestation["uses_private_heldout_content"] is False, license_attestation
assert license_attestation["license_policy_upgraded_beyond_scaffold_only"] is True, license_attestation
assert license_attestation["training_payload_materialization_authorized"] is False, license_attestation

assert corpus_plan["schema_version"] == "forgeagent.public_benchmark_full_corpus_scan_plan.v1", corpus_plan
assert corpus_plan["bounded_metadata_scan_complete"] is True, corpus_plan
assert corpus_plan["full_public_benchmark_corpus_scan_complete"] is False, corpus_plan
assert corpus_plan["contains_raw_benchmark_tasks"] is False, corpus_plan

assert policy["schema_version"] == "forgeagent.step29_33_training_release_policy_delta.v1", policy
assert policy["passed_requirement_count"] == 8, policy
assert policy["failed_requirement_count"] == 2, policy
assert policy["training_grade_data_release_allowed"] is False, policy

assert gate["schema_version"] == "forgeagent.public_benchmark_corpus_scan_license_attestation_gate_decision.v1", gate
assert gate["official_metadata_attestation_complete"] is True, gate
assert gate["license_attestation_complete"] is True, gate
assert gate["train_candidate_license_attestation_passed"] is True, gate
assert gate["full_public_benchmark_corpus_scan_complete"] is False, gate
assert gate["public_benchmark_direct_training_allowed_count"] == 0, gate
assert gate["training_grade_candidate_after_step29_33_count"] == 0, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert "license_policy_still_scaffold_only" in gate["resolved_previous_blockers"], gate
assert "full_public_benchmark_corpus_scan_incomplete" in gate["blocked_reasons"], gate
assert "training_payload_materialization_not_authorized" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_public_benchmark_corpus_scan_license_attestation_report.v1", public_report
assert public_report["benchmark_registry_entry_count"] == 12, public_report
assert public_report["official_metadata_attestation_complete"] is True, public_report
assert public_report["raw_benchmark_tasks_included"] is False, public_report
assert public_report["raw_task_ids_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["raw_text_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["hidden_test_content_included"] is False, public_report
assert public_report["private_identifier_values_included"] is False, public_report
assert public_report["model_outputs_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
for marker in ("diff --git", "assertEqual", "hidden_tests", "golden.patch", "raw_model_output"):
    assert marker not in public_blob, (marker, public_blob)

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("public_benchmark_corpus_scan_license_attestation_v1: OK")
print("benchmark_registry_entry_count:", summary["benchmark_registry_entry_count"])
print("metadata_fetch_success_count:", summary["metadata_fetch_success_count"])
print("explicit_dataset_license_count:", summary["explicit_dataset_license_count"])
print("ambiguous_or_unresolved_dataset_license_count:", summary["ambiguous_or_unresolved_dataset_license_count"])
print("updated_release_policy_passed_requirement_count:", summary["updated_release_policy_passed_requirement_count"])
print("updated_release_policy_failed_requirement_count:", summary["updated_release_policy_failed_requirement_count"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.33 Public Benchmark Corpus Scan and License Attestation" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.33 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Public Benchmark Corpus Scan and License Attestation" docs/data/PUBLIC_BENCHMARK_CORPUS_SCAN_LICENSE_ATTESTATION.md
grep -q "ADR-0059" docs/engineering/ADR_0059_PUBLIC_BENCHMARK_CORPUS_SCAN_LICENSE_ATTESTATION.md

echo
echo "STEP29_33_DOCTOR_OK"

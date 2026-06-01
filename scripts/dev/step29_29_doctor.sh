#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.29 doctor ==="
python3 --version
echo

echo "=== Compile task-family bundle/oracle-quality gate ==="
python3 -m compileall -q scripts/dev/run_task_family_bundle_oracle_quality_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.28 source artifacts ==="
./scripts/dev/step29_28_doctor.sh
echo

echo "=== Enforce no local model, training, large dataset download, or remote inference execution for this gate ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|torchrun|deepspeed|accelerate launch|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_29_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_29_forbidden_runtime_processes.txt
  echo "forbidden model runtime, training, or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run task-family bundle/oracle-quality gate v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_task_family_bundle_oracle_quality_v1.py
echo

RESULT_DIR="results/local/task_family_bundle_oracle_quality_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/task_family_bundle_manifest.json"
test -f "${RESULT_DIR}/split_bundle_isolation_report.json"
test -f "${RESULT_DIR}/oracle_quality_certifications.jsonl"
test -f "${RESULT_DIR}/task_oracle_quality_report.json"
test -f "${RESULT_DIR}/training_candidate_decisions.jsonl"
test -f "${RESULT_DIR}/task_family_bundle_oracle_quality_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_task_family_bundle_oracle_quality_report.json"
test -f "${RESULT_DIR}/task_family_bundle_oracle_quality_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/task_family_bundle_oracle_quality_v1")
summary = json.loads((root / "summary.json").read_text())
bundle_manifest = json.loads((root / "task_family_bundle_manifest.json").read_text())
split_report = json.loads((root / "split_bundle_isolation_report.json").read_text())
certs = [json.loads(line) for line in (root / "oracle_quality_certifications.jsonl").read_text().splitlines()]
task_oracle = json.loads((root / "task_oracle_quality_report.json").read_text())
candidate_decisions = [json.loads(line) for line in (root / "training_candidate_decisions.jsonl").read_text().splitlines()]
gate = json.loads((root / "task_family_bundle_oracle_quality_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_task_family_bundle_oracle_quality_report.json").read_text())
privacy = json.loads((root / "task_family_bundle_oracle_quality_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.task_family_bundle_oracle_quality_summary.v1", summary
assert summary["gate_name"] == "task_family_bundle_oracle_quality_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["source_row_count"] == 10, summary
assert summary["training_row_count"] == 6, summary
assert summary["eval_row_count"] == 2, summary
assert summary["private_heldout_row_count"] == 2, summary
assert summary["bundle_count"] == 3, summary
assert summary["train_bundle_count"] == 1, summary
assert summary["eval_bundle_count"] == 1, summary
assert summary["private_heldout_bundle_count"] == 1, summary
assert summary["cross_split_task_bundle_count"] == 0, summary
assert summary["same_task_multi_product_bundle_count"] == 3, summary
assert summary["same_task_multi_product_blocker_resolved_row_count"] == 10, summary
assert summary["train_bundle_isolation_passed"] is True, summary
assert summary["eval_private_distinctness_passed"] is False, summary
assert summary["split_bundle_isolation_passed"] is False, summary
assert summary["eval_private_high_near_duplicate_pair_count"] == 2, summary
assert summary["train_eval_high_near_duplicate_pair_count"] == 0, summary
assert summary["train_private_high_near_duplicate_pair_count"] == 0, summary
assert summary["task_oracle_certified_count"] == 3, summary
assert summary["row_task_oracle_certified_count"] == 10, summary
assert summary["row_training_payload_oracle_certified_count"] == 4, summary
assert summary["withheld_reference_row_count"] == 6, summary
assert summary["training_grade_candidate_after_step29_29_count"] == 0, summary
assert summary["task_family_bundle_policy_complete"] is True, summary
assert summary["oracle_quality_certification_complete"] is True, summary
assert summary["private_generalization_claim_allowed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary

assert bundle_manifest["schema_version"] == "forgeagent.task_family_bundle_manifest.v1", bundle_manifest
assert bundle_manifest["contains_raw_text"] is False, bundle_manifest
assert bundle_manifest["contains_private_identifiers"] is False, bundle_manifest
assert len(bundle_manifest["bundles"]) == 3, bundle_manifest
assert all(bundle["bundle_policy_pass"] is True for bundle in bundle_manifest["bundles"]), bundle_manifest
assert sorted(bundle["row_count"] for bundle in bundle_manifest["bundles"]) == [2, 2, 6], bundle_manifest

assert split_report["schema_version"] == "forgeagent.split_bundle_isolation_report.v1", split_report
assert split_report["train_bundle_isolation_passed"] is True, split_report
assert split_report["eval_private_distinctness_passed"] is False, split_report
assert split_report["split_bundle_isolation_passed"] is False, split_report
assert split_report["contains_raw_text"] is False, split_report
assert split_report["contains_private_identifiers"] is False, split_report

assert len(certs) == 10, certs
assert all(cert["task_oracle_certified"] is True for cert in certs), certs
assert all(cert["contains_raw_text"] is False for cert in certs), certs
assert all(cert["contains_private_identifiers"] is False for cert in certs), certs
assert sum(1 for cert in certs if cert["row_training_payload_oracle_certified"]) == 4, certs

assert task_oracle["schema_version"] == "forgeagent.task_oracle_quality_report.v1", task_oracle
assert task_oracle["oracle_task_count"] == 3, task_oracle
assert task_oracle["oracle_task_certified_count"] == 3, task_oracle
assert task_oracle["minimum_observed_oracle_strength_score"] == 1.0, task_oracle
assert task_oracle["hidden_test_isolation_passed"] is True, task_oracle
assert task_oracle["contains_raw_text"] is False, task_oracle
assert task_oracle["contains_private_identifiers"] is False, task_oracle

assert len(candidate_decisions) == 10, candidate_decisions
assert sum(1 for row in candidate_decisions if row["same_task_multi_product_blocker_resolved"]) == 10, candidate_decisions
assert sum(1 for row in candidate_decisions if row["row_training_payload_oracle_certified"]) == 4, candidate_decisions
assert all(row["training_grade_candidate_after_step29_29"] is False for row in candidate_decisions), candidate_decisions
assert all(row["contains_raw_text"] is False for row in candidate_decisions), candidate_decisions
assert all(row["contains_private_identifiers"] is False for row in candidate_decisions), candidate_decisions

assert gate["task_family_bundle_policy_ready"] is True, gate
assert gate["oracle_quality_certification_ready"] is True, gate
assert gate["task_family_bundle_policy_complete"] is True, gate
assert gate["oracle_quality_certification_complete"] is True, gate
assert gate["train_bundle_isolation_passed"] is True, gate
assert gate["eval_private_distinctness_passed"] is False, gate
assert gate["split_bundle_isolation_passed"] is False, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert "eval_private_high_similarity_requires_harder_private_eval_generation" in gate["blocked_reasons"], gate
assert "public_benchmark_scan_incomplete" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_task_family_bundle_oracle_quality_report.v1", public_report
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

print("task_family_bundle_oracle_quality_v1: OK")
print("source_row_count:", summary["source_row_count"])
print("bundle_count:", summary["bundle_count"])
print("same_task_multi_product_blocker_resolved_row_count:", summary["same_task_multi_product_blocker_resolved_row_count"])
print("row_training_payload_oracle_certified_count:", summary["row_training_payload_oracle_certified_row_count"] if "row_training_payload_oracle_certified_row_count" in summary else summary["row_training_payload_oracle_certified_count"])
print("training_grade_candidate_after_step29_29_count:", summary["training_grade_candidate_after_step29_29_count"])
print("split_bundle_isolation_passed:", summary["split_bundle_isolation_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.29 Task-Family Bundle and Oracle-Quality Gate" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.29 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Task-Family Bundle and Oracle-Quality Gate" docs/data/TASK_FAMILY_BUNDLE_ORACLE_QUALITY_GATE.md
grep -q "ADR-0055" docs/engineering/ADR_0055_TASK_FAMILY_BUNDLE_ORACLE_QUALITY_GATE.md

echo
echo "STEP29_29_DOCTOR_OK"

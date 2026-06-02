#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.32 doctor ==="
python3 --version
echo

echo "=== Compile hardened oracle quality/data release integration ==="
python3 -m compileall -q scripts/dev/run_hardened_oracle_quality_data_release_integration_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.31 source artifacts ==="
./scripts/dev/step29_31_doctor.sh
echo

echo "=== Enforce no local model or local training runtime for this gate ==="
if pgrep -af "ollama runner|local_transformers|torchrun|deepspeed|accelerate launch" >/tmp/forgemoe_step29_32_forbidden_local_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_32_forbidden_local_runtime_processes.txt
  echo "forbidden local model or local training runtime process detected"
  exit 1
fi
echo "forbidden_local_runtime_processes: none"
echo

echo "=== Run hardened oracle quality/data release integration v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_hardened_oracle_quality_data_release_integration_v1.py
echo

RESULT_DIR="results/local/hardened_oracle_quality_data_release_integration_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/hardened_oracle_quality_certifications.jsonl"
test -f "${RESULT_DIR}/hardened_data_release_decisions.jsonl"
test -f "${RESULT_DIR}/hardened_split_isolation_report.json"
test -f "${RESULT_DIR}/hardened_training_release_policy.json"
test -f "${RESULT_DIR}/hardened_oracle_quality_report.json"
test -f "${RESULT_DIR}/hardened_oracle_quality_data_release_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_hardened_oracle_quality_data_release_report.json"
test -f "${RESULT_DIR}/hardened_oracle_quality_data_release_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/hardened_oracle_quality_data_release_integration_v1")
summary = json.loads((root / "summary.json").read_text())
certs = [json.loads(line) for line in (root / "hardened_oracle_quality_certifications.jsonl").read_text().splitlines()]
decisions = [json.loads(line) for line in (root / "hardened_data_release_decisions.jsonl").read_text().splitlines()]
split_report = json.loads((root / "hardened_split_isolation_report.json").read_text())
release_policy = json.loads((root / "hardened_training_release_policy.json").read_text())
oracle_report = json.loads((root / "hardened_oracle_quality_report.json").read_text())
gate = json.loads((root / "hardened_oracle_quality_data_release_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_hardened_oracle_quality_data_release_report.json").read_text())
privacy = json.loads((root / "hardened_oracle_quality_data_release_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.hardened_oracle_quality_data_release_summary.v1", summary
assert summary["gate_name"] == "hardened_oracle_quality_data_release_integration_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["task_count"] == 12, summary
assert summary["oracle_certified_task_count"] == 12, summary
assert summary["train_oracle_certified_task_count"] == 4, summary
assert summary["oracle_certified_train_candidate_count"] == 4, summary
assert summary["training_grade_candidate_after_step29_32_count"] == 0, summary
assert summary["release_policy_integrated"] is True, summary
assert summary["release_policy_passed_requirement_count"] == 6, summary
assert summary["release_policy_failed_requirement_count"] == 3, summary
assert summary["new_hardened_tasks_oracle_certification_blocker_resolved"] is True, summary
assert summary["final_training_release_policy_integration_blocker_resolved"] is True, summary
assert summary["full_public_benchmark_corpus_scan_complete"] is False, summary
assert summary["license_policy_upgraded_beyond_scaffold_only"] is False, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["next_recommended_step"] == "step29_33_public_benchmark_corpus_scan_and_license_attestation_v1", summary

assert len(certs) == 12, certs
for cert in certs:
    assert cert["schema_version"] == "forgeagent.hardened_oracle_quality_certification.v1", cert
    assert cert["oracle_certified"] is True, cert
    assert cert["oracle_strength_score"] == 1.0, cert
    assert cert["criterion_pass_count"] == cert["criterion_required_count"], cert
    assert cert["criterion_required_count"] >= 15, cert
    assert cert["contains_raw_text"] is False, cert
    assert cert["contains_private_identifiers"] is False, cert
    assert set(cert["patch_sha256s"]) == {"golden", "public_overfit", "rejected", "semantic_noop", "wrong_file"}, cert

assert len(decisions) == 12, decisions
train_decisions = [row for row in decisions if row["split"] == "train"]
non_train_decisions = [row for row in decisions if row["split"] != "train"]
assert len(train_decisions) == 4, decisions
assert len(non_train_decisions) == 8, decisions
for row in train_decisions:
    assert row["oracle_certified_train_candidate"] is True, row
    assert row["training_grade_candidate_after_step29_32"] is False, row
    assert row["training_export_allowed"] is False, row
    assert row["release_class"] == "oracle_certified_train_candidate_blocked", row
    assert "full_public_benchmark_corpus_scan_incomplete" in row["blocked_reasons"], row
    assert "license_policy_still_scaffold_only" in row["blocked_reasons"], row
    assert "training_payload_materialization_not_authorized" in row["blocked_reasons"], row
for row in non_train_decisions:
    assert row["oracle_certified_train_candidate"] is False, row
    assert row["training_export_allowed"] is False, row
    assert row["release_class"] == "never_train_eval_or_heldout_reference", row
    assert "not_train_split" in row["blocked_reasons"], row

assert split_report["schema_version"] == "forgeagent.hardened_split_isolation_report.v1", split_report
assert split_report["train_release_split_isolation_passed"] is True, split_report
assert split_report["cross_split_task_hash_overlap_count"] == 0, split_report
assert split_report["train_eval_task_hash_overlap_count"] == 0, split_report
assert split_report["train_private_task_hash_overlap_count"] == 0, split_report
assert split_report["train_public_eval_task_hash_overlap_count"] == 0, split_report
assert split_report["private_generalization_claim_allowed"] is False, split_report

assert release_policy["schema_version"] == "forgeagent.hardened_training_release_policy.v1", release_policy
assert release_policy["policy_integrated"] is True, release_policy
assert release_policy["training_grade_data_release_allowed"] is False, release_policy
assert release_policy["passed_requirement_count"] == 6, release_policy
assert release_policy["failed_requirement_count"] == 3, release_policy

assert oracle_report["schema_version"] == "forgeagent.hardened_oracle_quality_report.v1", oracle_report
assert oracle_report["oracle_certified_task_count"] == 12, oracle_report
assert oracle_report["train_oracle_certified_task_count"] == 4, oracle_report
assert oracle_report["minimum_observed_oracle_strength_score"] == 1.0, oracle_report
assert oracle_report["challenge_matrix_complete"] is True, oracle_report

assert gate["schema_version"] == "forgeagent.hardened_oracle_quality_data_release_gate_decision.v1", gate
assert gate["hardened_oracle_quality_certification_complete"] is True, gate
assert gate["data_release_policy_integrated"] is True, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert "new_hardened_tasks_require_oracle_quality_certification_gate" in gate["resolved_previous_blockers"], gate
assert "final_training_release_policy_not_integrated" in gate["resolved_previous_blockers"], gate
assert "full_public_benchmark_corpus_scan_incomplete" in gate["blocked_reasons"], gate
assert "license_policy_still_scaffold_only" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_hardened_oracle_quality_data_release_report.v1", public_report
assert public_report["task_count"] == 12, public_report
assert public_report["oracle_certified_task_count"] == 12, public_report
assert public_report["raw_task_ids_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["raw_text_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["hidden_test_content_included"] is False, public_report
assert public_report["private_identifier_values_included"] is False, public_report
assert public_report["model_outputs_included"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
for marker in (
    "forge-hard-private-",
    "forge-hard-train-",
    "forge-hard-eval-",
    "forge-hard-public-eval-",
    "diff --git",
    "assertEqual",
    "hidden_tests",
):
    assert marker not in public_blob, (marker, public_blob)

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("hardened_oracle_quality_data_release_integration_v1: OK")
print("task_count:", summary["task_count"])
print("oracle_certified_task_count:", summary["oracle_certified_task_count"])
print("oracle_certified_train_candidate_count:", summary["oracle_certified_train_candidate_count"])
print("training_grade_candidate_after_step29_32_count:", summary["training_grade_candidate_after_step29_32_count"])
print("release_policy_passed_requirement_count:", summary["release_policy_passed_requirement_count"])
print("release_policy_failed_requirement_count:", summary["release_policy_failed_requirement_count"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.32 Hardened Oracle Quality and Data Release Integration" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.32 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Hardened Oracle Quality and Data Release Integration" docs/data/HARDENED_ORACLE_QUALITY_DATA_RELEASE_INTEGRATION.md
grep -q "ADR-0058" docs/engineering/ADR_0058_HARDENED_ORACLE_QUALITY_DATA_RELEASE_INTEGRATION.md

echo
echo "STEP29_32_DOCTOR_OK"

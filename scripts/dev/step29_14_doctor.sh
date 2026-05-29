#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.14 doctor ==="
python3 --version
echo

echo "=== Compile model candidate eval contract ==="
python3 -m compileall -q scripts/dev/run_model_candidate_eval_contract_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.13 heldout-aware protocol artifacts ==="
./scripts/dev/step29_13_doctor.sh
echo

echo "=== Run model candidate eval contract v1 ==="
PYTHONPATH=src python3 scripts/dev/run_model_candidate_eval_contract_v1.py
echo

RESULT_DIR="results/local/model_candidate_eval_contract_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/model_candidate_eval_contract.json"
test -f "${RESULT_DIR}/model_candidate_package_schema.json"
test -f "${RESULT_DIR}/fixture_validation_results.jsonl"
test -f "${RESULT_DIR}/candidate_eval_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_candidate_contract_report.json"
test -f "${RESULT_DIR}/contract_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/model_candidate_eval_contract_v1")
summary = json.loads((root / "summary.json").read_text())
contract = json.loads((root / "model_candidate_eval_contract.json").read_text())
schema = json.loads((root / "model_candidate_package_schema.json").read_text())
gate = json.loads((root / "candidate_eval_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_candidate_contract_report.json").read_text())
privacy = json.loads((root / "contract_privacy_report.json").read_text())
validation_rows = [
    json.loads(line)
    for line in (root / "fixture_validation_results.jsonl").read_text().splitlines()
    if line.strip()
]

assert summary["schema_version"] == "forgeagent.model_candidate_eval_contract_summary.v1", summary
assert summary["contract_name"] == "model_candidate_eval_contract_v1", summary
assert summary["heldout_protocol_ready"] is True, summary
assert summary["candidate_contract_ready"] is True, summary
assert summary["candidate_schema_ready"] is True, summary
assert summary["required_section_count"] >= 8, summary
assert summary["required_metric_count"] >= 10, summary
assert summary["fixture_candidate_count"] == 4, summary
assert summary["accepted_fixture_count"] == 1, summary
assert summary["rejected_fixture_count"] == 3, summary
assert summary["release_passed_fixture_count"] == 0, summary
assert summary["private_leak_fixture_rejected"] is True, summary
assert summary["weak_metric_fixture_rejected"] is True, summary
assert summary["missing_provenance_fixture_rejected"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_15_candidate_eval_runner_dry_run", summary

required_sections = {
    "candidate_identity",
    "model_metadata",
    "run_provenance",
    "generation_config",
    "eval_scope",
    "aggregate_metrics",
    "privacy_attestation",
    "cost_profile",
}
assert required_sections.issubset(set(contract["candidate_package_required_sections"])), contract
assert required_sections.issubset(set(schema["required_sections"])), schema

thresholds = contract["release_gate_thresholds"]
assert thresholds["parse_validity_rate_min"] >= 0.95, thresholds
assert thresholds["public_eval_solve_rate_min"] >= 0.8, thresholds
assert thresholds["private_heldout_pass_rate_min"] >= 0.8, thresholds
assert thresholds["public_overfit_detection_rate_min"] == 1.0, thresholds
assert thresholds["regression_free_patch_rate_min"] >= 0.95, thresholds

by_id = {row["candidate_id"]: row for row in validation_rows}
assert by_id["contract-fixture-structural-pass"]["contract_valid"] is True, by_id
assert by_id["contract-fixture-structural-pass"]["release_gate_passed"] is False, by_id
assert by_id["contract-fixture-private-leak-reject"]["contract_valid"] is False, by_id
assert "private_task_id_leak" in by_id["contract-fixture-private-leak-reject"]["errors"], by_id
assert by_id["contract-fixture-weak-metrics-reject"]["contract_valid"] is False, by_id
assert any(
    item.startswith("release_threshold_failed:")
    for item in by_id["contract-fixture-weak-metrics-reject"]["errors"]
), by_id
assert by_id["contract-fixture-missing-provenance-reject"]["contract_valid"] is False, by_id
assert "missing_field:run_provenance.heldout_protocol_version" in by_id["contract-fixture-missing-provenance-reject"]["errors"], by_id

assert gate["heldout_protocol_ready"] is True, gate
assert gate["contract_ready"] is True, gate
assert gate["accepted_fixture_count"] == 1, gate
assert gate["rejected_fixture_count"] == 3, gate
assert gate["release_passed_fixture_count"] == 0, gate
assert gate["training_launch_allowed"] is False, gate
assert gate["model_release_allowed"] is False, gate

public_blob = json.dumps(public_report, sort_keys=True)
assert public_report["redaction_policy"]["private_task_ids_included"] is False, public_report
assert public_report["redaction_policy"]["private_patch_content_included"] is False, public_report
assert public_report["redaction_policy"]["private_hidden_test_content_included"] is False, public_report
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy

fixture_files = sorted((root / "fixture_candidate_packages").glob("*.json"))
assert len(fixture_files) == 4, fixture_files

print("model_candidate_eval_contract_v1: OK")
print("candidate_contract_ready:", summary["candidate_contract_ready"])
print("required_section_count:", summary["required_section_count"])
print("required_metric_count:", summary["required_metric_count"])
print("fixture_candidate_count:", summary["fixture_candidate_count"])
print("accepted_fixture_count:", summary["accepted_fixture_count"])
print("rejected_fixture_count:", summary["rejected_fixture_count"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_14_DOCTOR_OK"

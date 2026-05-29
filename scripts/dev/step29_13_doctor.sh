#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.13 doctor ==="
python3 --version
echo

echo "=== Compile heldout-aware eval protocol ==="
python3 -m compileall -q scripts/dev/run_heldout_aware_eval_protocol_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.12 private heldout artifacts ==="
./scripts/dev/step29_12_doctor.sh
echo

echo "=== Run heldout-aware eval protocol v1 ==="
PYTHONPATH=src python3 scripts/dev/run_heldout_aware_eval_protocol_v1.py
echo

RESULT_DIR="results/local/heldout_aware_eval_protocol_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/heldout_split_policy.json"
test -f "${RESULT_DIR}/reference_candidate_scorecards.jsonl"
test -f "${RESULT_DIR}/heldout_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_heldout_report.json"
test -f "${RESULT_DIR}/protocol_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/heldout_aware_eval_protocol_v1")
summary = json.loads((root / "summary.json").read_text())
split_policy = json.loads((root / "heldout_split_policy.json").read_text())
gate = json.loads((root / "heldout_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_heldout_report.json").read_text())
privacy = json.loads((root / "protocol_privacy_report.json").read_text())
scorecards = [
    json.loads(line)
    for line in (root / "reference_candidate_scorecards.jsonl").read_text().splitlines()
    if line.strip()
]

assert summary["schema_version"] == "forgeagent.heldout_aware_eval_protocol_summary.v1", summary
assert summary["protocol_name"] == "heldout_aware_eval_protocol_v1", summary
assert summary["private_heldout_task_count"] == 3, summary
assert summary["verified_private_heldout_task_count"] == 3, summary
assert summary["private_task_family_count"] == 3, summary
assert summary["private_behavioral_axis_count"] == 6, summary
assert summary["split_policy_ready"] is True, summary
assert summary["reference_candidate_count"] == 3, summary
assert summary["golden_reference_private_pass_rate"] == 1.0, summary
assert summary["public_overfit_reference_private_pass_rate"] == 0.0, summary
assert summary["public_overfit_detected_count"] == 3, summary
assert summary["rejected_reference_private_pass_rate"] == 0.0, summary
assert summary["protocol_ready"] is True, summary
assert summary["private_isolation_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["public_safe_private_task_id_leak_count"] == 0, summary
assert summary["secret_finding_count"] == 0, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["next_recommended_step"] == "step29_14_model_candidate_eval_contract", summary

assert split_policy["development_split"]["may_use_for_training"] is True, split_policy
assert split_policy["model_selection_split"]["may_use_for_training"] is False, split_policy
assert split_policy["model_selection_split"]["may_use_for_prompt_iteration"] is False, split_policy
assert split_policy["private_final_gate_split"]["may_use_for_training"] is False, split_policy
assert split_policy["private_final_gate_split"]["may_use_for_prompt_iteration"] is False, split_policy
assert split_policy["private_final_gate_split"]["may_inspect_patch_content"] is False, split_policy
assert split_policy["private_final_gate_split"]["aggregate_metrics_only"] is True, split_policy

by_id = {row["candidate_id"]: row for row in scorecards}
assert set(by_id) == {
    "oracle_reference_golden",
    "oracle_reference_public_overfit",
    "oracle_reference_rejected",
}, by_id
assert by_id["oracle_reference_golden"]["private_pass_rate"] == 1.0, by_id
assert by_id["oracle_reference_golden"]["passes_private_gate"] is True, by_id
assert by_id["oracle_reference_public_overfit"]["private_pass_rate"] == 0.0, by_id
assert by_id["oracle_reference_public_overfit"]["public_pass_count"] == 3, by_id
assert by_id["oracle_reference_public_overfit"]["hidden_pass_count"] == 0, by_id
assert by_id["oracle_reference_public_overfit"]["public_overfit_detected_count"] == 3, by_id
assert by_id["oracle_reference_rejected"]["private_pass_rate"] == 0.0, by_id

assert gate["protocol_ready"] is True, gate
assert gate["training_launch_allowed"] is False, gate
assert gate["model_release_allowed"] is False, gate
assert all(gate["gates"].values()), gate

assert public_report["redaction_policy"]["private_task_ids_included"] is False, public_report
assert public_report["redaction_policy"]["private_patch_content_included"] is False, public_report
assert public_report["redaction_policy"]["private_hidden_test_content_included"] is False, public_report
assert public_report["redaction_policy"]["task_level_private_results_included"] is False, public_report

public_blob = json.dumps(public_report, sort_keys=True)
assert "forge-private-heldout-" not in public_blob, public_blob
assert "diff --git" not in public_blob, public_blob
assert "assertEqual" not in public_blob, public_blob

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_safe_private_task_id_leak_count"] == 0, privacy

print("heldout_aware_eval_protocol_v1: OK")
print("private_heldout_task_count:", summary["private_heldout_task_count"])
print("reference_candidate_count:", summary["reference_candidate_count"])
print("golden_reference_private_pass_rate:", summary["golden_reference_private_pass_rate"])
print("public_overfit_detected_count:", summary["public_overfit_detected_count"])
print("protocol_ready:", summary["protocol_ready"])
print("privacy_scan_passed:", summary["privacy_scan_passed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

echo
echo "STEP29_13_DOCTOR_OK"

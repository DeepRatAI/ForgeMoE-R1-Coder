#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.37 doctor ==="
python3 --version
echo

echo "=== Compile training payload schema quality tokenization gate ==="
python3 -m compileall -q scripts/dev/run_training_payload_schema_quality_tokenization_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.36 source artifacts ==="
./scripts/dev/step29_36_doctor.sh
echo

echo "=== Enforce no local model or local training runtime for this gate ==="
if pgrep -af "ollama runner|local_transformers|torchrun|deepspeed|accelerate launch" >/tmp/forgemoe_step29_37_forbidden_local_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_37_forbidden_local_runtime_processes.txt
  echo "forbidden local model or local training runtime process detected"
  exit 1
fi
echo "forbidden_local_runtime_processes: none"
echo

echo "=== Run training payload schema quality tokenization v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_training_payload_schema_quality_tokenization_v1.py
echo

RESULT_DIR="results/local/training_payload_schema_quality_tokenization_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/schema_validation_results.jsonl"
test -f "${RESULT_DIR}/tokenization_proxy_rows.jsonl"
test -f "${RESULT_DIR}/tokenization_proxy_report.json"
test -f "${RESULT_DIR}/training_manifest_v2.json"
test -f "${RESULT_DIR}/training_readiness_decision.json"
test -f "${RESULT_DIR}/public_safe_training_payload_schema_quality_tokenization_report.json"
test -f "${RESULT_DIR}/training_payload_schema_quality_tokenization_privacy_report.json"
test -f "${RESULT_DIR}/dataset_exports/rendered_patch_sft_training_payload.jsonl"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/training_payload_schema_quality_tokenization_v1")
summary = json.loads((root / "summary.json").read_text())
schema_rows = [
    json.loads(line)
    for line in (root / "schema_validation_results.jsonl").read_text().splitlines()
    if line.strip()
]
token_rows = [
    json.loads(line)
    for line in (root / "tokenization_proxy_rows.jsonl").read_text().splitlines()
    if line.strip()
]
token_report = json.loads((root / "tokenization_proxy_report.json").read_text())
manifest = json.loads((root / "training_manifest_v2.json").read_text())
readiness = json.loads((root / "training_readiness_decision.json").read_text())
public_report = json.loads((root / "public_safe_training_payload_schema_quality_tokenization_report.json").read_text())
privacy = json.loads((root / "training_payload_schema_quality_tokenization_privacy_report.json").read_text())
rendered_rows = [
    json.loads(line)
    for line in (root / "dataset_exports/rendered_patch_sft_training_payload.jsonl").read_text().splitlines()
    if line.strip()
]

assert summary["schema_version"] == "forgeagent.training_payload_schema_quality_tokenization_summary.v1", summary
assert summary["gate_name"] == "training_payload_schema_quality_tokenization_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["source_payload_row_count"] == 4, summary
assert summary["schema_valid_row_count"] == 4, summary
assert summary["row_quality_pass_count"] == 4, summary
assert summary["manifest_consistent_row_count"] == 4, summary
assert summary["token_budget_proxy_pass_count"] == 4, summary
assert summary["would_truncate_proxy_count"] == 0, summary
assert summary["max_estimated_tokens"] <= 4096, summary
assert summary["p95_estimated_tokens"] <= 4096, summary
assert summary["hidden_test_content_leak_count"] == 0, summary
assert summary["negative_patch_content_leak_count"] == 0, summary
assert summary["training_payload_schema_quality_passed"] is True, summary
assert summary["token_budget_proxy_gate_passed"] is True, summary
assert summary["model_specific_tokenizer_available"] is False, summary
assert summary["model_specific_tokenizer_validation_passed"] is False, summary
assert summary["training_payload_ready_for_model_specific_tokenizer_gate"] is True, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary
assert summary["next_recommended_step"] == "step29_38_model_specific_tokenizer_selection_and_remote_training_cost_gate_v1", summary

assert len(schema_rows) == 4, schema_rows
for row in schema_rows:
    assert row["schema_version"] == "forgeagent.training_payload_schema_validation_result.v1", row
    assert row["schema_valid"] is True, row
    assert row["schema_error_count"] == 0, row
    assert row["repo_file_hashes_valid"] is True, row
    assert row["public_test_hashes_valid"] is True, row
    assert row["target_patch_hash_valid"] is True, row
    assert row["payload_id_valid"] is True, row
    assert row["manifest_consistent"] is True, row
    assert row["messages_valid"] is True, row
    assert row["no_repo_tests_in_repo_files"] is True, row
    assert row["public_tests_present"] is True, row
    assert row["hidden_test_content_leak"] is False, row
    assert row["negative_patch_content_leak"] is False, row
    assert row["validation_command_present"] is True, row
    assert row["row_quality_passed"] is True, row
    assert row["contains_raw_text"] is False, row
    assert row["contains_private_identifiers"] is False, row

assert len(token_rows) == 4, token_rows
for row in token_rows:
    assert row["schema_version"] == "forgeagent.training_payload_tokenization_proxy_row.v1", row
    assert row["split"] == "train", row
    assert row["estimated_total_tokens"] > 0, row
    assert row["estimated_total_tokens"] <= row["proxy_max_sequence_length"], row
    assert row["proxy_max_sequence_length"] == 4096, row
    assert row["would_truncate_proxy"] is False, row
    assert row["estimation_method"] == "max(regex_code_token_count, ceil(character_count/3))", row
    assert row["model_specific_tokenizer_used"] is False, row
    assert row["contains_raw_text"] is False, row
    assert row["contains_private_identifiers"] is False, row

assert token_report["schema_version"] == "forgeagent.training_payload_tokenization_proxy_report.v1", token_report
assert token_report["preferred_tokenizer_model_id"] == "Qwen/Qwen2.5-Coder-0.5B-Instruct", token_report
assert token_report["proxy_max_sequence_length"] == 4096, token_report
assert token_report["token_budget_proxy_pass_count"] == 4, token_report
assert token_report["would_truncate_proxy_count"] == 0, token_report
assert token_report["token_budget_proxy_gate_passed"] is True, token_report
assert token_report["model_specific_tokenizer_validation_passed"] is False, token_report
assert token_report["training_launch_allowed"] is False, token_report
assert token_report["tokenizer_environment"]["full_weight_load_attempted"] is False, token_report
assert token_report["tokenizer_environment"]["local_model_execution_used"] is False, token_report
assert token_report["tokenizer_environment"]["model_specific_tokenizer_required_before_training_launch"] is True, token_report
assert token_report["contains_raw_text"] is False, token_report

assert manifest["schema_version"] == "forgeagent.patch_sft_training_manifest_v2.v1", manifest
assert manifest["payload_row_count"] == 4, manifest
assert manifest["train_rows"] == 4, manifest
assert manifest["eval_rows"] == 0, manifest
assert manifest["objective"] == "patch_sft_git_diff_generation", manifest
assert manifest["target_format"] == "git_diff_patch", manifest
assert manifest["schema_quality_gate"]["passed"] is True, manifest
assert manifest["schema_quality_gate"]["schema_valid_row_count"] == 4, manifest
assert manifest["schema_quality_gate"]["manifest_consistent_row_count"] == 4, manifest
assert manifest["tokenization_proxy_gate"]["passed"] is True, manifest
assert manifest["tokenization_proxy_gate"]["would_truncate_proxy_count"] == 0, manifest
assert manifest["model_specific_tokenizer_gate"]["passed"] is False, manifest
assert manifest["model_specific_tokenizer_gate"]["required_before_training_launch"] is True, manifest
assert manifest["training_launch_allowed"] is False, manifest
assert manifest["model_release_allowed"] is False, manifest

assert readiness["schema_version"] == "forgeagent.training_payload_readiness_decision.v1", readiness
assert readiness["training_payload_schema_quality_passed"] is True, readiness
assert readiness["token_budget_proxy_gate_passed"] is True, readiness
assert readiness["model_specific_tokenizer_validation_passed"] is False, readiness
assert readiness["training_payload_ready_for_model_specific_tokenizer_gate"] is True, readiness
assert readiness["training_launch_allowed"] is False, readiness
assert readiness["model_release_allowed"] is False, readiness
assert readiness["blocked_reasons"] == ["model_specific_tokenizer_validation_not_complete"], readiness
assert readiness["next_recommended_step"] == "step29_38_model_specific_tokenizer_selection_and_remote_training_cost_gate_v1", readiness

assert len(rendered_rows) == 4, rendered_rows
for row in rendered_rows:
    assert row["schema_version"] == "forgeagent.rendered_patch_sft_training_payload_row.v1", row
    assert row["split"] == "train", row
    assert row["training_export_allowed"] is True, row
    assert row["training_grade"] is True, row
    assert row["rendered_text"].startswith("<|user|>"), row
    assert "<|assistant|>" in row["rendered_text"], row
    assert "diff --git " in row["rendered_text"], row
    assert len(row["rendered_text_sha256"]) == 64, row
    int(row["rendered_text_sha256"], 16)

assert public_report["schema_version"] == "forgeagent.public_safe_training_payload_schema_quality_tokenization_report.v1", public_report
assert public_report["source_payload_row_count"] == 4, public_report
assert public_report["schema_valid_row_count"] == 4, public_report
assert public_report["manifest_consistent_row_count"] == 4, public_report
assert public_report["token_budget_proxy_pass_count"] == 4, public_report
assert public_report["would_truncate_proxy_count"] == 0, public_report
assert public_report["training_payload_schema_quality_passed"] is True, public_report
assert public_report["token_budget_proxy_gate_passed"] is True, public_report
assert public_report["model_specific_tokenizer_validation_passed"] is False, public_report
assert public_report["training_launch_allowed"] is False, public_report
assert public_report["model_release_allowed"] is False, public_report
assert public_report["raw_task_ids_included"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["repo_content_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["hidden_test_content_included"] is False, public_report
assert public_report["negative_patch_content_included"] is False, public_report
assert public_report["rendered_text_included"] is False, public_report
assert public_report["local_model_execution_used"] is False, public_report
assert public_report["remote_inference_invoked"] is False, public_report
public_blob = json.dumps(public_report, sort_keys=True)
for marker in (
    "forge-hard-train-",
    "forge-hard-eval-",
    "forge-hard-private-",
    "forge-hard-public-eval-",
    "diff --git",
    "assertEqual",
    '"hidden_tests":',
    '"target_patch":',
    '"repo_files":',
    '"messages":',
    '"content_sha256":',
    '"rendered_text":',
):
    assert marker not in public_blob, (marker, public_blob)

assert privacy["passed"] is True, privacy
assert privacy["secret_finding_count"] == 0, privacy
assert privacy["public_report_marker_leak_count"] == 0, privacy

print("training_payload_schema_quality_tokenization_v1: OK")
print("source_payload_row_count:", summary["source_payload_row_count"])
print("schema_valid_row_count:", summary["schema_valid_row_count"])
print("manifest_consistent_row_count:", summary["manifest_consistent_row_count"])
print("token_budget_proxy_pass_count:", summary["token_budget_proxy_pass_count"])
print("would_truncate_proxy_count:", summary["would_truncate_proxy_count"])
print("model_specific_tokenizer_validation_passed:", summary["model_specific_tokenizer_validation_passed"])
print("training_launch_allowed:", summary["training_launch_allowed"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.37 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Step 29.37 Training Payload Schema Quality and Tokenization" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Training Payload Schema Quality and Tokenization Gate" docs/data/TRAINING_PAYLOAD_SCHEMA_QUALITY_TOKENIZATION.md
grep -q "ADR-0063" docs/engineering/ADR_0063_TRAINING_PAYLOAD_SCHEMA_QUALITY_TOKENIZATION.md

echo
echo "STEP29_37_DOCTOR_OK"

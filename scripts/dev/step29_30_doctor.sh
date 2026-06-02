#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.30 doctor ==="
python3 --version
echo

echo "=== Compile hardened generation/public benchmark registry gate ==="
python3 -m compileall -q scripts/dev/run_hardened_task_generation_public_benchmark_registry_v1.py
echo "compileall: OK"
echo

echo "=== Refresh Step 29.29 source artifacts ==="
./scripts/dev/step29_29_doctor.sh
echo

echo "=== Enforce no local model, training, large dataset download, or remote inference execution for this gate ==="
if pgrep -af "ollama runner|run_real_candidate_smoke_package_v1.py|local_transformers|torchrun|deepspeed|accelerate launch|bedrock-runtime.*(converse|invoke-model)" >/tmp/forgemoe_step29_30_forbidden_runtime_processes.txt; then
  cat /tmp/forgemoe_step29_30_forbidden_runtime_processes.txt
  echo "forbidden model runtime, training, or remote inference process detected"
  exit 1
fi
echo "forbidden_runtime_processes: none"
echo

echo "=== Run hardened generation/public benchmark registry gate v1 ==="
PYTHONPATH=src:scripts/dev python3 scripts/dev/run_hardened_task_generation_public_benchmark_registry_v1.py
echo

RESULT_DIR="results/local/hardened_task_generation_public_benchmark_registry_v1"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/public_benchmark_registry.json"
test -f "${RESULT_DIR}/current_public_eval_reference_index.json"
test -f "${RESULT_DIR}/hardened_task_blueprints.json"
test -f "${RESULT_DIR}/hardened_task_blueprints.jsonl"
test -f "${RESULT_DIR}/hardened_generation_similarity_report.json"
test -f "${RESULT_DIR}/benchmark_contamination_gate_decision.json"
test -f "${RESULT_DIR}/public_safe_hardened_generation_benchmark_registry_report.json"
test -f "${RESULT_DIR}/hardened_generation_benchmark_registry_privacy_report.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/hardened_task_generation_public_benchmark_registry_v1")
summary = json.loads((root / "summary.json").read_text())
registry = json.loads((root / "public_benchmark_registry.json").read_text())
reference_index = json.loads((root / "current_public_eval_reference_index.json").read_text())
blueprints = json.loads((root / "hardened_task_blueprints.json").read_text())
blueprint_rows = [json.loads(line) for line in (root / "hardened_task_blueprints.jsonl").read_text().splitlines()]
similarity = json.loads((root / "hardened_generation_similarity_report.json").read_text())
gate = json.loads((root / "benchmark_contamination_gate_decision.json").read_text())
public_report = json.loads((root / "public_safe_hardened_generation_benchmark_registry_report.json").read_text())
privacy = json.loads((root / "hardened_generation_benchmark_registry_privacy_report.json").read_text())

assert summary["schema_version"] == "forgeagent.hardened_generation_public_benchmark_registry_summary.v1", summary
assert summary["gate_name"] == "hardened_task_generation_public_benchmark_registry_v1", summary
assert summary["source_step_ready"] is True, summary
assert summary["benchmark_registry_entry_count"] >= 10, summary
assert summary["benchmark_registry_never_train_direct_count"] == summary["benchmark_registry_entry_count"], summary
assert summary["benchmark_registry_requires_scan_count"] == summary["benchmark_registry_entry_count"], summary
assert summary["current_reference_count"] >= 15, summary
assert summary["current_public_eval_reference_count"] == 6, summary
assert summary["current_private_reference_count"] >= 4, summary
assert summary["hardened_blueprint_count"] == 12, summary
assert summary["hardened_train_blueprint_count"] == 4, summary
assert summary["hardened_eval_blueprint_count"] == 3, summary
assert summary["hardened_private_heldout_blueprint_count"] == 3, summary
assert summary["hardened_public_eval_blueprint_count"] == 2, summary
assert summary["public_benchmark_registry_ready"] is True, summary
assert summary["hardened_generation_plan_ready"] is True, summary
assert summary["exact_current_reference_collision_count"] == 0, summary
assert summary["exact_public_benchmark_registry_collision_count"] == 0, summary
assert summary["high_current_private_or_eval_reference_similarity_count"] == 0, summary
assert summary["high_public_benchmark_registry_similarity_count"] == 0, summary
assert summary["hardened_eval_private_high_similarity_pair_count"] == 0, summary
assert summary["full_public_benchmark_corpus_scan_complete"] is False, summary
assert summary["direct_benchmark_content_ingested"] is False, summary
assert summary["corpus_downloaded_for_this_gate"] is False, summary
assert summary["training_grade_data_release_allowed"] is False, summary
assert summary["training_launch_allowed"] is False, summary
assert summary["model_release_allowed"] is False, summary
assert summary["privacy_scan_passed"] is True, summary
assert summary["public_safe_report_ready"] is True, summary
assert summary["downloads_large_dataset"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["local_model_execution_used"] is False, summary
assert summary["remote_inference_invoked"] is False, summary

assert registry["schema_version"] == "forgeagent.public_benchmark_contamination_registry.v1", registry
assert registry["registry_entry_count"] == summary["benchmark_registry_entry_count"], registry
assert registry["full_public_benchmark_corpus_scan_complete"] is False, registry
assert registry["direct_benchmark_content_ingested"] is False, registry
assert registry["contains_raw_benchmark_tasks"] is False, registry
assert registry["contains_private_identifiers"] is False, registry
assert all(row["never_train_direct"] is True for row in registry["entries"]), registry
assert all(row["requires_contamination_scan"] is True for row in registry["entries"]), registry
assert all(row["contains_raw_benchmark_tasks"] is False for row in registry["entries"]), registry

assert reference_index["schema_version"] == "forgeagent.current_public_eval_reference_index.v1", reference_index
assert reference_index["hash_only"] is True, reference_index
assert reference_index["reference_count"] == summary["current_reference_count"], reference_index
assert reference_index["public_eval_reference_count"] == 6, reference_index
assert reference_index["contains_raw_text"] is False, reference_index
assert reference_index["contains_private_identifiers"] is False, reference_index
assert all(row["contains_raw_text"] is False for row in reference_index["rows"]), reference_index
assert all(row["contains_private_identifiers"] is False for row in reference_index["rows"]), reference_index

assert blueprints["schema_version"] == "forgeagent.hardened_task_blueprint_manifest.v1", blueprints
assert blueprints["blueprint_count"] == 12, blueprints
assert blueprints["contains_raw_text"] is False, blueprints
assert blueprints["contains_patch_content"] is False, blueprints
assert blueprints["contains_private_identifiers"] is False, blueprints
assert len(blueprint_rows) == 12, blueprint_rows
assert sorted({row["split"] for row in blueprint_rows}) == ["eval", "private_heldout", "public_eval", "train"], blueprint_rows
assert all(row["expected_patch_format"] == "git_diff" for row in blueprint_rows), blueprint_rows
assert all(row["required_verification_contract"]["git_apply_check"] is True for row in blueprint_rows), blueprint_rows
assert all(row["required_verification_contract"]["post_hidden_pass"] is True for row in blueprint_rows), blueprint_rows
assert all(row["generation_constraints"]["must_use_real_temp_git_repo"] is True for row in blueprint_rows), blueprint_rows
assert all(row["contains_raw_text"] is False for row in blueprint_rows), blueprint_rows
assert all(row["contains_patch_content"] is False for row in blueprint_rows), blueprint_rows
assert all(row["contains_private_identifiers"] is False for row in blueprint_rows), blueprint_rows

assert similarity["schema_version"] == "forgeagent.hardened_generation_similarity_report.v1", similarity
assert similarity["exact_current_reference_collision_count"] == 0, similarity
assert similarity["exact_public_benchmark_registry_collision_count"] == 0, similarity
assert similarity["high_current_private_or_eval_reference_similarity_count"] == 0, similarity
assert similarity["high_public_benchmark_registry_similarity_count"] == 0, similarity
assert similarity["hardened_eval_private_high_similarity_pair_count"] == 0, similarity
assert similarity["contains_raw_text"] is False, similarity
assert similarity["contains_raw_benchmark_tasks"] is False, similarity
assert similarity["contains_private_identifiers"] is False, similarity

assert gate["schema_version"] == "forgeagent.hardened_generation_public_benchmark_registry_gate_decision.v1", gate
assert gate["public_benchmark_registry_ready"] is True, gate
assert gate["hardened_generation_plan_ready"] is True, gate
assert gate["full_public_benchmark_corpus_scan_complete"] is False, gate
assert gate["training_grade_data_release_allowed"] is False, gate
assert gate["training_launch_allowed"] is False, gate
assert "full_public_benchmark_corpus_scan_incomplete" in gate["blocked_reasons"], gate
assert "executable_hardened_task_repos_not_generated_yet" in gate["blocked_reasons"], gate

assert public_report["schema_version"] == "forgeagent.public_safe_hardened_generation_benchmark_registry_report.v1", public_report
assert public_report["benchmark_registry_entry_count"] == summary["benchmark_registry_entry_count"], public_report
assert public_report["hardened_generation_plan_ready"] is True, public_report
assert public_report["training_launch_allowed"] is False, public_report
assert public_report["raw_rows_included"] is False, public_report
assert public_report["raw_text_included"] is False, public_report
assert public_report["raw_benchmark_tasks_included"] is False, public_report
assert public_report["private_identifier_values_included"] is False, public_report
assert public_report["patch_content_included"] is False, public_report
assert public_report["prompt_content_included"] is False, public_report
assert public_report["withheld_eval_content_included"] is False, public_report
assert public_report["model_outputs_included"] is False, public_report
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

print("hardened_task_generation_public_benchmark_registry_v1: OK")
print("benchmark_registry_entry_count:", summary["benchmark_registry_entry_count"])
print("current_reference_count:", summary["current_reference_count"])
print("hardened_blueprint_count:", summary["hardened_blueprint_count"])
print("hardened_generation_plan_ready:", summary["hardened_generation_plan_ready"])
print("full_public_benchmark_corpus_scan_complete:", summary["full_public_benchmark_corpus_scan_complete"])
print("next_recommended_step:", summary["next_recommended_step"])
PY

grep -q "Step 29.30 Hardened Task Generation and Public Benchmark Registry" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.30 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "Hardened Task Generation and Public Benchmark Contamination Registry" docs/data/HARDENED_TASK_GENERATION_PUBLIC_BENCHMARK_REGISTRY.md
grep -q "ADR-0056" docs/engineering/ADR_0056_HARDENED_TASK_GENERATION_PUBLIC_BENCHMARK_REGISTRY.md

echo
echo "STEP29_30_DOCTOR_OK"

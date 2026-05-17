#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.7 doctor ==="
python3 --version
echo

echo "=== Compile source matrix builder ==="
python3 -m compileall -q scripts/dev/build_dataset_source_matrix_gate_v0.py
echo "compileall: OK"
echo

echo "=== Build dataset source matrix and acquisition gate ==="
PYTHONPATH=src python3 scripts/dev/build_dataset_source_matrix_gate_v0.py
echo

test -f results/local/dataset_source_matrix_gate_v0/dataset_source_matrix_gate.json
test -f results/local/dataset_source_matrix_gate_v0/dataset_acquisition_gate_report.json
test -f docs/data/DATASET_SOURCE_MATRIX_AND_ACQUISITION_GATE.md
test -f docs/engineering/ADR_0033_DATASET_SOURCE_MATRIX_AND_ACQUISITION_GATE.md

python3 - <<'PY'
import json
from pathlib import Path

matrix = json.loads(Path("results/local/dataset_source_matrix_gate_v0/dataset_source_matrix_gate.json").read_text())
report = json.loads(Path("results/local/dataset_source_matrix_gate_v0/dataset_acquisition_gate_report.json").read_text())

assert matrix["schema_version"] == "forgeagent.dataset_source_matrix_gate.v0", matrix
assert report["schema_version"] == "forgeagent.dataset_acquisition_gate_report.v0", report

assert matrix["source_count"] == 11, matrix
assert matrix["gate_count"] == 10, matrix
assert matrix["launches_training_job"] is False, matrix
assert matrix["downloads_large_dataset"] is False, matrix
assert matrix["gpu_required"] is False, matrix
assert matrix["requires_explicit_approval_before_training"] is True, matrix
assert matrix["next_recommended_step"] == "step29_8_internal_synthetic_task_generator_design", matrix

assert report["training_launch_allowed"] is False, report
assert report["large_dataset_download_allowed"] is False, report
assert len(report["internal_build_candidates"]) >= 3, report
assert "forge_synthetic_executable_tasks" in report["internal_build_candidates"], report
assert "forge_agentic_trajectories" in report["internal_build_candidates"], report
assert "forge_private_heldout_eval" in report["internal_build_candidates"], report
assert "the_stack_v2" in report["blocked_before_ingestion"], report
assert "swe_bench_verified" in report["reference_only_sources"], report
assert "livecodebench" in report["reference_only_sources"], report
assert "bigcodebench" in report["reference_only_sources"], report

docs = Path("docs/data/DATASET_SOURCE_MATRIX_AND_ACQUISITION_GATE.md").read_text()
adr = Path("docs/engineering/ADR_0033_DATASET_SOURCE_MATRIX_AND_ACQUISITION_GATE.md").read_text()

assert "Dataset Source Matrix" in docs, docs
assert "Step 30 training remains blocked" in adr, adr

print("dataset_source_matrix_gate: OK")
print("source_count:", matrix["source_count"])
print("gate_count:", matrix["gate_count"])
print("decision_counts:", matrix["decision_counts"])
print("internal_build_candidates:", ",".join(report["internal_build_candidates"]))
print("training_launch_allowed:", report["training_launch_allowed"])
print("next_recommended_step:", matrix["next_recommended_step"])
PY

echo

grep -q "Step 29.7 Dataset Source Matrix and Acquisition Gate" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.7 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md

echo "docs: OK"
echo
echo "STEP29_7_DOCTOR_OK"

#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.6 doctor ==="
python3 --version
echo

echo "=== Compile strategy writer ==="
python3 -m compileall -q scripts/dev/write_sota_dataset_strategy_docs.py
echo "compileall: OK"
echo

echo "=== Generate strategy docs and reports ==="
PYTHONPATH=src python3 scripts/dev/write_sota_dataset_strategy_docs.py
echo

test -f docs/strategy/PROJECT_NORTH_STAR.md
test -f docs/data/SOTA_DATASET_STRATEGY_AND_GOVERNANCE.md
test -f docs/engineering/ADR_0032_SOTA_DATASET_GOVERNANCE_BEFORE_TRAINING.md
test -f results/local/sota_dataset_strategy_v0/dataset_governance_plan.json
test -f results/local/sota_dataset_strategy_v0/dataset_source_matrix.json

python3 - <<'PY'
import json
from pathlib import Path

plan = json.loads(Path("results/local/sota_dataset_strategy_v0/dataset_governance_plan.json").read_text())
matrix = json.loads(Path("results/local/sota_dataset_strategy_v0/dataset_source_matrix.json").read_text())

assert plan["schema_version"] == "forgeagent.sota_dataset_governance_plan.v0", plan
assert plan["current_dataset_classification"]["step29_5_rows"] == 192, plan
assert plan["current_dataset_classification"]["training_grade"] is False, plan
assert len(plan["data_layers"]) >= 7, plan
assert len(plan["quality_dimensions"]) >= 10, plan
assert len(plan["public_dataset_candidate_classes"]) >= 4, plan
assert plan["launches_training_job"] is False, plan
assert plan["gpu_required"] is False, plan
assert plan["requires_explicit_approval_before_training"] is True, plan
assert plan["next_recommended_step"] == "step29_7_dataset_source_matrix_and_acquisition_gate", plan

assert matrix["schema_version"] == "forgeagent.dataset_source_matrix.v0", matrix
assert matrix["status"] == "candidate_classes_only", matrix
assert len(matrix["blocking_before_ingestion"]) >= 7, matrix

north_star = Path("docs/strategy/PROJECT_NORTH_STAR.md").read_text()
strategy = Path("docs/data/SOTA_DATASET_STRATEGY_AND_GOVERNANCE.md").read_text()
adr = Path("docs/engineering/ADR_0032_SOTA_DATASET_GOVERNANCE_BEFORE_TRAINING.md").read_text()

assert "7B / 9B / 14B" in north_star, north_star
assert "scaffold / plumbing / format-validation data" in strategy, strategy
assert "Do not treat Step 29.2 or Step 29.5 synthetic data as final training-grade data" in adr, adr

print("sota_dataset_strategy: OK")
print("step29_5_rows:", plan["current_dataset_classification"]["step29_5_rows"])
print("training_grade:", plan["current_dataset_classification"]["training_grade"])
print("data_layers:", len(plan["data_layers"]))
print("quality_dimensions:", len(plan["quality_dimensions"]))
print("candidate_dataset_classes:", len(plan["public_dataset_candidate_classes"]))
print("next_recommended_step:", plan["next_recommended_step"])
PY

echo

grep -q "Step 29.6 SOTA Dataset Governance" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.6 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md

echo "docs: OK"
echo
echo "STEP29_6_DOCTOR_OK"

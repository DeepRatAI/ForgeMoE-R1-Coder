#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.8 doctor ==="
python3 --version
echo

echo "=== Compile internal generator design builder ==="
python3 -m compileall -q scripts/dev/build_internal_synthetic_task_generator_design_v0.py
echo "compileall: OK"
echo

echo "=== Build internal synthetic generator design ==="
PYTHONPATH=src python3 scripts/dev/build_internal_synthetic_task_generator_design_v0.py
echo

test -f results/local/internal_synthetic_task_generator_design_v0/generator_design.json
test -f results/local/internal_synthetic_task_generator_design_v0/synthetic_task_schema_v0.json
test -f results/local/internal_synthetic_task_generator_design_v0/agentic_trajectory_schema_v0.json
test -f results/local/internal_synthetic_task_generator_design_v0/private_heldout_protocol_v0.json
test -f results/local/internal_synthetic_task_generator_design_v0/synthetic_data_engine_risk_register.json
test -f docs/data/INTERNAL_SYNTHETIC_EXECUTABLE_TASK_GENERATOR.md
test -f docs/data/PRIVATE_HELDOUT_PROTOCOL.md
test -f docs/engineering/ADR_0034_INTERNAL_SYNTHETIC_GENERATOR_AND_HELDOUT.md

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/internal_synthetic_task_generator_design_v0")
design = json.loads((root / "generator_design.json").read_text())
task_schema = json.loads((root / "synthetic_task_schema_v0.json").read_text())
trajectory_schema = json.loads((root / "agentic_trajectory_schema_v0.json").read_text())
heldout = json.loads((root / "private_heldout_protocol_v0.json").read_text())
risk = json.loads((root / "synthetic_data_engine_risk_register.json").read_text())

assert design["schema_version"] == "forgeagent.internal_synthetic_task_generator_design.v0", design
assert len(design["generator_modules"]) == 13, design
assert len(task_schema["task_families"]) == 12, task_schema
assert task_schema["private_heldout_rule"] == "never_train_on_private_heldout", task_schema
assert len(trajectory_schema["event_types"]) >= 10, trajectory_schema
assert "private_heldout_tasks_are_never_used_for_training" in heldout["rules"], heldout
assert len(heldout["promotion_metrics"]) >= 10, heldout
assert len(risk["risks"]) >= 6, risk

assert design["launches_training_job"] is False, design
assert design["downloads_large_dataset"] is False, design
assert design["gpu_required"] is False, design
assert design["next_recommended_step"] == "step29_9_task_schema_and_micro_generator_scaffold", design

docs = Path("docs/data/INTERNAL_SYNTHETIC_EXECUTABLE_TASK_GENERATOR.md").read_text()
heldout_doc = Path("docs/data/PRIVATE_HELDOUT_PROTOCOL.md").read_text()
adr = Path("docs/engineering/ADR_0034_INTERNAL_SYNTHETIC_GENERATOR_AND_HELDOUT.md").read_text()

assert "Internal Synthetic Executable Task Generator" in docs, docs
assert "Private Heldout Protocol" in heldout_doc, heldout_doc
assert "Step 30 remains blocked" in adr, adr

print("internal_generator_design: OK")
print("generator_modules:", len(design["generator_modules"]))
print("task_families:", len(task_schema["task_families"]))
print("trajectory_event_types:", len(trajectory_schema["event_types"]))
print("heldout_metrics:", len(heldout["promotion_metrics"]))
print("risk_count:", len(risk["risks"]))
print("next_recommended_step:", design["next_recommended_step"])
PY

echo

grep -q "Step 29.8 Internal Synthetic Generator and Heldout Design" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 29.8 Recap" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md

echo "docs: OK"
echo
echo "STEP29_8_DOCTOR_OK"

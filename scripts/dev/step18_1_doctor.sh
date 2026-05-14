#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 18.1 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/build_run_registry.py
echo "compileall: OK"
echo

echo "=== Validate engineering docs ==="
grep -q "ADR-0014" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "ADR-0015" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 18 — Real Model Adapter v0: completed" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
echo "engineering docs: OK"
echo

echo "=== Build updated run registry ==="
PYTHONPATH=src python3 scripts/dev/build_run_registry.py
echo

test -f reports/local/run_registry.json
test -f reports/local/run_registry.md

python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("reports/local/run_registry.json").read_text())
entries = data["entries"]
steps = [entry["step"] for entry in entries]

assert len(entries) == 12, entries
assert steps == [9, 10, 11, 12, 13, 14, 15, 16, 17, 176, 18, 19], steps

by_step = {entry["step"]: entry for entry in entries}
assert by_step[18]["name"] == "real_model_adapter_contract", by_step[18]
assert by_step[18]["metrics"]["selected_patch_id"] == "mock_good_max2_candidate_2", by_step[18]
assert by_step[18]["metrics"]["real_model_downloaded"] is False, by_step[18]
assert by_step[176]["name"] == "engineering_decision_records", by_step[176]

md = Path("reports/local/run_registry.md").read_text()
assert "real_model_adapter_contract" in md, md
assert "engineering_decision_records" in md, md

print("updated_run_registry: OK")
print("entry_count:", len(entries))
print("steps:", steps)
PY

echo
echo "STEP18_1_DOCTOR_OK"

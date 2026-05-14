#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 19.1 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/build_run_registry.py
echo "compileall: OK"
echo

echo "=== Validate docs ==="
test -f docs/engineering/ADR_0017_FIRST_REAL_MODEL_RUNTIME.md
grep -q "Step 19 transition" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Post-Step 19 status" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md
grep -q "sshleifer/tiny-gpt2" docs/engineering/ADR_0017_FIRST_REAL_MODEL_RUNTIME.md
echo "docs: OK"
echo

echo "=== Build refreshed run registry ==="
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

step19 = next(entry for entry in entries if entry["step"] == 19)
assert step19["name"] == "tiny_real_model_smoke", step19
assert step19["status"] == "ok", step19
assert step19["gpu_required"] is False, step19
assert step19["h100_purchase_required"] is False, step19
assert step19["metrics"]["model_load_ok"] is True, step19
assert step19["metrics"]["real_generation_ok"] is True, step19
assert step19["metrics"]["parse_failure_count"] == 1, step19

md = Path("reports/local/run_registry.md").read_text()
assert "tiny_real_model_smoke" in md, md
assert "sshleifer/tiny-gpt2" in md, md

print("updated_run_registry: OK")
print("entry_count:", len(entries))
print("steps:", steps)
print("step19_metrics:", step19["metrics"])
PY

echo
echo "STEP19_1_DOCTOR_OK"

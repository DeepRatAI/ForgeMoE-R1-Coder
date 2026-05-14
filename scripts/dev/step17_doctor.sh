#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 17 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/build_run_registry.py
echo "compileall: OK"
echo

echo "=== Build run registry ==="
PYTHONPATH=src python3 scripts/dev/build_run_registry.py
echo

test -f reports/local/run_registry.json
test -f reports/local/run_registry.md

python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("reports/local/run_registry.json").read_text())
entries = data["entries"]

assert data["project"] == "ForgeMoE-R1-Agent-Coder", data
assert data["registry_version"] == "v0", data
assert len(entries) >= 8, entries

steps = [entry["step"] for entry in entries]
assert all(step in steps for step in [9, 10, 11, 12, 13, 14, 15, 16]), steps

assert all(entry["status"] == "ok" for entry in entries), entries
assert all(entry["gpu_required"] is False for entry in entries), entries
assert all(entry["h100_purchase_required"] is False for entry in entries), entries

md = Path("reports/local/run_registry.md").read_text()
assert "ForgeMoE-R1-Agent-Coder Run Registry" in md, md
assert "agentic_experiment_runner" in md, md

print("registry_json: OK")
print("registry_markdown: OK")
print("entry_count:", len(entries))
print("steps:", steps)
PY

echo
echo "STEP17_DOCTOR_OK"

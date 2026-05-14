#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 20.1 doctor ==="
python3 --version
echo

echo "=== Compile analyzer ==="
python3 -m compileall -q scripts/dev/analyze_step20_qwen_baseline.py
echo "compileall: OK"
echo

echo "=== Run forensic analyzer ==="
PYTHONPATH=src python3 scripts/dev/analyze_step20_qwen_baseline.py
echo

test -f reports/local/step20_forensics/step20_qwen_baseline_forensics.json
test -f reports/local/step20_forensics/step20_qwen_baseline_forensics.md

python3 - <<'PY'
import json
from pathlib import Path

path = Path("reports/local/step20_forensics/step20_qwen_baseline_forensics.json")
data = json.loads(path.read_text())

assert data["schema_version"] == "forgeagent.step20_forensics.v0", data
assert data["task_count"] == 3, data
assert data["parsed_candidate_count"] == 3, data
assert data["parse_failure_count"] == 0, data
assert data["candidate_pipeline_attempted_count"] == 3, data
assert len(data["task_reports"]) == 3, data

print("forensics_json: OK")
print("task_count:", data["task_count"])
print("solved_tasks:", data["solved_tasks"])
print("parsed_candidate_count:", data["parsed_candidate_count"])
print("parse_failure_count:", data["parse_failure_count"])
print("candidate_pipeline_attempted_count:", data["candidate_pipeline_attempted_count"])
print("failure_mode_count:", data["failure_mode_count"])
PY

echo
echo "STEP20_1_DOCTOR_OK"

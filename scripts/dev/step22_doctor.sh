#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 22 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q \
  src/forgeagentcoder/agent/patch_hygiene.py \
  scripts/dev/analyze_step21_patch_hygiene.py
echo "compileall: OK"
echo

echo "=== Run patch hygiene analyzer ==="
PYTHONPATH=src python3 scripts/dev/analyze_step21_patch_hygiene.py
echo

REPORT_JSON="reports/local/step22_patch_hygiene/step22_patch_hygiene_report.json"
REPORT_MD="reports/local/step22_patch_hygiene/step22_patch_hygiene_report.md"

test -f "${REPORT_JSON}"
test -f "${REPORT_MD}"

python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("reports/local/step22_patch_hygiene/step22_patch_hygiene_report.json").read_text())
summary = data["summary"]

assert summary["schema_version"] == "forgeagent.patch_hygiene_report.v0", summary
assert summary["task_count"] == 3, summary
assert summary["generated_response_count"] == 3, summary
assert summary["diff_header_count"] == 3, summary
assert summary["step21_patch_apply_success_count"] == 0, summary
assert summary["step21_solved_tasks"] == 0, summary
assert summary["actionable_diff_like_count"] == 0, summary

print("patch_hygiene_report: OK")
print("task_count:", summary["task_count"])
print("generated_response_count:", summary["generated_response_count"])
print("diff_header_count:", summary["diff_header_count"])
print("markdown_fence_count:", summary["markdown_fence_count"])
print("prose_after_diff_count:", summary["prose_after_diff_count"])
print("has_change_lines_count:", summary["has_change_lines_count"])
print("non_actionable_no_change_lines_count:", summary["non_actionable_no_change_lines_count"])
print("actionable_diff_like_count:", summary["actionable_diff_like_count"])
print("recommended_next_step:", summary["interpretation"]["recommended_next_step"])
PY

echo
echo "STEP22_DOCTOR_OK"

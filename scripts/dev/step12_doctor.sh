#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 12 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/export_toy_trajectory_dataset.py
echo "compileall: OK"
echo

echo "=== Generate self-repair trajectory ==="
PYTHONPATH=src python3 scripts/dev/run_toy_self_repair.py >/tmp/forgeagent_step12_self_repair.log
tail -n 5 /tmp/forgeagent_step12_self_repair.log
echo

echo "=== Export trajectory dataset ==="
PYTHONPATH=src python3 scripts/dev/export_toy_trajectory_dataset.py
echo

test -f results/local/trajectory_dataset_v0/toy_self_repair_v0/patch_attempts.jsonl
test -f results/local/trajectory_dataset_v0/toy_self_repair_v0/sft_positive.jsonl
test -f results/local/trajectory_dataset_v0/toy_self_repair_v0/summary.json

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/trajectory_dataset_v0/toy_self_repair_v0")
summary = json.loads((root / "summary.json").read_text())
attempts = (root / "patch_attempts.jsonl").read_text().strip().splitlines()
positives = (root / "sft_positive.jsonl").read_text().strip().splitlines()

assert summary["total_attempts"] == 2, summary
assert summary["positive_attempts"] == 1, summary
assert summary["negative_attempts"] == 1, summary
assert len(attempts) == 2, attempts
assert len(positives) == 1, positives

first = json.loads(attempts[0])
second = json.loads(attempts[1])
positive = json.loads(positives[0])

assert first["label"] == "negative", first
assert second["label"] == "positive", second
assert positive["messages"][-1]["content"].strip().startswith("diff --git"), positive

print("trajectory_dataset_summary: OK")
print("patch_attempt_rows:", len(attempts))
print("sft_positive_rows:", len(positives))
print("best_patch_id:", summary["best_patch_id"])
PY

echo
echo "STEP12_DOCTOR_OK"

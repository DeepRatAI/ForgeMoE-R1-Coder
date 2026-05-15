#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 26 doctor ==="
python3 --version
echo

echo "=== Compile exporter ==="
python3 -m compileall -q scripts/dev/export_structured_intent_sft_dataset.py
echo "compileall: OK"
echo

echo "=== Run structured intent SFT dataset export ==="
PYTHONPATH=src python3 scripts/dev/export_structured_intent_sft_dataset.py
echo

RESULT_DIR="results/local/structured_intent_sft_dataset_v0"

test -f "${RESULT_DIR}/summary.json"
test -f "${RESULT_DIR}/sft_structured_intent.jsonl"
test -f "${RESULT_DIR}/trajectory_records.jsonl"
test -f "${RESULT_DIR}/dataset_card.md"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/structured_intent_sft_dataset_v0")

summary = json.loads((root / "summary.json").read_text())
sft_rows = [json.loads(line) for line in (root / "sft_structured_intent.jsonl").read_text().strip().splitlines()]
trajectory_rows = [json.loads(line) for line in (root / "trajectory_records.jsonl").read_text().strip().splitlines()]

assert summary["schema_version"] == "forgeagent.structured_intent_sft_dataset_summary.v0", summary
assert summary["dataset_name"] == "structured_intent_sft_dataset_v0", summary
assert summary["total_sft_rows"] == 3, summary
assert summary["total_trajectory_rows"] == 3, summary
assert summary["positive_reward_rows"] == 3, summary
assert summary["solved_rows"] == 3, summary
assert summary["average_reward"] == 1.0, summary
assert summary["all_targets_are_repaired_intents"] is True, summary
assert summary["all_rows_have_canonical_patch"] is True, summary

assert len(sft_rows) == 3, sft_rows
assert len(trajectory_rows) == 3, trajectory_rows

for row in sft_rows:
    assert row["schema_version"] == "forgeagent.structured_intent_sft_row.v0", row
    assert row["messages"][-1]["role"] == "assistant", row
    target = json.loads(row["target"])
    assert target["file_path"] == "app/utils.py", target
    assert target["find_text"], target
    assert target["replace_text"], target

for row in trajectory_rows:
    assert row["schema_version"] == "forgeagent.structured_intent_trajectory_record.v0", row
    assert row["reward"] == 1.0, row
    assert row["solved"] is True, row
    assert row["canonical_patch"], row

print("structured_intent_sft_dataset_summary: OK")
print("total_sft_rows:", summary["total_sft_rows"])
print("total_trajectory_rows:", summary["total_trajectory_rows"])
print("positive_reward_rows:", summary["positive_reward_rows"])
print("solved_rows:", summary["solved_rows"])
print("average_reward:", summary["average_reward"])
PY

echo
echo "STEP26_DOCTOR_OK"

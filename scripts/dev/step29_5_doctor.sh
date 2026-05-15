#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.5 doctor ==="
python3 --version
echo

echo "=== Compile curriculum builder ==="
python3 -m compileall -q scripts/dev/build_structured_sft_curriculum_v1.py
echo "compileall: OK"
echo

echo "=== Build structured SFT curriculum v1 ==="
PYTHONPATH=src python3 scripts/dev/build_structured_sft_curriculum_v1.py
echo

RESULT_DIR="results/local/structured_sft_curriculum_expansion_v1"

test -f "${RESULT_DIR}/all.jsonl"
test -f "${RESULT_DIR}/train.jsonl"
test -f "${RESULT_DIR}/eval.jsonl"
test -f "${RESULT_DIR}/summary.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/structured_sft_curriculum_expansion_v1")
summary = json.loads((root / "summary.json").read_text())

all_rows = [json.loads(line) for line in (root / "all.jsonl").read_text().splitlines() if line.strip()]
train_rows = [json.loads(line) for line in (root / "train.jsonl").read_text().splitlines() if line.strip()]
eval_rows = [json.loads(line) for line in (root / "eval.jsonl").read_text().splitlines() if line.strip()]

assert summary["schema_version"] == "forgeagent.structured_sft_curriculum_expansion_summary.v1", summary
assert summary["dataset_name"] == "structured_sft_curriculum_expansion_v1", summary
assert summary["total_rows"] == 192, summary
assert summary["train_rows"] == 160, summary
assert summary["eval_rows"] == 32, summary
assert summary["case_count"] == 16, summary
assert summary["category_count"] == 12, summary
assert len(summary["category_counts"]) == 12, summary
assert all(count == 16 for count in summary["category_counts"].values()), summary
assert summary["launches_training_job"] is False, summary
assert summary["gpu_required"] is False, summary
assert summary["cost_gate"]["requires_explicit_approval_before_training"] is True, summary

assert len(all_rows) == 192, len(all_rows)
assert len(train_rows) == 160, len(train_rows)
assert len(eval_rows) == 32, len(eval_rows)

seen = set()
for row in all_rows:
    assert row["schema_version"] == "forgeagent.sft_row.v1", row
    assert row["task_id"] not in seen, row["task_id"]
    seen.add(row["task_id"])
    assert row["messages"][0]["role"] == "system", row
    assert row["messages"][1]["role"] == "user", row

    target = json.loads(row["target_text"])
    assert target["schema_version"] == "forgeagent.structured_intent.v1", target
    assert target["task_id"] == row["task_id"], target
    assert target["category"] == row["category"], target
    assert target["target_files"], target
    assert target["operations"], target
    assert target["verification"], target

print("structured_sft_curriculum_v1: OK")
print("total_rows:", summary["total_rows"])
print("train_rows:", summary["train_rows"])
print("eval_rows:", summary["eval_rows"])
print("case_count:", summary["case_count"])
print("category_count:", summary["category_count"])
print("categories:", ",".join(sorted(summary["category_counts"].keys())))
PY

echo

grep -q "Structured SFT Curriculum Expansion" docs/engineering/ADR_0031_STRUCTURED_SFT_CURRICULUM_EXPANSION.md

echo "docs: OK"
echo
echo "STEP29_5_DOCTOR_OK"

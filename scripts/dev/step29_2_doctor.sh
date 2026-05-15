#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 29.2 doctor ==="
python3 --version
echo

echo "=== Compile dataset expansion builder ==="
python3 -m compileall -q scripts/dev/build_structured_sft_dataset_expansion.py
echo "compileall: OK"
echo

echo "=== Build structured SFT dataset expansion ==="
PYTHONPATH=src python3 scripts/dev/build_structured_sft_dataset_expansion.py
echo

RESULT_DIR="results/local/structured_sft_dataset_expansion_v0"

test -f "${RESULT_DIR}/all.jsonl"
test -f "${RESULT_DIR}/train.jsonl"
test -f "${RESULT_DIR}/eval.jsonl"
test -f "${RESULT_DIR}/summary.json"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/structured_sft_dataset_expansion_v0")

summary = json.loads((root / "summary.json").read_text())
all_rows = [json.loads(line) for line in (root / "all.jsonl").read_text().splitlines() if line.strip()]
train_rows = [json.loads(line) for line in (root / "train.jsonl").read_text().splitlines() if line.strip()]
eval_rows = [json.loads(line) for line in (root / "eval.jsonl").read_text().splitlines() if line.strip()]

assert summary["schema_version"] == "forgeagent.structured_sft_dataset_expansion_summary.v0", summary
assert summary["total_rows"] == 48, summary
assert summary["train_rows"] == 40, summary
assert summary["eval_rows"] == 8, summary
assert len(all_rows) == 48, len(all_rows)
assert len(train_rows) == 40, len(train_rows)
assert len(eval_rows) == 8, len(eval_rows)
assert len(summary["category_counts"]) == 8, summary

for row in all_rows:
    assert row["schema_version"] == "forgeagent.sft_row.v0", row
    assert row["messages"][0]["role"] == "system", row
    assert row["messages"][1]["role"] == "user", row
    target = json.loads(row["target_text"])
    assert target["schema_version"] == "forgeagent.structured_intent.v0", target
    assert target["operations"], target
    assert target["verification"], target

print("dataset_expansion: OK")
print("total_rows:", summary["total_rows"])
print("train_rows:", summary["train_rows"])
print("eval_rows:", summary["eval_rows"])
print("categories:", ",".join(sorted(summary["category_counts"].keys())))
PY

echo

grep -q "Expand Structured SFT Dataset" docs/engineering/ADR_0029_EXPAND_DATASET_BEFORE_GPU_TRAINING.md

echo "docs: OK"
echo
echo "STEP29_2_DOCTOR_OK"

#!/usr/bin/env bash
set -euo pipefail

VENV="${FORGEMOE_STEP29_3_VENV:-/tmp/forgemoe-step29-3-venv}"

echo "=== Step 29.3 doctor ==="
"${VENV}/bin/python" --version
echo

echo "=== Dependency check ==="
"${VENV}/bin/python" - <<'PY'
import transformers
print("transformers:", transformers.__version__)
PY
echo

echo "=== Compile tokenizer refresh script ==="
"${VENV}/bin/python" -m compileall -q scripts/dev/tokenize_structured_sft_dataset.py
echo "compileall: OK"
echo

echo "=== Run tokenizer refresh ==="
PYTHONPATH=src \
HF_HOME="${HF_HOME:-/tmp/forgemoe-hf-cache}" \
HF_HUB_CACHE="${HF_HUB_CACHE:-/tmp/forgemoe-hf-cache/hub}" \
FORGEMOE_STEP29_3_MODEL_ID="${FORGEMOE_STEP29_3_MODEL_ID:-Qwen/Qwen2.5-Coder-0.5B-Instruct}" \
"${VENV}/bin/python" scripts/dev/tokenize_structured_sft_dataset.py
echo

RESULT_DIR="results/local/structured_sft_tokenization_refresh_v0"

test -f "${RESULT_DIR}/rendered_all.jsonl"
test -f "${RESULT_DIR}/rendered_train.jsonl"
test -f "${RESULT_DIR}/rendered_eval.jsonl"
test -f "${RESULT_DIR}/tokenization_report.json"
test -f "${RESULT_DIR}/training_manifest.json"

"${VENV}/bin/python" - <<'PY'
import json
from pathlib import Path

root = Path("results/local/structured_sft_tokenization_refresh_v0")
report = json.loads((root / "tokenization_report.json").read_text())
manifest = json.loads((root / "training_manifest.json").read_text())

rendered_all = [json.loads(line) for line in (root / "rendered_all.jsonl").read_text().splitlines() if line.strip()]
rendered_train = [json.loads(line) for line in (root / "rendered_train.jsonl").read_text().splitlines() if line.strip()]
rendered_eval = [json.loads(line) for line in (root / "rendered_eval.jsonl").read_text().splitlines() if line.strip()]

assert report["schema_version"] == "forgeagent.structured_sft_tokenization_report.v0", report
assert manifest["schema_version"] == "forgeagent.structured_sft_training_manifest.v0", manifest
assert report["model_id"] == "Qwen/Qwen2.5-Coder-0.5B-Instruct", report
assert report["full_weight_load_attempted"] is False, report
assert report["launches_training_job"] is False, report
assert report["gpu_required"] is False, report
assert report["all"]["row_count"] == 48, report
assert report["train"]["row_count"] == 40, report
assert report["eval"]["row_count"] == 8, report
assert report["all"]["would_truncate_count"] == 0, report
assert manifest["tokenization_gate"]["passed"] is True, manifest
assert manifest["cost_gate"]["requires_explicit_approval_before_launch"] is True, manifest

assert len(rendered_all) == 48, len(rendered_all)
assert len(rendered_train) == 40, len(rendered_train)
assert len(rendered_eval) == 8, len(rendered_eval)

for row in rendered_all:
    assert row["schema_version"] == "forgeagent.rendered_sft_row.v0", row
    assert row["text"].strip(), row
    assert row["target_text"].strip(), row

print("tokenization_refresh: OK")
print("total_rows:", manifest["total_rows"])
print("train_rows:", manifest["train_rows"])
print("eval_rows:", manifest["eval_rows"])
print("max_seq_length:", manifest["max_seq_length"])
print("max_tokens:", report["all"]["max_tokens"])
print("p95_tokens:", report["all"]["p95_tokens"])
print("would_truncate_count:", report["all"]["would_truncate_count"])
print("tokenization_gate_passed:", manifest["tokenization_gate"]["passed"])
PY

echo

grep -q "Tokenize Expanded Structured SFT Dataset" docs/engineering/ADR_0030_TOKENIZE_EXPANDED_DATASET_BEFORE_GPU_TRAINING.md

echo "docs: OK"
echo
echo "STEP29_3_DOCTOR_OK"

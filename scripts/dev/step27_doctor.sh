#!/usr/bin/env bash
set -euo pipefail

VENV="${FORGEMOE_STEP27_VENV:-/tmp/forgemoe-step20-venv}"

echo "=== Step 27 doctor ==="
"${VENV}/bin/python" --version
echo

echo "=== Dependency check ==="
"${VENV}/bin/python" - <<'PY'
import transformers
print("transformers:", transformers.__version__)
PY
echo

echo "=== Compile source ==="
"${VENV}/bin/python" -m compileall -q \
  src/forgeagentcoder/training \
  scripts/dev/prepare_structured_intent_training_data.py
echo "compileall: OK"
echo

echo "=== Run training data preparation ==="
PYTHONPATH=src \
HF_HOME="${HF_HOME:-/tmp/forgemoe-hf-cache}" \
HF_HUB_CACHE="${HF_HUB_CACHE:-/tmp/forgemoe-hf-cache/hub}" \
FORGEMOE_STEP27_MODEL_ID="${FORGEMOE_STEP27_MODEL_ID:-Qwen/Qwen2.5-Coder-0.5B-Instruct}" \
"${VENV}/bin/python" scripts/dev/prepare_structured_intent_training_data.py
echo

RESULT_DIR="results/local/local_adapter_training_plan_v0"

test -f "${RESULT_DIR}/training_manifest.json"
test -f "${RESULT_DIR}/tokenization_report.json"
test -f "${RESULT_DIR}/train.jsonl"
test -f "${RESULT_DIR}/eval.jsonl"
test -f "${RESULT_DIR}/all_validated_examples.jsonl"
test -f "${RESULT_DIR}/validation_issues.json"
test -f "${RESULT_DIR}/rendered_preview.json"

"${VENV}/bin/python" - <<'PY'
import json
from pathlib import Path

root = Path("results/local/local_adapter_training_plan_v0")

manifest = json.loads((root / "training_manifest.json").read_text())
token_report = json.loads((root / "tokenization_report.json").read_text())
issues = json.loads((root / "validation_issues.json").read_text())

train_rows = (root / "train.jsonl").read_text().strip().splitlines()
eval_rows = (root / "eval.jsonl").read_text().strip().splitlines()
all_rows = (root / "all_validated_examples.jsonl").read_text().strip().splitlines()

assert manifest["schema_version"] == "forgeagent.local_adapter_training_plan.v0", manifest
assert manifest["plan_name"] == "local_adapter_training_plan_v0", manifest
assert manifest["model_id"] == "Qwen/Qwen2.5-Coder-0.5B-Instruct", manifest
assert manifest["total_rows"] == 3, manifest
assert manifest["validation_issue_count"] == 0, manifest
assert manifest["train_rows"] == 2, manifest
assert manifest["eval_rows"] == 1, manifest
assert manifest["adapter_strategy"]["this_step_trains_model"] is False, manifest

assert token_report["schema_version"] == "forgeagent.tokenization_report.v0", token_report
assert token_report["stats"]["row_count"] == 3, token_report
assert token_report["stats"]["max_tokens"] > 0, token_report

assert issues == [], issues
assert len(train_rows) == 2, train_rows
assert len(eval_rows) == 1, eval_rows
assert len(all_rows) == 3, all_rows

print("local_adapter_training_plan: OK")
print("total_rows:", manifest["total_rows"])
print("train_rows:", manifest["train_rows"])
print("eval_rows:", manifest["eval_rows"])
print("validation_issue_count:", manifest["validation_issue_count"])
print("tokenizer_class:", manifest["tokenizer_class"])
print("token_min:", token_report["stats"]["min_tokens"])
print("token_max:", token_report["stats"]["max_tokens"])
print("token_mean:", token_report["stats"]["mean_tokens"])
PY

echo
echo "STEP27_DOCTOR_OK"

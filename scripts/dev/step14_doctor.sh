#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 14 doctor ==="
python3 --version
echo

echo "=== Compile source ==="
python3 -m compileall -q src scripts/dev/run_toy_model_io.py
echo "compileall: OK"
echo

echo "=== Run toy model I/O ==="
PYTHONPATH=src python3 scripts/dev/run_toy_model_io.py
echo

test -f results/local/toy_model_io_v0/prompt_messages.json
test -f results/local/toy_model_io_v0/raw_model_response.txt
test -f results/local/toy_model_io_v0/parsed.patch
test -f results/local/toy_model_io_v0/eval_result.json

python3 - <<'PY'
import json
from pathlib import Path

root = Path("results/local/toy_model_io_v0")
messages = json.loads((root / "prompt_messages.json").read_text())
patch = (root / "parsed.patch").read_text()
result = json.loads((root / "eval_result.json").read_text())

assert len(messages) == 2, messages
assert messages[0]["role"] == "system", messages
assert messages[1]["role"] == "user", messages
assert patch.startswith("diff --git "), patch
assert result["patch_applied"] is True, result
assert result["post_test"]["passed"] is True, result

print("prompt_messages: OK")
print("parsed_patch: OK")
print("eval_result: OK")
print("reward:", result["reward"])
PY

echo
echo "STEP14_DOCTOR_OK"

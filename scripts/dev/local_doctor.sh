#!/usr/bin/env bash
set -euo pipefail

echo "=== Local project doctor ==="
python3 --version
echo

echo "=== Tree ==="
find . -maxdepth 3 -type f | sort
echo

echo "=== Configs ==="
python3 - <<'PY'
from pathlib import Path
import yaml

for path in [
    "configs/aws/paths.yaml",
    "configs/models/qwen3_coder_30b_a3b.yaml",
    "configs/eval/fullstack_agent_eval_v0.yaml",
    "configs/training/qlora_agentic_sft_v0.yaml",
]:
    p = Path(path)
    assert p.exists(), f"Missing {p}"
    yaml.safe_load(p.read_text())
    print(f"OK {p}")
PY

echo
echo "LOCAL_DOCTOR_OK"

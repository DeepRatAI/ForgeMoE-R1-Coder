#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 17.6 doctor ==="
python3 --version
echo

test -f docs/engineering/ENGINEERING_DECISION_RECORD.md
test -f docs/engineering/PROJECT_RECAP_AND_ROADMAP.md

grep -q "ADR-0001" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "BUG-0001" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "ModelAdapter" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "executable verifier" docs/engineering/ENGINEERING_DECISION_RECORD.md
grep -q "Step 18" docs/engineering/PROJECT_RECAP_AND_ROADMAP.md

python3 - <<'PY'
from pathlib import Path

edr = Path("docs/engineering/ENGINEERING_DECISION_RECORD.md").read_text()
recap = Path("docs/engineering/PROJECT_RECAP_AND_ROADMAP.md").read_text()

assert edr.count("ADR-") >= 12, "Expected at least 12 ADR entries"
assert edr.count("BUG-") >= 5, "Expected at least 5 bug/failure entries"
assert "AWS access keys" in edr, "Expected security warning"
assert "real model" in recap.lower(), "Expected real model roadmap"

print("engineering_decision_record: OK")
print("project_recap_and_roadmap: OK")
print("adr_count:", edr.count("ADR-"))
print("bug_count:", edr.count("BUG-"))
PY

echo
echo "STEP17_6_DOCTOR_OK"

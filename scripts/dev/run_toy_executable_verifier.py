from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.patch_provider import PatchCandidate
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.verifier.executable_verifier import run_executable_verifier


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_task(root: Path) -> tuple[Path, list[PatchCandidate]]:
    if root.exists():
        shutil.rmtree(root)

    repo = root / "repo"
    task_dir = root / "task"
    patch_dir = root / "patches"

    write(repo / "app" / "__init__.py", "")

    write(
        repo / "app" / "utils.py",
        '''def is_even(n: int) -> bool:
    return True
''',
    )

    write(
        repo / "tests" / "test_utils.py",
        '''import unittest
from app.utils import is_even

class TestUtils(unittest.TestCase):
    def test_even_number(self):
        self.assertTrue(is_even(2))

    def test_odd_number(self):
        self.assertFalse(is_even(3))

if __name__ == "__main__":
    unittest.main()
''',
    )

    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": "toy-verifier-is-even-bugfix",
        "task_type": "unit_bugfix",
        "title": "Fix is_even implementation",
        "description": "is_even always returns True. It should detect parity.",
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }

    write(task_dir / "task.json", json.dumps(task, indent=2))

    bad_patch_false = '''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def is_even(n: int) -> bool:
-    return True
+    return False
'''

    bad_patch_identity = '''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def is_even(n: int) -> bool:
-    return True
+    return bool(n)
'''

    good_patch = '''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def is_even(n: int) -> bool:
-    return True
+    return n % 2 == 0
'''

    bad_false_path = patch_dir / "bad_false.patch"
    bad_identity_path = patch_dir / "bad_identity.patch"
    good_path = patch_dir / "good.patch"

    write(bad_false_path, bad_patch_false)
    write(bad_identity_path, bad_patch_identity)
    write(good_path, good_patch)

    candidates = [
        PatchCandidate(
            patch_id="bad_patch_always_false",
            patch_path=bad_false_path,
            description="Incorrect: always false.",
        ),
        PatchCandidate(
            patch_id="bad_patch_bool_identity",
            patch_path=bad_identity_path,
            description="Incorrect: bool(n) is true for both 2 and 3.",
        ),
        PatchCandidate(
            patch_id="good_patch_modulo",
            patch_path=good_path,
            description="Correct: n % 2 == 0.",
        ),
    ]

    return task_dir / "task.json", candidates


def main() -> None:
    root = PROJECT_ROOT / "tmp" / "toy_executable_verifier_v0"
    work_root = PROJECT_ROOT / "tmp" / "toy_executable_verifier_runs"
    output_json = PROJECT_ROOT / "results" / "local" / "toy_executable_verifier_v0" / "verification.json"

    task_json, candidates = build_task(root)
    task = AgentTask.from_json_file(task_json)

    result = run_executable_verifier(
        task=task,
        candidates=candidates,
        work_root=work_root,
        output_json=output_json,
    )

    print(json.dumps(json.loads(output_json.read_text()), indent=2))

    if not result.solved:
        raise SystemExit("Expected verifier to select a solving patch")
    if result.selected_patch_id != "good_patch_modulo":
        raise SystemExit(f"Unexpected selected_patch_id: {result.selected_patch_id}")
    if result.candidate_count != 3:
        raise SystemExit(f"Expected 3 candidates, got {result.candidate_count}")

    print("TOY_EXECUTABLE_VERIFIER_OK")


if __name__ == "__main__":
    main()

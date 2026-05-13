from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.patch_provider import PatchCandidate, ScriptedPatchProvider
from forgeagentcoder.agent.self_repair import run_self_repair_loop
from forgeagentcoder.data.task_schema import AgentTask


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_task(root: Path) -> tuple[Path, Path, Path]:
    if root.exists():
        shutil.rmtree(root)

    repo = root / "repo"
    task_dir = root / "task"
    patch_dir = root / "patches"

    write(repo / "app" / "__init__.py", "")

    write(
        repo / "app" / "utils.py",
        '''def multiply(a: int, b: int) -> int:
    return a + b
''',
    )

    write(
        repo / "tests" / "test_utils.py",
        '''import unittest
from app.utils import multiply

class TestUtils(unittest.TestCase):
    def test_multiply(self):
        self.assertEqual(multiply(2, 3), 6)
        self.assertEqual(multiply(-2, 3), -6)

if __name__ == "__main__":
    unittest.main()
''',
    )

    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": "toy-self-repair-multiply-bugfix",
        "task_type": "unit_bugfix",
        "title": "Fix multiply implementation",
        "description": "multiply currently adds instead of multiplying.",
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }

    write(task_dir / "task.json", json.dumps(task, indent=2))

    bad_patch = '''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def multiply(a: int, b: int) -> int:
-    return a + b
+    return a - b
'''

    good_patch = '''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def multiply(a: int, b: int) -> int:
-    return a + b
+    return a * b
'''

    bad_patch_path = patch_dir / "bad.patch"
    good_patch_path = patch_dir / "good.patch"

    write(bad_patch_path, bad_patch)
    write(good_patch_path, good_patch)

    return task_dir / "task.json", bad_patch_path, good_patch_path


def main() -> None:
    root = PROJECT_ROOT / "tmp" / "toy_self_repair_v0"
    work_root = PROJECT_ROOT / "tmp" / "toy_self_repair_runs"
    output_json = PROJECT_ROOT / "results" / "local" / "toy_self_repair_v0" / "trajectory.json"

    task_json, bad_patch, good_patch = build_task(root)

    task = AgentTask.from_json_file(task_json)
    provider = ScriptedPatchProvider(
        [
            PatchCandidate(
                patch_id="bad_patch_subtraction",
                patch_path=bad_patch,
                description="Incorrect attempt: subtraction.",
            ),
            PatchCandidate(
                patch_id="good_patch_multiplication",
                patch_path=good_patch,
                description="Correct attempt: multiplication.",
            ),
        ]
    )

    result = run_self_repair_loop(
        task=task,
        patch_provider=provider,
        work_root=work_root,
        max_iterations=3,
        output_json=output_json,
    )

    print(json.dumps(json.loads(output_json.read_text()), indent=2))

    if not result.solved:
        raise SystemExit("Expected self-repair loop to solve the task")
    if result.iterations_used != 2:
        raise SystemExit(f"Expected 2 iterations, got {result.iterations_used}")
    if result.best_patch_id != "good_patch_multiplication":
        raise SystemExit(f"Unexpected best_patch_id: {result.best_patch_id}")

    print("TOY_SELF_REPAIR_OK")


if __name__ == "__main__":
    main()

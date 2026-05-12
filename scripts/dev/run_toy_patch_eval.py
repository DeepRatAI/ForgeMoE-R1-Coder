from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.patch_task_eval import evaluate_patch_task


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_toy_task(root: Path) -> tuple[Path, Path]:
    if root.exists():
        shutil.rmtree(root)

    repo = root / "repo"
    task_dir = root / "task"
    patch_dir = root / "patches"

    write(
        repo / "app" / "__init__.py",
        "",
    )

    write(
        repo / "app" / "math_utils.py",
        '''def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a - b
''',
    )

    write(
        repo / "tests" / "test_math_utils.py",
        '''import unittest

from app.math_utils import add


class TestMathUtils(unittest.TestCase):
    def test_add_positive_numbers(self):
        self.assertEqual(add(2, 3), 5)

    def test_add_negative_numbers(self):
        self.assertEqual(add(-2, -3), -5)


if __name__ == "__main__":
    unittest.main()
''',
    )

    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": "toy-python-add-bugfix",
        "task_type": "unit_bugfix",
        "title": "Fix incorrect add implementation",
        "description": "The add function subtracts instead of adding. Fix it without changing tests.",
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }

    write(task_dir / "task.json", json.dumps(task, indent=2))

    patch = '''diff --git a/app/math_utils.py b/app/math_utils.py
--- a/app/math_utils.py
+++ b/app/math_utils.py
@@ -1,3 +1,3 @@
 def add(a: int, b: int) -> int:
     """Return the sum of two integers."""
-    return a - b
+    return a + b
'''

    write(patch_dir / "gold.patch", patch)

    return task_dir / "task.json", patch_dir / "gold.patch"


def main() -> None:
    root = PROJECT_ROOT / "tmp" / "toy_tasks" / "toy_python_add"
    result_path = PROJECT_ROOT / "results" / "local" / "toy_patch_eval_result.json"
    work_root = PROJECT_ROOT / "tmp" / "toy_runs"

    task_json, patch_file = build_toy_task(root)
    task = AgentTask.from_json_file(task_json)

    result = evaluate_patch_task(
        task,
        patch_file=patch_file,
        work_root=work_root,
        output_json=result_path,
    )

    print(json.dumps(json.loads(result_path.read_text()), indent=2))

    if not result.patch_applied:
        raise SystemExit("Patch failed to apply")
    if not result.post_tests_passed:
        raise SystemExit("Post-patch tests failed")

    print("TOY_PATCH_EVAL_OK")


if __name__ == "__main__":
    main()

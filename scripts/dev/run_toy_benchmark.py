from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.eval.batch_eval import load_task_specs, run_batch_patch_eval


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_task(
    *,
    root: Path,
    task_id: str,
    title: str,
    description: str,
    module_code: str,
    test_code: str,
    patch: str,
) -> dict:
    repo = root / task_id / "repo"
    task_dir = root / task_id / "task"
    patch_dir = root / task_id / "patches"

    write(repo / "app" / "__init__.py", "")
    write(repo / "app" / "utils.py", module_code)
    write(repo / "tests" / "test_utils.py", test_code)

    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": task_id,
        "task_type": "unit_bugfix",
        "title": title,
        "description": description,
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }

    write(task_dir / "task.json", json.dumps(task, indent=2))
    write(patch_dir / "gold.patch", patch)

    return {
        "task_json": str((task_dir / "task.json").relative_to(root)),
        "patch_file": str((patch_dir / "gold.patch").relative_to(root)),
    }


def build_benchmark(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)

    tasks = []

    tasks.append(
        build_task(
            root=root,
            task_id="toy-add-bugfix",
            title="Fix add implementation",
            description="add subtracts instead of adding.",
            module_code='''def add(a: int, b: int) -> int:
    return a - b
''',
            test_code='''import unittest
from app.utils import add

class TestUtils(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-2, -3), -5)

if __name__ == "__main__":
    unittest.main()
''',
            patch='''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def add(a: int, b: int) -> int:
-    return a - b
+    return a + b
''',
        )
    )

    tasks.append(
        build_task(
            root=root,
            task_id="toy-reverse-bugfix",
            title="Fix reverse_string implementation",
            description="reverse_string currently returns the original string.",
            module_code='''def reverse_string(value: str) -> str:
    return value
''',
            test_code='''import unittest
from app.utils import reverse_string

class TestUtils(unittest.TestCase):
    def test_reverse_string(self):
        self.assertEqual(reverse_string("abc"), "cba")
        self.assertEqual(reverse_string(""), "")

if __name__ == "__main__":
    unittest.main()
''',
            patch='''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def reverse_string(value: str) -> str:
-    return value
+    return value[::-1]
''',
        )
    )

    tasks.append(
        build_task(
            root=root,
            task_id="toy-normalize-bugfix",
            title="Fix normalize_name implementation",
            description="normalize_name should strip spaces and lowercase.",
            module_code='''def normalize_name(value: str) -> str:
    return value.strip()
''',
            test_code='''import unittest
from app.utils import normalize_name

class TestUtils(unittest.TestCase):
    def test_normalize_name(self):
        self.assertEqual(normalize_name(" Alice "), "alice")
        self.assertEqual(normalize_name("BOB"), "bob")

if __name__ == "__main__":
    unittest.main()
''',
            patch='''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def normalize_name(value: str) -> str:
-    return value.strip()
+    return value.strip().lower()
''',
        )
    )

    benchmark_spec = {
        "benchmark_name": "toy_agentic_patch_benchmark_v0",
        "tasks": tasks,
    }

    spec_path = root / "benchmark.json"
    write(spec_path, json.dumps(benchmark_spec, indent=2))
    return spec_path


def main() -> None:
    benchmark_root = PROJECT_ROOT / "tmp" / "toy_benchmark_v0"
    output_dir = PROJECT_ROOT / "results" / "local" / "toy_benchmark_v0"
    work_root = PROJECT_ROOT / "tmp" / "toy_benchmark_runs"

    spec_path = build_benchmark(benchmark_root)
    specs = load_task_specs(spec_path)

    summary = run_batch_patch_eval(
        benchmark_name="toy_agentic_patch_benchmark_v0",
        task_specs=specs,
        work_root=work_root,
        output_dir=output_dir,
    )

    print(json.dumps(summary.__dict__, indent=2))

    if summary.total_tasks != 3:
        raise SystemExit("Expected 3 tasks")
    if summary.solved_tasks != 3:
        raise SystemExit("Expected all tasks solved")
    if summary.pass_rate != 1.0:
        raise SystemExit("Expected pass_rate=1.0")

    print("TOY_BENCHMARK_OK")


if __name__ == "__main__":
    main()

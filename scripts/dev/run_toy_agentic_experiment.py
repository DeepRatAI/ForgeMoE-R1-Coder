from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.candidate_pipeline import run_candidate_generation_pipeline
from forgeagentcoder.agent.mock_model import MockPatchModel, RawModelResponse
from forgeagentcoder.agent.prompt_builder import build_patch_generation_messages
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.command_runner import run_shell_command
from forgeagentcoder.eval.experiment_runner import (
    candidate_result_to_task_result,
    write_experiment_outputs,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_task(
    *,
    root: Path,
    task_id: str,
    function_code: str,
    test_code: str,
    good_patch: str,
    bad_patch: str,
    title: str,
    description: str,
) -> tuple[Path, list[RawModelResponse]]:
    repo = root / task_id / "repo"
    task_dir = root / task_id / "task"

    write(repo / "app" / "__init__.py", "")
    write(repo / "app" / "utils.py", function_code)
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

    responses = [
        RawModelResponse(
            response_id=f"{task_id}_invalid",
            text="The issue is obvious. I would fix the implementation.",
        ),
        RawModelResponse(
            response_id=f"{task_id}_bad",
            text=bad_patch,
        ),
        RawModelResponse(
            response_id=f"{task_id}_good",
            text=good_patch,
        ),
    ]

    return task_dir / "task.json", responses


def build_experiment(root: Path) -> list[tuple[Path, list[RawModelResponse]]]:
    if root.exists():
        shutil.rmtree(root)

    tasks: list[tuple[Path, list[RawModelResponse]]] = []

    tasks.append(
        build_task(
            root=root,
            task_id="toy-exp-square-bugfix",
            title="Fix square implementation",
            description="square should return x multiplied by itself.",
            function_code='''def square(x: int) -> int:
    return x + x
''',
            test_code='''import unittest
from app.utils import square

class TestUtils(unittest.TestCase):
    def test_square(self):
        self.assertEqual(square(3), 9)
        self.assertEqual(square(-4), 16)

if __name__ == "__main__":
    unittest.main()
''',
            bad_patch='''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def square(x: int) -> int:
-    return x + x
+    return x - x
''',
            good_patch='''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def square(x: int) -> int:
-    return x + x
+    return x * x
''',
        )
    )

    tasks.append(
        build_task(
            root=root,
            task_id="toy-exp-negate-bugfix",
            title="Fix negate implementation",
            description="negate should return the arithmetic negation.",
            function_code='''def negate(x: int) -> int:
    return x
''',
            test_code='''import unittest
from app.utils import negate

class TestUtils(unittest.TestCase):
    def test_negate(self):
        self.assertEqual(negate(5), -5)
        self.assertEqual(negate(-3), 3)

if __name__ == "__main__":
    unittest.main()
''',
            bad_patch='''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def negate(x: int) -> int:
-    return x
+    return abs(x)
''',
            good_patch='''diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def negate(x: int) -> int:
-    return x
+    return -x
''',
        )
    )

    return tasks


def main() -> None:
    experiment_name = "toy_agentic_experiment_v0"
    experiment_root = PROJECT_ROOT / "tmp" / experiment_name
    output_dir = PROJECT_ROOT / "results" / "local" / experiment_name
    task_output_root = output_dir / "tasks"
    work_root = PROJECT_ROOT / "tmp" / "toy_agentic_experiment_runs"

    started = time.time()
    task_specs = build_experiment(experiment_root)

    task_results = []

    for task_json, raw_responses in task_specs:
        task = AgentTask.from_json_file(task_json)

        pre_test = run_shell_command(
            task.test_command,
            cwd=task.repo_dir,
            timeout_seconds=task.timeout_seconds,
        )

        messages = build_patch_generation_messages(
            task,
            pre_test_stderr=pre_test.stderr,
        )

        mock_model = MockPatchModel(raw_responses)
        generated = mock_model.generate(messages, n=3)

        task_output_dir = task_output_root / task.task_id

        result = run_candidate_generation_pipeline(
            task=task,
            raw_responses=generated,
            patch_output_dir=task_output_dir / "parsed_patches",
            work_root=work_root,
            output_json=task_output_dir / "generation_pipeline_result.json",
        )

        task_results.append(
            candidate_result_to_task_result(
                result,
                result_path=task_output_dir / "generation_pipeline_result.json",
            )
        )

    summary = write_experiment_outputs(
        experiment_name=experiment_name,
        task_results=task_results,
        output_dir=output_dir,
        started_at=started,
    )

    print(json.dumps(summary.__dict__, indent=2))

    if summary.total_tasks != 2:
        raise SystemExit("Expected 2 tasks")
    if summary.solved_tasks != 2:
        raise SystemExit("Expected all tasks solved")
    if summary.solve_rate != 1.0:
        raise SystemExit("Expected solve_rate=1.0")
    if summary.total_parse_failures != 2:
        raise SystemExit("Expected 2 parse failures")

    print("TOY_AGENTIC_EXPERIMENT_OK")


if __name__ == "__main__":
    main()

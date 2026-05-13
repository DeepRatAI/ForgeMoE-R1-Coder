from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.candidate_pipeline import run_candidate_generation_pipeline
from forgeagentcoder.agent.mock_model import MockPatchModel, RawModelResponse
from forgeagentcoder.agent.prompt_builder import build_patch_generation_messages, write_messages_json
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.command_runner import run_shell_command


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_task(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)

    repo = root / "repo"
    task_dir = root / "task"

    write(repo / "app" / "__init__.py", "")

    write(
        repo / "app" / "utils.py",
        '''def abs_value(x: int) -> int:
    return x
''',
    )

    write(
        repo / "tests" / "test_utils.py",
        '''import unittest
from app.utils import abs_value

class TestUtils(unittest.TestCase):
    def test_abs_value(self):
        self.assertEqual(abs_value(5), 5)
        self.assertEqual(abs_value(-5), 5)

if __name__ == "__main__":
    unittest.main()
''',
    )

    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": "toy-candidate-pipeline-abs-bugfix",
        "task_type": "unit_bugfix",
        "title": "Fix abs_value implementation",
        "description": "abs_value should return the absolute value of an integer.",
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }

    write(task_dir / "task.json", json.dumps(task, indent=2))
    return task_dir / "task.json"


def main() -> None:
    root = PROJECT_ROOT / "tmp" / "toy_candidate_pipeline_v0"
    output_dir = PROJECT_ROOT / "results" / "local" / "toy_candidate_pipeline_v0"
    patch_output_dir = output_dir / "parsed_patches"
    work_root = PROJECT_ROOT / "tmp" / "toy_candidate_pipeline_runs"

    task_json = build_task(root)
    task = AgentTask.from_json_file(task_json)

    pre_test = run_shell_command(
        task.test_command,
        cwd=task.repo_dir,
        timeout_seconds=task.timeout_seconds,
    )

    messages = build_patch_generation_messages(task, pre_test_stderr=pre_test.stderr)
    write_messages_json(output_dir / "prompt_messages.json", messages)

    bad_patch = """```diff
diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def abs_value(x: int) -> int:
-    return x
+    return -x
```"""

    good_patch = """diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def abs_value(x: int) -> int:
-    return x
+    return abs(x)
"""

    mock_model = MockPatchModel(
        [
            RawModelResponse(
                response_id="raw_invalid_0",
                text="I would fix the function by checking if the number is negative.",
            ),
            RawModelResponse(
                response_id="raw_bad_1",
                text=bad_patch,
            ),
            RawModelResponse(
                response_id="raw_good_2",
                text=good_patch,
            ),
        ]
    )

    raw_responses = mock_model.generate(messages, n=3)

    result = run_candidate_generation_pipeline(
        task=task,
        raw_responses=raw_responses,
        patch_output_dir=patch_output_dir,
        work_root=work_root,
        output_json=output_dir / "generation_pipeline_result.json",
    )

    print(json.dumps(json.loads((output_dir / "generation_pipeline_result.json").read_text()), indent=2))

    if not result.solved:
        raise SystemExit("Expected pipeline to solve task")
    if result.raw_response_count != 3:
        raise SystemExit("Expected 3 raw responses")
    if result.parsed_candidate_count != 2:
        raise SystemExit(f"Expected 2 parsed candidates, got {result.parsed_candidate_count}")
    if result.parse_failure_count != 1:
        raise SystemExit(f"Expected 1 parse failure, got {result.parse_failure_count}")
    if result.selected_patch_id != "raw_good_2_candidate_2":
        raise SystemExit(f"Unexpected selected_patch_id: {result.selected_patch_id}")

    print("TOY_CANDIDATE_PIPELINE_OK")


if __name__ == "__main__":
    main()

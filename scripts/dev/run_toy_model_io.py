from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.patch_parser import extract_unified_diff, write_patch
from forgeagentcoder.agent.prompt_builder import build_patch_generation_messages, write_messages_json
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.command_runner import run_shell_command
from forgeagentcoder.eval.patch_task_eval import evaluate_patch_task


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
        '''def clamp(value: int, minimum: int, maximum: int) -> int:
    return value
''',
    )

    write(
        repo / "tests" / "test_utils.py",
        '''import unittest
from app.utils import clamp

class TestUtils(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(-5, 0, 10), 0)
        self.assertEqual(clamp(15, 0, 10), 10)

if __name__ == "__main__":
    unittest.main()
''',
    )

    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": "toy-model-io-clamp-bugfix",
        "task_type": "unit_bugfix",
        "title": "Fix clamp implementation",
        "description": "clamp should bound value between minimum and maximum.",
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }

    write(task_dir / "task.json", json.dumps(task, indent=2))
    return task_dir / "task.json"


def main() -> None:
    root = PROJECT_ROOT / "tmp" / "toy_model_io_v0"
    output_dir = PROJECT_ROOT / "results" / "local" / "toy_model_io_v0"
    work_root = PROJECT_ROOT / "tmp" / "toy_model_io_runs"

    task_json = build_task(root)
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

    prompt_path = output_dir / "prompt_messages.json"
    raw_response_path = output_dir / "raw_model_response.txt"
    parsed_patch_path = output_dir / "parsed.patch"
    eval_result_path = output_dir / "eval_result.json"

    write_messages_json(prompt_path, messages)

    raw_model_response = '''Here is the patch:

```diff
diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def clamp(value: int, minimum: int, maximum: int) -> int:
-    return value
+    return max(minimum, min(value, maximum))
```
'''

    write(raw_response_path, raw_model_response)

    patch = extract_unified_diff(raw_model_response)
    write_patch(parsed_patch_path, patch)

    result = evaluate_patch_task(
        task,
        patch_file=parsed_patch_path,
        work_root=work_root,
        output_json=eval_result_path,
    )

    print(json.dumps(json.loads(eval_result_path.read_text()), indent=2))

    if not pre_test.passed and result.patch_applied and result.post_tests_passed:
        print("TOY_MODEL_IO_OK")
        return

    raise SystemExit("Toy model I/O validation failed")


if __name__ == "__main__":
    main()

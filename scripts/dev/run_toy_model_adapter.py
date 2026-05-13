from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.candidate_pipeline import run_candidate_generation_pipeline
from forgeagentcoder.agent.prompt_builder import build_patch_generation_messages, write_messages_json
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.command_runner import run_shell_command
from forgeagentcoder.models.bridge import (
    generated_responses_to_raw_model_responses,
    write_generated_responses_jsonl,
)
from forgeagentcoder.models.local_transformers_adapter import LocalTransformersModelAdapter
from forgeagentcoder.models.mock_adapter import DeterministicMockModelAdapter, ScriptedModelOutput
from forgeagentcoder.models.types import GenerationConfig


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
        """def max2(a: int, b: int) -> int:
    return a
""",
    )

    write(
        repo / "tests" / "test_utils.py",
        """import unittest
from app.utils import max2

class TestUtils(unittest.TestCase):
    def test_max2(self):
        self.assertEqual(max2(1, 2), 2)
        self.assertEqual(max2(3, 2), 3)
        self.assertEqual(max2(-1, -5), -1)

if __name__ == "__main__":
    unittest.main()
""",
    )

    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": "toy-model-adapter-max2-bugfix",
        "task_type": "unit_bugfix",
        "title": "Fix max2 implementation",
        "description": "max2 should return the larger of two integers.",
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }

    write(task_dir / "task.json", json.dumps(task, indent=2))
    return task_dir / "task.json"


def main() -> None:
    root = PROJECT_ROOT / "tmp" / "toy_model_adapter_v0"
    output_dir = PROJECT_ROOT / "results" / "local" / "toy_model_adapter_v0"
    patch_output_dir = output_dir / "parsed_patches"
    work_root = PROJECT_ROOT / "tmp" / "toy_model_adapter_runs"

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
    write_messages_json(output_dir / "prompt_messages.json", messages)

    config = GenerationConfig(
        max_new_tokens=256,
        temperature=0.2,
        top_p=0.95,
        do_sample=True,
        num_return_sequences=3,
        seed=17,
    )

    adapter = DeterministicMockModelAdapter(
        [
            ScriptedModelOutput(
                response_id="mock_invalid_max2",
                text="The bug is that max2 always returns the first argument.",
            ),
            ScriptedModelOutput(
                response_id="mock_bad_max2",
                text="""diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def max2(a: int, b: int) -> int:
-    return a
+    return b
""",
            ),
            ScriptedModelOutput(
                response_id="mock_good_max2",
                text="""```diff
diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -1,2 +1,2 @@
 def max2(a: int, b: int) -> int:
-    return a
+    return a if a >= b else b
```""",
            ),
        ],
        model_id="mock-step18-model-adapter",
    )

    generated = adapter.generate(messages, config=config)
    write_generated_responses_jsonl(output_dir / "generated_responses.jsonl", generated)

    raw_responses = generated_responses_to_raw_model_responses(generated)

    pipeline_result = run_candidate_generation_pipeline(
        task=task,
        raw_responses=raw_responses,
        patch_output_dir=patch_output_dir,
        work_root=work_root,
        output_json=output_dir / "candidate_pipeline_result.json",
    )

    skeleton = LocalTransformersModelAdapter(
        model_id="tiny-model-placeholder-for-step19",
        lazy_load=True,
    )

    final_result = {
        "schema_version": "forgeagent.model_adapter_result.v0",
        "task_id": task.task_id,
        "model_metadata": adapter.metadata().to_dict(),
        "generation_config": config.to_dict(),
        "generated_response_count": len(generated),
        "candidate_pipeline_result": asdict(pipeline_result),
        "local_transformers_skeleton_metadata": skeleton.metadata().to_dict(),
    }

    result_path = output_dir / "model_adapter_result.json"
    result_path.write_text(json.dumps(final_result, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final_result, indent=2, default=str))

    if len(generated) != 3:
        raise SystemExit("Expected 3 generated responses")
    if not pipeline_result.solved:
        raise SystemExit("Expected candidate pipeline to solve task")
    if pipeline_result.selected_patch_id != "mock_good_max2_candidate_2":
        raise SystemExit(f"Unexpected selected_patch_id: {pipeline_result.selected_patch_id}")
    if pipeline_result.parse_failure_count != 1:
        raise SystemExit(f"Expected 1 parse failure, got {pipeline_result.parse_failure_count}")

    print("TOY_MODEL_ADAPTER_OK")


if __name__ == "__main__":
    main()

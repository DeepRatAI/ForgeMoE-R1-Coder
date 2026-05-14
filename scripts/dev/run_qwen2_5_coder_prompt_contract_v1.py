from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
import json
import os
import shutil
import sys
import time
import traceback
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.candidate_pipeline import (
    parse_responses_to_patch_candidates,
    run_candidate_generation_pipeline,
)
from forgeagentcoder.agent.mock_model import RawModelResponse
from forgeagentcoder.agent.prompt_builder import write_messages_json
from forgeagentcoder.agent.prompt_contract import (
    build_strict_unified_diff_messages,
    summarize_prompt_contract,
)
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.command_runner import run_shell_command
from forgeagentcoder.models.bridge import write_generated_responses_jsonl
from forgeagentcoder.models.local_transformers_adapter import LocalTransformersModelAdapter
from forgeagentcoder.models.types import GenerationConfig, GeneratedResponse


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def append_jsonl(path: Path, row: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def build_task(
    *,
    root: Path,
    task_id: str,
    title: str,
    description: str,
    function_code: str,
    test_code: str,
) -> Path:
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
    return task_dir / "task.json"


def build_task_suite(root: Path) -> list[Path]:
    if root.exists():
        shutil.rmtree(root)

    return [
        build_task(
            root=root,
            task_id="qwen-contract-add-one",
            title="Fix add_one implementation",
            description="The function add_one should return x + 1.",
            function_code="""def add_one(x: int) -> int:
    return x
""",
            test_code="""import unittest
from app.utils import add_one

class TestUtils(unittest.TestCase):
    def test_add_one(self):
        self.assertEqual(add_one(1), 2)
        self.assertEqual(add_one(-1), 0)

if __name__ == "__main__":
    unittest.main()
""",
        ),
        build_task(
            root=root,
            task_id="qwen-contract-square",
            title="Fix square implementation",
            description="The function square should return x multiplied by itself.",
            function_code="""def square(x: int) -> int:
    return x + x
""",
            test_code="""import unittest
from app.utils import square

class TestUtils(unittest.TestCase):
    def test_square(self):
        self.assertEqual(square(3), 9)
        self.assertEqual(square(-4), 16)

if __name__ == "__main__":
    unittest.main()
""",
        ),
        build_task(
            root=root,
            task_id="qwen-contract-max2",
            title="Fix max2 implementation",
            description="The function max2 should return the larger of two integers.",
            function_code="""def max2(a: int, b: int) -> int:
    return a
""",
            test_code="""import unittest
from app.utils import max2

class TestUtils(unittest.TestCase):
    def test_max2(self):
        self.assertEqual(max2(1, 2), 2)
        self.assertEqual(max2(3, 2), 3)
        self.assertEqual(max2(-1, -5), -1)

if __name__ == "__main__":
    unittest.main()
""",
        ),
    ]


def make_raw_responses(task_id: str, generated: list[GeneratedResponse]) -> list[RawModelResponse]:
    rows: list[RawModelResponse] = []
    for index, item in enumerate(generated):
        rows.append(
            RawModelResponse(
                response_id=f"{task_id}_{item.response_id}_{index}",
                text=item.text,
                source=f"{item.adapter_name}:{item.model_id}",
            )
        )
    return rows


def extract_patch_apply_success_count(task_rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in task_rows:
        pipeline = row.get("candidate_pipeline_result") or {}
        verifier = pipeline.get("verifier_result") or {}
        ranked = verifier.get("ranked_candidates") or []
        if any(bool(item.get("patch_applied")) for item in ranked):
            count += 1
    return count


def main() -> None:
    started = time.time()

    model_id = os.environ.get("FORGEMOE_STEP21_MODEL_ID", "Qwen/Qwen2.5-Coder-0.5B-Instruct")
    experiment_name = "qwen2_5_coder_0_5b_prompt_contract_v1"
    output_dir = PROJECT_ROOT / "results" / "local" / experiment_name
    task_output_root = output_dir / "tasks"
    suite_root = PROJECT_ROOT / "tmp" / experiment_name
    work_root = PROJECT_ROOT / "tmp" / "qwen2_5_coder_prompt_contract_v1_runs"

    if output_dir.exists():
        shutil.rmtree(output_dir)

    task_json_paths = build_task_suite(suite_root)

    config = GenerationConfig(
        max_new_tokens=192,
        temperature=0.0,
        top_p=1.0,
        do_sample=False,
        num_return_sequences=1,
        seed=21,
    )

    adapter = LocalTransformersModelAdapter(
        model_id=model_id,
        device="cpu",
        dtype="auto",
        lazy_load=True,
        trust_remote_code=False,
    )

    task_results: list[dict[str, Any]] = []

    for task_json in task_json_paths:
        task = AgentTask.from_json_file(task_json)
        task_output_dir = task_output_root / task.task_id
        patch_output_dir = task_output_dir / "parsed_patches"

        pre_test = run_shell_command(
            task.test_command,
            cwd=task.repo_dir,
            timeout_seconds=task.timeout_seconds,
        )

        messages = build_strict_unified_diff_messages(
            task,
            pre_test_stderr=pre_test.stderr,
            max_files=4,
            max_file_chars=4000,
        )

        write_messages_json(task_output_dir / "prompt_messages.json", messages)

        generated_raw = adapter.generate(messages, config=config)
        generated = [
            replace(item, response_id=f"{task.task_id}_{item.response_id}_{index}")
            for index, item in enumerate(generated_raw)
        ]

        write_generated_responses_jsonl(task_output_dir / "generated_responses.jsonl", generated)

        for item in generated:
            append_jsonl(output_dir / "all_generated_responses.jsonl", item.to_dict())

        raw_responses = make_raw_responses(task.task_id, generated)

        candidates, parse_failures = parse_responses_to_patch_candidates(
            raw_responses=raw_responses,
            patch_output_dir=patch_output_dir,
        )

        parse_failure_rows = [asdict(item) for item in parse_failures]
        write_json(task_output_dir / "parse_failures.json", parse_failure_rows)

        for row in parse_failure_rows:
            append_jsonl(output_dir / "all_parse_failures.jsonl", {"task_id": task.task_id, **row})

        pipeline_result = None
        pipeline_error = None

        if candidates:
            try:
                pipeline = run_candidate_generation_pipeline(
                    task=task,
                    raw_responses=raw_responses,
                    patch_output_dir=patch_output_dir,
                    work_root=work_root,
                    output_json=task_output_dir / "candidate_pipeline_result.json",
                )
                pipeline_result = asdict(pipeline)
            except Exception as exc:
                pipeline_error = {
                    "type": type(exc).__name__,
                    "repr": repr(exc),
                    "traceback_tail": traceback.format_exc()[-4000:],
                }

        solved = False
        selected_reward = None
        patch_apply_success = False

        if pipeline_result:
            solved = bool(pipeline_result.get("solved", False))
            verifier_result = pipeline_result.get("verifier_result") or {}
            selected_reward = verifier_result.get("selected_reward")
            ranked = verifier_result.get("ranked_candidates") or []
            patch_apply_success = any(bool(item.get("patch_applied")) for item in ranked)

        task_row = {
            "task_id": task.task_id,
            "model_id": model_id,
            "prompt_contract": summarize_prompt_contract(),
            "generated_response_count": len(generated),
            "parsed_candidate_count": len(candidates),
            "parse_failure_count": len(parse_failures),
            "candidate_pipeline_attempted": bool(candidates),
            "candidate_pipeline_error": pipeline_error,
            "candidate_pipeline_result": pipeline_result,
            "patch_apply_success": patch_apply_success,
            "solved": solved,
            "selected_reward": selected_reward,
            "task_output_dir": str(task_output_dir),
        }

        task_results.append(task_row)
        append_jsonl(output_dir / "task_results.jsonl", task_row)
        write_json(task_output_dir / "task_result.json", task_row)

    total_tasks = len(task_results)
    generated_count = sum(row["generated_response_count"] for row in task_results)
    parsed_count = sum(row["parsed_candidate_count"] for row in task_results)
    parse_failure_count = sum(row["parse_failure_count"] for row in task_results)
    attempted_count = sum(1 for row in task_results if row["candidate_pipeline_attempted"])
    patch_apply_success_count = sum(1 for row in task_results if row["patch_apply_success"])
    solved_tasks = sum(1 for row in task_results if row["solved"])

    previous_patch_apply_success_count = 0
    previous_solved_tasks = 0

    summary = {
        "schema_version": "forgeagent.prompt_contract_baseline.v0",
        "experiment_name": experiment_name,
        "model_id": model_id,
        "runtime": "local_transformers",
        "device": "cpu",
        "prompt_contract": summarize_prompt_contract(),
        "model_load_ok": True,
        "real_generation_ok": generated_count > 0,
        "total_tasks": total_tasks,
        "generated_response_count": generated_count,
        "parsed_candidate_count": parsed_count,
        "parse_failure_count": parse_failure_count,
        "candidate_pipeline_attempted_count": attempted_count,
        "patch_apply_success_count": patch_apply_success_count,
        "solved_tasks": solved_tasks,
        "failed_tasks": total_tasks - solved_tasks,
        "solve_rate": round(solved_tasks / total_tasks, 6) if total_tasks else 0.0,
        "comparison_against_step20": {
            "previous_patch_apply_success_count": previous_patch_apply_success_count,
            "previous_solved_tasks": previous_solved_tasks,
            "patch_apply_success_delta": patch_apply_success_count - previous_patch_apply_success_count,
            "solved_tasks_delta": solved_tasks - previous_solved_tasks,
        },
        "generation_config": config.to_dict(),
        "model_metadata": adapter.metadata().to_dict(),
        "elapsed_seconds": round(time.time() - started, 6),
        "artifacts": {
            "summary": str(output_dir / "summary.json"),
            "task_results": str(output_dir / "task_results.jsonl"),
            "all_generated_responses": str(output_dir / "all_generated_responses.jsonl"),
            "all_parse_failures": str(output_dir / "all_parse_failures.jsonl"),
        },
    }

    write_json(output_dir / "summary.json", summary)

    print(json.dumps(summary, indent=2, default=str))
    print("QWEN2_5_CODER_PROMPT_CONTRACT_V1_OK")


if __name__ == "__main__":
    main()

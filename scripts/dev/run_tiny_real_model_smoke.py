from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import os
import shutil
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.candidate_pipeline import (
    parse_responses_to_patch_candidates,
    run_candidate_generation_pipeline,
)
from forgeagentcoder.agent.prompt_builder import build_patch_generation_messages, write_messages_json
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.command_runner import run_shell_command
from forgeagentcoder.models.bridge import (
    generated_responses_to_raw_model_responses,
    write_generated_responses_jsonl,
)
from forgeagentcoder.models.local_transformers_adapter import LocalTransformersModelAdapter
from forgeagentcoder.models.types import GenerationConfig


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def build_task(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)

    repo = root / "repo"
    task_dir = root / "task"

    write(repo / "app" / "__init__.py", "")

    write(
        repo / "app" / "utils.py",
        """def add_one(x: int) -> int:
    return x
""",
    )

    write(
        repo / "tests" / "test_utils.py",
        """import unittest
from app.utils import add_one

class TestUtils(unittest.TestCase):
    def test_add_one(self):
        self.assertEqual(add_one(1), 2)
        self.assertEqual(add_one(-1), 0)

if __name__ == "__main__":
    unittest.main()
""",
    )

    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": "toy-tiny-real-model-add-one-bugfix",
        "task_type": "unit_bugfix",
        "title": "Fix add_one implementation",
        "description": "add_one should return x + 1.",
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }

    write(task_dir / "task.json", json.dumps(task, indent=2))
    return task_dir / "task.json"


def main() -> None:
    started = time.time()

    model_id = os.environ.get("FORGEMOE_STEP19_MODEL_ID", "sshleifer/tiny-gpt2")
    experiment_name = "tiny_real_model_smoke_v0"
    safe_model_name = model_id.replace("/", "_").replace(":", "_")

    root = PROJECT_ROOT / "tmp" / experiment_name
    output_dir = PROJECT_ROOT / "results" / "local" / experiment_name / safe_model_name
    parsed_patch_dir = output_dir / "parsed_patches"
    work_root = PROJECT_ROOT / "tmp" / "tiny_real_model_smoke_runs"

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
        max_files=10,
        max_file_chars=2000,
    )

    write_messages_json(output_dir / "prompt_messages.json", messages)

    config = GenerationConfig(
        max_new_tokens=64,
        temperature=0.0,
        top_p=1.0,
        do_sample=False,
        num_return_sequences=1,
        seed=19,
    )

    adapter = LocalTransformersModelAdapter(
        model_id=model_id,
        device="cpu",
        dtype="auto",
        lazy_load=True,
        trust_remote_code=False,
    )

    generated = adapter.generate(messages, config=config)
    write_generated_responses_jsonl(output_dir / "generated_responses.jsonl", generated)

    raw_responses = generated_responses_to_raw_model_responses(generated)

    candidates, parse_failures = parse_responses_to_patch_candidates(
        raw_responses=raw_responses,
        patch_output_dir=parsed_patch_dir,
    )

    parse_failure_rows = [asdict(item) for item in parse_failures]
    write_json(output_dir / "parse_failures.json", parse_failure_rows)

    candidate_pipeline_result = None
    candidate_pipeline_error = None

    if candidates:
        try:
            pipeline_result = run_candidate_generation_pipeline(
                task=task,
                raw_responses=raw_responses,
                patch_output_dir=parsed_patch_dir,
                work_root=work_root,
                output_json=output_dir / "candidate_pipeline_result.json",
            )
            candidate_pipeline_result = asdict(pipeline_result)
        except Exception as exc:
            candidate_pipeline_error = repr(exc)

    result = {
        "schema_version": "forgeagent.tiny_real_model_smoke.v0",
        "experiment_name": experiment_name,
        "model_id": model_id,
        "runtime": "local_transformers",
        "device": "cpu",
        "model_load_ok": True,
        "real_generation_ok": len(generated) > 0,
        "generated_response_count": len(generated),
        "parsed_candidate_count": len(candidates),
        "parse_failure_count": len(parse_failures),
        "candidate_pipeline_attempted": bool(candidates),
        "candidate_pipeline_error": candidate_pipeline_error,
        "candidate_pipeline_result": candidate_pipeline_result,
        "solve_required": False,
        "solved": candidate_pipeline_result.get("solved") if candidate_pipeline_result else None,
        "generation_config": config.to_dict(),
        "model_metadata": adapter.metadata().to_dict(),
        "elapsed_seconds": round(time.time() - started, 6),
        "artifacts": {
            "prompt_messages": str(output_dir / "prompt_messages.json"),
            "generated_responses": str(output_dir / "generated_responses.jsonl"),
            "parse_failures": str(output_dir / "parse_failures.json"),
            "candidate_pipeline_result": str(output_dir / "candidate_pipeline_result.json")
            if candidate_pipeline_result
            else None,
        },
    }

    write_json(output_dir / "tiny_real_model_smoke_result.json", result)

    print(json.dumps(result, indent=2, default=str))

    if not result["model_load_ok"]:
        raise SystemExit("Expected model_load_ok")
    if not result["real_generation_ok"]:
        raise SystemExit("Expected real_generation_ok")
    if result["generated_response_count"] < 1:
        raise SystemExit("Expected at least one generated response")

    print("TINY_REAL_MODEL_SMOKE_OK")


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.edit_intent import EditIntent, build_canonical_patch
from forgeagentcoder.models.local_transformers_adapter import LocalTransformersModelAdapter
from forgeagentcoder.models.types import GenerationConfig


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def run(cmd: list[str], cwd: Path) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": " ".join(cmd),
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
        "elapsed_seconds": round(time.time() - started, 6),
    }


def skipped_result(reason: str, cwd: Path) -> dict[str, Any]:
    return {
        "command": None,
        "cwd": str(cwd),
        "exit_code": None,
        "stdout": "",
        "stderr": reason,
        "passed": False,
        "elapsed_seconds": 0.0,
    }


def response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "to_dict"):
        return response.to_dict()

    return {
        "response_id": getattr(response, "response_id", None),
        "text": getattr(response, "text", ""),
        "metadata": getattr(response, "metadata", {}),
        "token_counts": getattr(response, "token_counts", None),
        "latency_seconds": getattr(response, "latency_seconds", None),
    }


def response_text(response: Any) -> str:
    return str(getattr(response, "text", ""))


def extract_json_object(text: str) -> str:
    stripped = text.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("no_json_object_found")

    return stripped[start : end + 1]


def build_repo(root: Path, task_id: str, function_code: str, test_code: str) -> Path:
    repo = root / task_id / "repo"

    if repo.exists():
        shutil.rmtree(repo)

    write(repo / "app" / "__init__.py", "")
    write(repo / "app" / "utils.py", function_code)
    write(repo / "tests" / "test_utils.py", test_code)

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.email", "toy@example.com"], cwd=repo)
    run(["git", "config", "user.name", "Toy Runner"], cwd=repo)
    run(["git", "add", "."], cwd=repo)
    run(["git", "commit", "-q", "-m", "init"], cwd=repo)

    return repo


def build_messages(*, task_id: str, function_code: str, test_code: str, expected_behavior: str) -> list[dict[str, str]]:
    schema = {
        "intent_id": "string",
        "task_id": task_id,
        "file_path": "app/utils.py",
        "find_text": "exact current full content of app/utils.py",
        "replace_text": "exact corrected full content of app/utils.py",
        "rationale": "brief reason",
    }

    return [
        {
            "role": "system",
            "content": (
                "You are a strict code editing model. "
                "Return only one valid JSON object. "
                "Do not return Markdown. Do not return a diff. Do not include prose. "
                "Your output must match the requested JSON schema exactly."
            ),
        },
        {
            "role": "user",
            "content": (
                "Create a structured edit intent for this Python bugfix task.\n\n"
                f"task_id: {task_id}\n\n"
                "Required JSON schema:\n"
                f"{json.dumps(schema, indent=2)}\n\n"
                "Constraints:\n"
                "- file_path must be app/utils.py\n"
                "- find_text must be the exact full current content of app/utils.py\n"
                "- replace_text must be the exact full corrected content of app/utils.py\n"
                "- Do not edit tests\n"
                "- Return JSON only\n\n"
                "Current file app/utils.py:\n"
                "```python\n"
                f"{function_code}"
                "```\n\n"
                "Tests:\n"
                "```python\n"
                f"{test_code}"
                "```\n\n"
                "Expected behavior:\n"
                f"{expected_behavior}\n"
            ),
        },
    ]


def main() -> None:
    started = time.time()

    experiment_name = "qwen2_5_coder_0_5b_structured_intent_v0"
    model_id = os.environ.get("FORGEMOE_STEP24_MODEL_ID", "Qwen/Qwen2.5-Coder-0.5B-Instruct")

    output_dir = PROJECT_ROOT / "results" / "local" / experiment_name
    tmp_root = PROJECT_ROOT / "tmp" / experiment_name

    if output_dir.exists():
        shutil.rmtree(output_dir)

    if tmp_root.exists():
        shutil.rmtree(tmp_root)

    output_dir.mkdir(parents=True, exist_ok=True)

    config = GenerationConfig(
        max_new_tokens=384,
        temperature=0.0,
        top_p=1.0,
        do_sample=False,
        num_return_sequences=1,
        seed=24,
    )

    specs = [
        {
            "task_id": "qwen-intent-add-one",
            "function_code": "def add_one(x: int) -> int:\n    return x\n",
            "test_code": "import unittest\nfrom app.utils import add_one\n\nclass TestUtils(unittest.TestCase):\n    def test_add_one(self):\n        self.assertEqual(add_one(1), 2)\n        self.assertEqual(add_one(-1), 0)\n\nif __name__ == '__main__':\n    unittest.main()\n",
            "expected_behavior": "add_one(x) must return x + 1.",
        },
        {
            "task_id": "qwen-intent-square",
            "function_code": "def square(x: int) -> int:\n    return x + x\n",
            "test_code": "import unittest\nfrom app.utils import square\n\nclass TestUtils(unittest.TestCase):\n    def test_square(self):\n        self.assertEqual(square(3), 9)\n        self.assertEqual(square(-4), 16)\n\nif __name__ == '__main__':\n    unittest.main()\n",
            "expected_behavior": "square(x) must return x multiplied by itself.",
        },
        {
            "task_id": "qwen-intent-max2",
            "function_code": "def max2(a: int, b: int) -> int:\n    return a\n",
            "test_code": "import unittest\nfrom app.utils import max2\n\nclass TestUtils(unittest.TestCase):\n    def test_max2(self):\n        self.assertEqual(max2(1, 2), 2)\n        self.assertEqual(max2(3, 2), 3)\n        self.assertEqual(max2(-1, -5), -1)\n\nif __name__ == '__main__':\n    unittest.main()\n",
            "expected_behavior": "max2(a, b) must return the larger integer.",
        },
    ]

    summary: dict[str, Any] = {
        "schema_version": "forgeagent.qwen_structured_intent_baseline.v0",
        "experiment_name": experiment_name,
        "model_id": model_id,
        "runtime": "local_transformers",
        "device": "cpu",
        "model_load_ok": False,
        "real_generation_ok": False,
        "total_tasks": len(specs),
        "generated_response_count": 0,
        "json_parse_success_count": 0,
        "valid_intent_count": 0,
        "canonical_patch_count": 0,
        "patch_apply_success_count": 0,
        "solved_tasks": 0,
        "failed_tasks": 0,
        "solve_rate": 0.0,
        "generation_config": config.to_dict() if hasattr(config, "to_dict") else config.__dict__,
        "model_metadata": None,
        "elapsed_seconds": None,
        "artifacts": {
            "summary": str(output_dir / "summary.json"),
            "task_results": str(output_dir / "task_results.jsonl"),
            "all_generated_responses": str(output_dir / "all_generated_responses.jsonl"),
        },
    }

    rows: list[dict[str, Any]] = []
    generated_rows: list[dict[str, Any]] = []

    try:
        adapter = LocalTransformersModelAdapter(
            model_id=model_id,
            device="cpu",
            dtype="auto",
            lazy_load=True,
            trust_remote_code=False,
        )

        for spec in specs:
            task_id = spec["task_id"]
            task_out = output_dir / "tasks" / task_id
            task_out.mkdir(parents=True, exist_ok=True)

            repo = build_repo(
                tmp_root,
                task_id,
                spec["function_code"],
                spec["test_code"],
            )

            pre_test = run(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=repo)

            messages = build_messages(
                task_id=task_id,
                function_code=spec["function_code"],
                test_code=spec["test_code"],
                expected_behavior=spec["expected_behavior"],
            )

            write_json(task_out / "prompt_messages.json", messages)

            responses = adapter.generate(messages, config=config)
            response_dicts = [response_to_dict(response) for response in responses]

            with (task_out / "generated_responses.jsonl").open("w", encoding="utf-8") as f:
                for response_dict in response_dicts:
                    response_dict = {"task_id": task_id, **response_dict}
                    generated_rows.append(response_dict)
                    f.write(json.dumps(response_dict, ensure_ascii=False, default=str) + "\n")

            intent = None
            intent_json = None
            intent_parse_error = None
            patch_result = None
            patch_path = None

            if responses:
                raw_text = response_text(responses[0])
                try:
                    intent_json = json.loads(extract_json_object(raw_text))
                    intent = EditIntent.from_dict(intent_json)
                except BaseException as exc:
                    intent_parse_error = {
                        "error_type": type(exc).__name__,
                        "error": repr(exc),
                        "traceback_tail": traceback.format_exc()[-2000:],
                        "raw_text_preview": raw_text[:2000],
                    }

            if intent is not None:
                patch_result = build_canonical_patch(repo, intent)
                patch_path = task_out / "canonical.patch"
                write(patch_path, patch_result.patch_text)
                write_json(task_out / "intent.json", intent.to_dict())
                write_json(task_out / "patch_result.json", patch_result.to_dict())

            if patch_result is not None and patch_result.patch_text:
                apply_result = run(["git", "apply", str(patch_path)], cwd=repo)
            else:
                apply_result = skipped_result("no_canonical_patch", repo)

            if apply_result["passed"]:
                post_test = run(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=repo)
            else:
                post_test = skipped_result("patch_apply_failed_or_missing", repo)

            validation = patch_result.validation.to_dict() if patch_result is not None else None

            row = {
                "task_id": task_id,
                "generated_response_count": len(responses),
                "json_parse_success": intent is not None,
                "intent_parse_error": intent_parse_error,
                "intent": intent.to_dict() if intent is not None else None,
                "intent_json": intent_json,
                "validation": validation,
                "canonical_patch_created": bool(patch_result and patch_result.patch_text),
                "patch_path": str(patch_path) if patch_path is not None else None,
                "patch_apply_passed": apply_result["passed"],
                "post_test_passed": post_test["passed"],
                "solved": post_test["passed"],
                "pre_test": pre_test,
                "patch_apply": apply_result,
                "post_test": post_test,
            }

            rows.append(row)
            write_json(task_out / "task_result.json", row)

        metadata = adapter.metadata().to_dict() if hasattr(adapter.metadata(), "to_dict") else adapter.metadata().__dict__

        summary["model_load_ok"] = True
        summary["model_metadata"] = metadata

    except BaseException as exc:
        summary["top_level_error"] = {
            "error_type": type(exc).__name__,
            "error": repr(exc),
            "traceback_tail": traceback.format_exc()[-4000:],
        }

    summary["generated_response_count"] = sum(row["generated_response_count"] for row in rows)
    summary["real_generation_ok"] = summary["generated_response_count"] > 0
    summary["json_parse_success_count"] = sum(1 for row in rows if row["json_parse_success"])
    summary["valid_intent_count"] = sum(1 for row in rows if row["validation"] and row["validation"]["valid"])
    summary["canonical_patch_count"] = sum(1 for row in rows if row["canonical_patch_created"])
    summary["patch_apply_success_count"] = sum(1 for row in rows if row["patch_apply_passed"])
    summary["solved_tasks"] = sum(1 for row in rows if row["solved"])
    summary["failed_tasks"] = summary["total_tasks"] - summary["solved_tasks"]
    summary["solve_rate"] = round(summary["solved_tasks"] / summary["total_tasks"], 6) if summary["total_tasks"] else 0.0
    summary["elapsed_seconds"] = round(time.time() - started, 6)

    write_json(output_dir / "summary.json", summary)

    with (output_dir / "task_results.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    with (output_dir / "all_generated_responses.jsonl").open("w", encoding="utf-8") as f:
        for row in generated_rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    print(json.dumps(summary, indent=2, default=str))
    print("QWEN_STRUCTURED_INTENT_BASELINE_OK")

    if not summary["model_load_ok"]:
        raise SystemExit("model_load_failed")

    if not summary["real_generation_ok"]:
        raise SystemExit("real_generation_failed")


if __name__ == "__main__":
    main()

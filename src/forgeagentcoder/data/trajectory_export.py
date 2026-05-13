from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def read_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def read_patch_text(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def build_patch_attempt_examples(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    task_id = str(trajectory["task_id"])
    rows: list[dict[str, Any]] = []

    previous_failure_stderr = ""

    for item in trajectory.get("trajectory", []):
        eval_result = item.get("eval_result", {})
        pre_test = eval_result.get("pre_test", {})
        post_test = eval_result.get("post_test", {})

        patch_text = read_patch_text(item.get("patch_path"))
        post_tests_passed = bool(item.get("post_tests_passed"))
        label = "positive" if post_tests_passed else "negative"

        row = {
            "schema_version": "forgeagent.patch_attempt.v0",
            "example_id": f"{task_id}::iter_{item['iteration']}::{item['patch_id']}",
            "task_id": task_id,
            "iteration": int(item["iteration"]),
            "patch_id": str(item["patch_id"]),
            "patch_applied": bool(item.get("patch_applied")),
            "post_tests_passed": post_tests_passed,
            "reward": float(item.get("reward", 0.0)),
            "label": label,
            "input": {
                "instruction": "Generate a unified diff patch that fixes the repository task and makes tests pass.",
                "pre_test_command": pre_test.get("command", ""),
                "pre_test_stderr": pre_test.get("stderr", ""),
                "previous_failure_stderr": previous_failure_stderr,
            },
            "output": {
                "patch": patch_text,
            },
            "metadata": {
                "source": "self_repair_trajectory",
                "work_dir": eval_result.get("work_dir", ""),
                "patch_path": item.get("patch_path", ""),
            },
        }

        rows.append(row)

        if not post_tests_passed:
            previous_failure_stderr = post_test.get("stderr", "")

    return rows


def build_sft_positive_examples(patch_attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for item in patch_attempts:
        if item["label"] != "positive":
            continue

        user_content = (
            "You are a fullstack software engineering agent.\n"
            "Fix the repository by producing a unified diff patch.\n\n"
            f"Task ID: {item['task_id']}\n\n"
            "Pre-test failure:\n"
            f"{item['input'].get('pre_test_stderr', '')}\n\n"
            "Previous failed attempt feedback:\n"
            f"{item['input'].get('previous_failure_stderr', '')}\n\n"
            "Return only the patch."
        )

        row = {
            "schema_version": "forgeagent.sft_positive.v0",
            "example_id": item["example_id"],
            "task_id": item["task_id"],
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert software engineering agent that edits repositories using unified diff patches.",
                },
                {
                    "role": "user",
                    "content": user_content,
                },
                {
                    "role": "assistant",
                    "content": item["output"]["patch"],
                },
            ],
            "reward": item["reward"],
            "metadata": {
                "source": "self_repair_positive_attempt",
                "patch_id": item["patch_id"],
            },
        }

        rows.append(row)

    return rows


def export_trajectory_dataset(
    *,
    trajectory_json: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    trajectory = read_json(trajectory_json)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    patch_attempts = build_patch_attempt_examples(trajectory)
    sft_positive = build_sft_positive_examples(patch_attempts)

    patch_attempts_path = output_dir / "patch_attempts.jsonl"
    sft_positive_path = output_dir / "sft_positive.jsonl"
    summary_path = output_dir / "summary.json"

    write_jsonl(patch_attempts_path, patch_attempts)
    write_jsonl(sft_positive_path, sft_positive)

    summary = {
        "schema_version": "forgeagent.trajectory_dataset_summary.v0",
        "task_id": trajectory["task_id"],
        "total_attempts": len(patch_attempts),
        "positive_attempts": len(sft_positive),
        "negative_attempts": len(patch_attempts) - len(sft_positive),
        "solved": bool(trajectory.get("solved")),
        "best_patch_id": trajectory.get("best_patch_id"),
        "best_reward": trajectory.get("best_reward"),
        "patch_attempts_jsonl": str(patch_attempts_path),
        "sft_positive_jsonl": str(sft_positive_path),
    }

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

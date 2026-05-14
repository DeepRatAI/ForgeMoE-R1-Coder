from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.edit_intent import EditIntent, build_canonical_patch
from forgeagentcoder.agent.intent_repair import repair_intent_from_context


SOURCE_DIR = PROJECT_ROOT / "results/local/qwen2_5_coder_0_5b_structured_intent_v0"
OUT_DIR = PROJECT_ROOT / "results/local/intent_repair_normalization_v0"
TMP_ROOT = PROJECT_ROOT / "tmp/intent_repair_normalization_v0"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


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


def skipped(reason: str, cwd: Path) -> dict[str, Any]:
    return {
        "command": None,
        "cwd": str(cwd),
        "exit_code": None,
        "stdout": "",
        "stderr": reason,
        "passed": False,
        "elapsed_seconds": 0.0,
    }


def extract_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end == -1:
        return ""
    return text[start:end]


def extract_after(text: str, marker: str) -> str:
    start = text.find(marker)
    if start == -1:
        return ""
    return text[start + len(marker):].strip()


def extract_context(prompt_messages: list[dict[str, Any]]) -> dict[str, str]:
    combined = "\n\n".join(str(item.get("content", "")) for item in prompt_messages)

    current_file = extract_block(
        combined,
        "Current file app/utils.py:\n```python\n",
        "```\n\nTests:",
    )

    tests = extract_block(
        combined,
        "Tests:\n```python\n",
        "```\n\nExpected behavior:",
    )

    expected_behavior = extract_after(combined, "Expected behavior:\n")

    return {
        "current_file": current_file,
        "tests": tests,
        "expected_behavior": expected_behavior,
    }


def build_repo(root: Path, task_id: str, current_file: str, tests: str) -> Path:
    repo = root / task_id / "repo"

    if repo.exists():
        shutil.rmtree(repo)

    write(repo / "app" / "__init__.py", "")
    write(repo / "app" / "utils.py", current_file)
    write(repo / "tests" / "test_utils.py", tests)

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.email", "toy@example.com"], cwd=repo)
    run(["git", "config", "user.name", "Toy Runner"], cwd=repo)
    run(["git", "add", "."], cwd=repo)
    run(["git", "commit", "-q", "-m", "init"], cwd=repo)

    return repo


def main() -> None:
    started = time.time()

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    source_summary = read_json(SOURCE_DIR / "summary.json")
    source_rows = read_jsonl(SOURCE_DIR / "task_results.jsonl")

    task_results = []

    for source_row in source_rows:
        task_id = source_row["task_id"]
        source_task_dir = SOURCE_DIR / "tasks" / task_id
        out_task_dir = OUT_DIR / "tasks" / task_id

        prompt_messages = read_json(source_task_dir / "prompt_messages.json")
        context = extract_context(prompt_messages)

        repo = build_repo(
            TMP_ROOT,
            task_id,
            context["current_file"],
            context["tests"],
        )

        pre_test = run(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=repo)

        original_intent = source_row.get("intent")
        repair_report = repair_intent_from_context(
            repo_dir=str(repo),
            task_id=task_id,
            original_intent=original_intent,
            current_file_text=context["current_file"],
            expected_behavior=context["expected_behavior"],
        )

        repaired_intent = (
            EditIntent.from_dict(repair_report.repaired_intent)
            if repair_report.repaired_intent is not None
            else None
        )

        if repaired_intent is not None:
            patch_result = build_canonical_patch(repo, repaired_intent)
            patch_path = out_task_dir / "canonical_repaired.patch"
            write(patch_path, patch_result.patch_text)
            write_json(out_task_dir / "patch_result.json", patch_result.to_dict())
        else:
            patch_result = None
            patch_path = None

        if patch_result is not None and patch_result.patch_text:
            apply_result = run(["git", "apply", str(patch_path)], cwd=repo)
        else:
            apply_result = skipped("no_repaired_canonical_patch", repo)

        if apply_result["passed"]:
            post_test = run(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=repo)
        else:
            post_test = skipped("patch_apply_failed_or_missing", repo)

        row = {
            "task_id": task_id,
            "source_json_parse_success": source_row.get("json_parse_success"),
            "source_validation": source_row.get("validation"),
            "repair_report": repair_report.to_dict(),
            "repaired_valid": bool(
                repair_report.repaired_validation
                and repair_report.repaired_validation.get("valid")
            ),
            "canonical_patch_created": bool(patch_result and patch_result.patch_text),
            "patch_apply_passed": apply_result["passed"],
            "post_test_passed": post_test["passed"],
            "solved": post_test["passed"],
            "pre_test": pre_test,
            "patch_apply": apply_result,
            "post_test": post_test,
            "prompt_context": context,
        }

        task_results.append(row)
        write_json(out_task_dir / "task_result.json", row)
        write_json(out_task_dir / "repair_report.json", repair_report.to_dict())

    total = len(task_results)
    original_valid = sum(
        1 for row in task_results
        if row["source_validation"] and row["source_validation"].get("valid")
    )
    repaired_valid = sum(1 for row in task_results if row["repaired_valid"])
    patch_apply_success = sum(1 for row in task_results if row["patch_apply_passed"])
    solved = sum(1 for row in task_results if row["solved"])

    summary = {
        "schema_version": "forgeagent.intent_repair_normalization_replay.v0",
        "experiment_name": "intent_repair_normalization_v0",
        "source_experiment": source_summary["experiment_name"],
        "source_model_id": source_summary["model_id"],
        "total_tasks": total,
        "source_json_parse_success_count": sum(1 for row in task_results if row["source_json_parse_success"]),
        "original_valid_intent_count": original_valid,
        "repaired_valid_intent_count": repaired_valid,
        "canonical_patch_count": sum(1 for row in task_results if row["canonical_patch_created"]),
        "patch_apply_success_count": patch_apply_success,
        "solved_tasks": solved,
        "solve_rate": round(solved / total, 6) if total else 0.0,
        "elapsed_seconds": round(time.time() - started, 6),
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "task_results": str(OUT_DIR / "task_results.jsonl"),
        },
    }

    write_json(OUT_DIR / "summary.json", summary)

    with (OUT_DIR / "task_results.jsonl").open("w", encoding="utf-8") as f:
        for row in task_results:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    print(json.dumps(summary, indent=2, default=str))
    print("INTENT_REPAIR_NORMALIZATION_REPLAY_OK")


if __name__ == "__main__":
    main()

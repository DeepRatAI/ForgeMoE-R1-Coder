from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.edit_intent import EditIntent, build_canonical_patch


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def run(cmd: list[str], cwd: Path) -> dict:
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


def main() -> None:
    started = time.time()

    experiment_name = "structured_edit_intent_toy_v0"
    output_dir = PROJECT_ROOT / "results" / "local" / experiment_name
    tmp_root = PROJECT_ROOT / "tmp" / experiment_name

    if output_dir.exists():
        shutil.rmtree(output_dir)
    if tmp_root.exists():
        shutil.rmtree(tmp_root)

    specs = [
        {
            "task_id": "intent-add-one",
            "function_code": "def add_one(x: int) -> int:\n    return x\n",
            "test_code": "import unittest\nfrom app.utils import add_one\n\nclass TestUtils(unittest.TestCase):\n    def test_add_one(self):\n        self.assertEqual(add_one(1), 2)\n        self.assertEqual(add_one(-1), 0)\n\nif __name__ == '__main__':\n    unittest.main()\n",
            "intent": {
                "intent_id": "intent-add-one-fix",
                "task_id": "intent-add-one",
                "file_path": "app/utils.py",
                "find_text": "def add_one(x: int) -> int:\n    return x\n",
                "replace_text": "def add_one(x: int) -> int:\n    return x + 1\n",
                "rationale": "add_one must increment by one",
            },
        },
        {
            "task_id": "intent-square",
            "function_code": "def square(x: int) -> int:\n    return x + x\n",
            "test_code": "import unittest\nfrom app.utils import square\n\nclass TestUtils(unittest.TestCase):\n    def test_square(self):\n        self.assertEqual(square(3), 9)\n        self.assertEqual(square(-4), 16)\n\nif __name__ == '__main__':\n    unittest.main()\n",
            "intent": {
                "intent_id": "intent-square-fix",
                "task_id": "intent-square",
                "file_path": "app/utils.py",
                "find_text": "def square(x: int) -> int:\n    return x + x\n",
                "replace_text": "def square(x: int) -> int:\n    return x * x\n",
                "rationale": "square requires multiplication",
            },
        },
        {
            "task_id": "intent-max2",
            "function_code": "def max2(a: int, b: int) -> int:\n    return a\n",
            "test_code": "import unittest\nfrom app.utils import max2\n\nclass TestUtils(unittest.TestCase):\n    def test_max2(self):\n        self.assertEqual(max2(1, 2), 2)\n        self.assertEqual(max2(3, 2), 3)\n        self.assertEqual(max2(-1, -5), -1)\n\nif __name__ == '__main__':\n    unittest.main()\n",
            "intent": {
                "intent_id": "intent-max2-fix",
                "task_id": "intent-max2",
                "file_path": "app/utils.py",
                "find_text": "def max2(a: int, b: int) -> int:\n    return a\n",
                "replace_text": "def max2(a: int, b: int) -> int:\n    return a if a >= b else b\n",
                "rationale": "max2 must return the larger argument",
            },
        },
    ]

    rows = []

    for spec in specs:
        task_id = spec["task_id"]
        task_out = output_dir / "tasks" / task_id
        repo = build_repo(
            tmp_root,
            task_id,
            spec["function_code"],
            spec["test_code"],
        )

        pre_test = run(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=repo)

        intent = EditIntent.from_dict(spec["intent"])
        patch_result = build_canonical_patch(repo, intent)

        patch_path = task_out / "canonical.patch"
        write(patch_path, patch_result.patch_text)

        apply_result = run(["git", "apply", str(patch_path)], cwd=repo)

        post_test = run(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=repo)

        row = {
            "task_id": task_id,
            "intent": intent.to_dict(),
            "validation": patch_result.validation.to_dict(),
            "patch_path": str(patch_path),
            "patch_text": patch_result.patch_text,
            "pre_test_passed": pre_test["passed"],
            "patch_apply_passed": apply_result["passed"],
            "post_test_passed": post_test["passed"],
            "pre_test": pre_test,
            "patch_apply": apply_result,
            "post_test": post_test,
        }

        rows.append(row)
        write_json(task_out / "task_result.json", row)

    total = len(rows)
    valid_intents = sum(1 for row in rows if row["validation"]["valid"])
    patch_apply_success = sum(1 for row in rows if row["patch_apply_passed"])
    solved = sum(1 for row in rows if row["post_test_passed"])

    summary = {
        "schema_version": "forgeagent.structured_edit_intent_toy.v0",
        "experiment_name": experiment_name,
        "total_tasks": total,
        "valid_intents": valid_intents,
        "canonical_patch_count": total,
        "patch_apply_success_count": patch_apply_success,
        "solved_tasks": solved,
        "solve_rate": round(solved / total, 6) if total else 0.0,
        "elapsed_seconds": round(time.time() - started, 6),
        "artifacts": {
            "summary": str(output_dir / "summary.json"),
            "task_results": str(output_dir / "task_results.jsonl"),
        },
    }

    write_json(output_dir / "summary.json", summary)

    with (output_dir / "task_results.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    print(json.dumps(summary, indent=2, default=str))
    print("STRUCTURED_EDIT_INTENT_TOY_OK")


if __name__ == "__main__":
    main()

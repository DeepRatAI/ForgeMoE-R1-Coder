from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import difflib
import hashlib
import json
import shutil
import subprocess
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "results/local/internal_synthetic_micro_generator_v0"
RUN_DIR = PROJECT_ROOT / "tmp/internal_synthetic_micro_generator_runs"


@dataclass(frozen=True)
class MicroTaskDefinition:
    task_id: str
    split: str
    function_name: str
    before_body: str
    after_body: str
    rejected_body: str
    public_test_body: str
    hidden_test_body: str
    instruction: str
    difficulty: str


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def run_command(command: list[str], cwd: Path, timeout_seconds: int = 30) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_seconds": round(time.time() - started, 6),
            "timed_out": False,
            "passed": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "elapsed_seconds": round(time.time() - started, 6),
            "timed_out": True,
            "passed": False,
        }


def normalize_py(text: str) -> str:
    return text.strip() + "\n"


def make_patch(relative_path: str, before_text: str, after_text: str) -> str:
    before_lines = normalize_py(before_text).splitlines(keepends=False)
    after_lines = normalize_py(after_text).splitlines(keepends=False)

    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
        )
    )

    has_real_change = any(
        (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
        for line in diff_lines
    )

    if not diff_lines or not has_real_change:
        raise RuntimeError(f"empty or non-actionable patch generated for {relative_path}")

    payload = "\n".join(diff_lines)
    if not payload.endswith("\n"):
        payload += "\n"

    return f"diff --git a/{relative_path} b/{relative_path}\n" + payload


def create_repo(repo_dir: Path, task: MicroTaskDefinition, body: str) -> None:
    if repo_dir.exists():
        shutil.rmtree(repo_dir)

    write_text(repo_dir / "app/__init__.py", f"from .utils import {task.function_name}\n")
    write_text(repo_dir / "app/utils.py", normalize_py(body))
    write_text(repo_dir / "tests/test_public.py", task.public_test_body.strip() + "\n")


def init_git_repo(work_dir: Path) -> dict[str, Any]:
    init = run_command(["git", "init", "-q"], cwd=work_dir)
    if not init["passed"]:
        return init

    run_command(["git", "config", "user.email", "forge@example.invalid"], cwd=work_dir)
    run_command(["git", "config", "user.name", "Forge Synthetic Generator"], cwd=work_dir)
    run_command(["git", "add", "."], cwd=work_dir)
    commit = run_command(["git", "commit", "-q", "-m", "baseline"], cwd=work_dir)
    return commit


def verify_patch(task_dir: Path, task: MicroTaskDefinition, patch_path: Path, hidden_test_path: Path, label: str) -> dict[str, Any]:
    work_dir = RUN_DIR / f"{task.task_id}-{label}"

    if work_dir.exists():
        shutil.rmtree(work_dir)

    shutil.copytree(task_dir / "repo_before", work_dir)

    git_init = init_git_repo(work_dir)
    pre_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)

    local_patch = work_dir / "_candidate.patch"
    shutil.copy2(patch_path, local_patch)

    patch_check = run_command(["git", "apply", "--check", str(local_patch.name)], cwd=work_dir)
    patch_apply = run_command(["git", "apply", str(local_patch.name)], cwd=work_dir) if patch_check["passed"] else {
        "command": ["git", "apply", str(local_patch.name)],
        "cwd": str(work_dir),
        "exit_code": 1,
        "stdout": "",
        "stderr": "git apply --check failed; apply skipped.\n" + (patch_check.get("stderr") or ""),
        "elapsed_seconds": 0.0,
        "timed_out": False,
        "passed": False,
    }

    if patch_apply["passed"]:
        post_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
        shutil.copy2(hidden_test_path, work_dir / "tests/test_hidden.py")
        post_hidden = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
    else:
        post_public = {
            "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; public post-test skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }
        post_hidden = {
            "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; hidden post-test skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }

    return {
        "label": label,
        "work_dir": str(work_dir),
        "git_init": git_init,
        "pre_public": pre_public,
        "patch_check": patch_check,
        "patch_apply": patch_apply,
        "post_public": post_public,
        "post_hidden": post_hidden,
        "pre_public_failed_as_expected": not pre_public["passed"],
        "patch_check_passed": patch_check["passed"],
        "patch_applied": patch_apply["passed"],
        "post_public_passed": post_public["passed"],
        "post_hidden_passed": post_hidden["passed"],
        "verified": (not pre_public["passed"]) and patch_apply["passed"] and post_public["passed"] and post_hidden["passed"],
    }


def build_tasks() -> list[MicroTaskDefinition]:
    return [
        MicroTaskDefinition(
            task_id="forge-micro-train-add-one",
            split="train",
            function_name="add_one",
            before_body="def add_one(x: int) -> int:\n    return x\n",
            after_body="def add_one(x: int) -> int:\n    return x + 1\n",
            rejected_body="def add_one(x: int) -> int:\n    return x + 2\n",
            public_test_body="""
import unittest
from app.utils import add_one

class TestAddOnePublic(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(add_one(1), 2)
""",
            hidden_test_body="""
import unittest
from app.utils import add_one

class TestAddOneHidden(unittest.TestCase):
    def test_zero_and_negative(self):
        self.assertEqual(add_one(0), 1)
        self.assertEqual(add_one(-1), 0)
""",
            instruction="Fix add_one so it returns x + 1 for all integer inputs.",
            difficulty="micro",
        ),
        MicroTaskDefinition(
            task_id="forge-micro-eval-square",
            split="eval",
            function_name="square",
            before_body="def square(x: int) -> int:\n    return x + x\n",
            after_body="def square(x: int) -> int:\n    return x * x\n",
            rejected_body="def square(x: int) -> int:\n    return x ** 3\n",
            public_test_body="""
import unittest
from app.utils import square

class TestSquarePublic(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(square(3), 9)
""",
            hidden_test_body="""
import unittest
from app.utils import square

class TestSquareHidden(unittest.TestCase):
    def test_zero_and_negative(self):
        self.assertEqual(square(0), 0)
        self.assertEqual(square(-4), 16)
""",
            instruction="Fix square so it returns x multiplied by itself.",
            difficulty="micro",
        ),
        MicroTaskDefinition(
            task_id="forge-micro-private-heldout-max2",
            split="private_heldout",
            function_name="max2",
            before_body="def max2(a: int, b: int) -> int:\n    return a\n",
            after_body="def max2(a: int, b: int) -> int:\n    return a if a >= b else b\n",
            rejected_body="def max2(a: int, b: int) -> int:\n    return b\n",
            public_test_body="""
import unittest
from app.utils import max2

class TestMax2Public(unittest.TestCase):
    def test_b_larger(self):
        self.assertEqual(max2(1, 2), 2)
""",
            hidden_test_body="""
import unittest
from app.utils import max2

class TestMax2Hidden(unittest.TestCase):
    def test_a_larger_and_equal(self):
        self.assertEqual(max2(5, 2), 5)
        self.assertEqual(max2(3, 3), 3)
""",
            instruction="Fix max2 so it returns the larger of a and b.",
            difficulty="micro",
        ),
    ]


def task_spec(task: MicroTaskDefinition, task_dir: Path, golden_patch_text: str) -> dict[str, Any]:
    sha = hashlib.sha256(golden_patch_text.encode("utf-8")).hexdigest()
    return {
        "schema_version": "forgeagent.synthetic_executable_task.v0",
        "task_id": task.task_id,
        "source_repo": {
            "type": "internal_generated_micro_repo",
            "license": "internal_scaffold_only",
            "provenance": "generated_by_step29_9_micro_generator",
        },
        "repo_snapshot": {
            "path": str(task_dir / "repo_before"),
            "immutable_snapshot": True,
        },
        "task_family": "single_file_bugfix",
        "instruction": task.instruction,
        "pre_failure_command": "python3 -B -m unittest discover -s tests",
        "post_success_command": "python3 -B -m unittest discover -s tests",
        "hidden_tests": {
            "path": str(task_dir / "hidden_tests/test_hidden.py"),
            "required_for_training_grade": True,
        },
        "expected_edit_scope": {
            "files": ["app/utils.py"],
            "max_files": 1,
        },
        "difficulty": {
            "label": task.difficulty,
            "single_file": True,
            "requires_hidden_generalization": True,
        },
        "split": task.split,
        "never_train_on": task.split == "private_heldout",
        "golden_patch_ref": {
            "path": str(task_dir / "golden.patch"),
            "sha256": sha,
            "export_to_training": task.split == "train",
        },
        "provenance": {
            "generator": "run_internal_synthetic_micro_generator.py",
            "generator_version": "v0",
            "deterministic": True,
        },
        "quality_scores": {
            "execution_oracle": 1.0,
            "hidden_test_strength": 0.7,
            "edit_locality": 1.0,
            "agentic_value": 0.25,
            "training_grade_candidate": task.split == "train",
        },
        "contamination_report": {
            "public_benchmark_overlap_checked": False,
            "reason": "micro internal generated scaffold; full contamination scanner not implemented yet",
            "allowed_for_scaffold": True,
        },
    }


def build_patch_sft_row(task: MicroTaskDefinition, spec: dict[str, Any], golden_patch_text: str) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.patch_sft_row.v0",
        "task_id": task.task_id,
        "split": task.split,
        "instruction": task.instruction,
        "repo_context": {
            "files": [
                {"path": "app/utils.py", "content": normalize_py(task.before_body)},
                {"path": "tests/test_public.py", "content": task.public_test_body.strip() + "\n"},
            ],
        },
        "target_patch": golden_patch_text,
        "metadata": {
            "source": "internal_micro_generator",
            "task_family": "single_file_bugfix",
            "hidden_tests_available": True,
            "never_train_on": spec["never_train_on"],
        },
    }


def build_trajectory_seed(task: MicroTaskDefinition, verification: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.agentic_trajectory_seed.v0",
        "trajectory_id": task.task_id + "-trajectory-seed",
        "task_id": task.task_id,
        "split": task.split,
        "events": [
            {"type": "read_file", "path": "app/utils.py"},
            {"type": "run_tests", "result": "pre_public_failed"},
            {"type": "plan", "content": task.instruction},
            {"type": "generate_patch", "result": "golden_patch"},
            {"type": "apply_patch", "result": "applied"},
            {"type": "run_tests", "result": "post_public_and_hidden_passed"},
        ],
        "reward": "solved" if verification["verified"] else "failed",
        "never_train_on": task.split == "private_heldout",
    }


def build_preference_pair(task: MicroTaskDefinition, golden_patch_text: str, rejected_patch_text: str) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.preference_pair_seed.v0",
        "pair_id": task.task_id + "-chosen-vs-rejected",
        "task_id": task.task_id,
        "split": task.split,
        "prompt": task.instruction,
        "chosen_patch": golden_patch_text,
        "rejected_patch": rejected_patch_text,
        "chosen_reason": "golden_patch_applies_and_passes_public_and_hidden_tests",
        "rejected_reason": "rejected_patch_applies_but_fails_behavioral_tests_or_is_lower_reward",
        "never_train_on": task.split == "private_heldout",
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    export_dir = OUT_DIR / "dataset_exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    for path in [
        export_dir / "patch_sft_train.jsonl",
        export_dir / "trajectory_sft_train_seed.jsonl",
        export_dir / "preference_pairs_train_seed.jsonl",
        export_dir / "eval_tasks.jsonl",
        export_dir / "private_heldout_tasks.jsonl",
    ]:
        if path.exists():
            path.unlink()

    tasks = build_tasks()
    task_results: list[dict[str, Any]] = []

    for task in tasks:
        task_dir = OUT_DIR / "tasks" / task.task_id
        create_repo(task_dir / "repo_before", task, task.before_body)
        write_text(task_dir / "hidden_tests/test_hidden.py", task.hidden_test_body.strip() + "\n")

        before_text = normalize_py(task.before_body)
        after_text = normalize_py(task.after_body)
        rejected_text = normalize_py(task.rejected_body)

        golden_patch = make_patch("app/utils.py", before_text, after_text)
        rejected_patch = make_patch("app/utils.py", before_text, rejected_text)

        write_text(task_dir / "golden.patch", golden_patch)
        write_text(task_dir / "rejected.patch", rejected_patch)

        golden_verification = verify_patch(
            task_dir=task_dir,
            task=task,
            patch_path=task_dir / "golden.patch",
            hidden_test_path=task_dir / "hidden_tests/test_hidden.py",
            label="golden",
        )

        rejected_verification = verify_patch(
            task_dir=task_dir,
            task=task,
            patch_path=task_dir / "rejected.patch",
            hidden_test_path=task_dir / "hidden_tests/test_hidden.py",
            label="rejected",
        )

        spec = task_spec(task=task, task_dir=task_dir, golden_patch_text=golden_patch)

        write_json(task_dir / "task_spec.json", spec)
        write_json(task_dir / "verification_result.json", golden_verification)
        write_json(task_dir / "rejected_patch_verification_result.json", rejected_verification)

        if task.split == "train":
            append_jsonl(export_dir / "patch_sft_train.jsonl", build_patch_sft_row(task, spec, golden_patch))
            append_jsonl(export_dir / "trajectory_sft_train_seed.jsonl", build_trajectory_seed(task, golden_verification))
            append_jsonl(export_dir / "preference_pairs_train_seed.jsonl", build_preference_pair(task, golden_patch, rejected_patch))
        elif task.split == "eval":
            append_jsonl(export_dir / "eval_tasks.jsonl", spec)
        elif task.split == "private_heldout":
            private_spec = dict(spec)
            private_spec["golden_patch_ref"] = {
                "path": "withheld_from_training_exports",
                "sha256": spec["golden_patch_ref"]["sha256"],
                "export_to_training": False,
            }
            append_jsonl(export_dir / "private_heldout_tasks.jsonl", private_spec)

        task_results.append(
            {
                "task_id": task.task_id,
                "split": task.split,
                "task_family": "single_file_bugfix",
                "verified": golden_verification["verified"],
                "pre_public_failed_as_expected": golden_verification["pre_public_failed_as_expected"],
                "golden_patch_check_passed": golden_verification["patch_check_passed"],
                "golden_patch_applied": golden_verification["patch_applied"],
                "post_public_passed": golden_verification["post_public_passed"],
                "post_hidden_passed": golden_verification["post_hidden_passed"],
                "rejected_patch_verified": rejected_verification["verified"],
                "rejected_patch_check_passed": rejected_verification["patch_check_passed"],
                "rejected_patch_applied": rejected_verification["patch_applied"],
                "rejected_post_public_passed": rejected_verification["post_public_passed"],
                "rejected_post_hidden_passed": rejected_verification["post_hidden_passed"],
                "never_train_on": task.split == "private_heldout",
                "task_dir": str(task_dir),
            }
        )

    split_counts: dict[str, int] = {}
    for row in task_results:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1

    def count_jsonl(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    summary = {
        "schema_version": "forgeagent.internal_synthetic_micro_generator_summary.v0",
        "experiment_name": "internal_synthetic_micro_generator_v0",
        "task_count": len(task_results),
        "verified_task_count": sum(1 for row in task_results if row["verified"]),
        "split_counts": split_counts,
        "task_family_count": 1,
        "task_families": ["single_file_bugfix"],
        "patch_sft_train_rows": count_jsonl(export_dir / "patch_sft_train.jsonl"),
        "trajectory_sft_train_seed_rows": count_jsonl(export_dir / "trajectory_sft_train_seed.jsonl"),
        "preference_pair_train_seed_rows": count_jsonl(export_dir / "preference_pairs_train_seed.jsonl"),
        "eval_task_rows": count_jsonl(export_dir / "eval_tasks.jsonl"),
        "private_heldout_task_rows": count_jsonl(export_dir / "private_heldout_tasks.jsonl"),
        "private_heldout_exported_to_training": False,
        "launches_training_job": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_10_oracle_hidden_test_gate",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "task_results": str(OUT_DIR / "task_results.jsonl"),
            "dataset_exports": str(export_dir),
        },
    }

    write_json(OUT_DIR / "summary.json", summary)

    for row in task_results:
        append_jsonl(OUT_DIR / "task_results.jsonl", row)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("INTERNAL_SYNTHETIC_MICRO_GENERATOR_OK")


if __name__ == "__main__":
    main()

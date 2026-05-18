from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "results/local/internal_synthetic_micro_generator_v0"
OUT_DIR = PROJECT_ROOT / "results/local/oracle_hidden_test_gate_v0"
RUN_DIR = PROJECT_ROOT / "tmp/oracle_hidden_test_gate_runs"


@dataclass(frozen=True)
class TaskBundle:
    task_id: str
    split: str
    task_dir: Path
    spec: dict[str, Any]
    repo_before: Path
    hidden_test: Path
    golden_patch: Path
    rejected_patch: Path


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


def ensure_passed(result: dict[str, Any], context: str) -> None:
    if result["passed"]:
        return

    raise RuntimeError(
        f"{context} failed with exit code {result['exit_code']}\n"
        f"command: {' '.join(result['command'])}\n"
        f"cwd: {result['cwd']}\n"
        f"stdout:\n{result.get('stdout') or ''}\n"
        f"stderr:\n{result.get('stderr') or ''}"
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def init_git_repo(work_dir: Path) -> None:
    ensure_passed(run_command(["git", "init", "-q"], cwd=work_dir), "git init")
    ensure_passed(
        run_command(["git", "config", "user.email", "forge@example.invalid"], cwd=work_dir),
        "git config user.email",
    )
    ensure_passed(
        run_command(["git", "config", "user.name", "Forge Oracle Gate"], cwd=work_dir),
        "git config user.name",
    )
    ensure_passed(run_command(["git", "add", "."], cwd=work_dir), "git add baseline")
    ensure_passed(run_command(["git", "commit", "-q", "-m", "baseline"], cwd=work_dir), "git commit")


def copy_repo(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def changed_files_from_patch(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        parts = line.split()
        if len(parts) >= 4 and parts[3].startswith("b/"):
            files.append(parts[3][2:])
    return files


def make_mutation_patch(task: TaskBundle, label: str, mutations: dict[str, str]) -> Path:
    build_dir = RUN_DIR / "challenge_patch_build_repos" / task.task_id / label
    copy_repo(task.repo_before, build_dir)
    init_git_repo(build_dir)

    for relative_path, content in mutations.items():
        target = build_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    diff_result = run_command(["git", "diff", "--", *mutations.keys()], cwd=build_dir)
    ensure_passed(diff_result, f"git diff for {task.task_id}:{label}")
    patch_text = diff_result["stdout"]
    if not patch_text.strip():
        raise RuntimeError(f"empty mutation patch for {task.task_id}:{label}")

    out_path = OUT_DIR / "challenge_patches" / task.task_id / f"{label}.patch"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(patch_text if patch_text.endswith("\n") else patch_text + "\n", encoding="utf-8")
    return out_path


def make_empty_patch(task: TaskBundle) -> Path:
    out_path = OUT_DIR / "challenge_patches" / task.task_id / "empty.patch"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("", encoding="utf-8")
    return out_path


def current_utils_body(task: TaskBundle) -> str:
    return (task.repo_before / "app/utils.py").read_text(encoding="utf-8")


def semantic_noop_body(task: TaskBundle) -> str:
    body = current_utils_body(task)
    if body.endswith("\n"):
        return body + "\n# semantic no-op challenge patch\n"
    return body + "\n\n# semantic no-op challenge patch\n"


def wrong_file_body(task: TaskBundle) -> str:
    body = (task.repo_before / "app/__init__.py").read_text(encoding="utf-8")
    if body.endswith("\n"):
        return body + "\n# wrong-file challenge patch\n"
    return body + "\n\n# wrong-file challenge patch\n"


def public_overfit_body(task: TaskBundle) -> str:
    if task.task_id == "forge-micro-train-add-one":
        return "def add_one(x: int) -> int:\n    return 2\n"
    if task.task_id == "forge-micro-eval-square":
        return "def square(x: int) -> int:\n    return 9\n"
    if task.task_id == "forge-micro-private-heldout-max2":
        return "def max2(a: int, b: int) -> int:\n    return b\n"
    raise RuntimeError(f"no public-overfit body registered for {task.task_id}")


def verify_patch(task: TaskBundle, label: str, patch_path: Path) -> dict[str, Any]:
    work_dir = RUN_DIR / "challenge_verification" / task.task_id / label
    copy_repo(task.repo_before, work_dir)
    init_git_repo(work_dir)

    pre_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)

    local_patch = work_dir / "_candidate.patch"
    shutil.copy2(patch_path, local_patch)
    patch_text = local_patch.read_text(encoding="utf-8")

    patch_check = run_command(["git", "apply", "--check", local_patch.name], cwd=work_dir)
    if patch_check["passed"]:
        patch_apply = run_command(["git", "apply", local_patch.name], cwd=work_dir)
    else:
        patch_apply = {
            "command": ["git", "apply", local_patch.name],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "git apply --check failed; apply skipped.\n" + (patch_check.get("stderr") or ""),
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }

    if patch_apply["passed"]:
        changed_files_result = run_command(["git", "diff", "--name-only"], cwd=work_dir)
        post_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
        shutil.copy2(task.hidden_test, work_dir / "tests/test_hidden.py")
        post_hidden = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
    else:
        changed_files_result = {
            "command": ["git", "diff", "--name-only"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; changed-file listing skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }
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

    expected_files = set(task.spec["expected_edit_scope"]["files"])
    patch_changed_files = changed_files_from_patch(patch_text)
    observed_changed_files = [
        line.strip()
        for line in changed_files_result.get("stdout", "").splitlines()
        if line.strip()
    ]
    changed_files = observed_changed_files or patch_changed_files
    edit_scope_ok = bool(changed_files) and set(changed_files).issubset(expected_files)

    return {
        "schema_version": "forgeagent.oracle_patch_challenge_result.v0",
        "task_id": task.task_id,
        "split": task.split,
        "challenge": label,
        "patch_path": str(patch_path),
        "patch_sha256": sha256_text(patch_text),
        "patch_bytes": len(patch_text.encode("utf-8")),
        "changed_files": changed_files,
        "expected_files": sorted(expected_files),
        "edit_scope_ok": edit_scope_ok,
        "pre_public_failed_as_expected": not pre_public["passed"],
        "patch_check_passed": patch_check["passed"],
        "patch_applied": patch_apply["passed"],
        "post_public_passed": post_public["passed"],
        "post_hidden_passed": post_hidden["passed"],
        "solved": (not pre_public["passed"])
        and patch_apply["passed"]
        and post_public["passed"]
        and post_hidden["passed"],
        "pre_public": pre_public,
        "patch_check": patch_check,
        "patch_apply": patch_apply,
        "post_public": post_public,
        "post_hidden": post_hidden,
    }


def load_tasks() -> list[TaskBundle]:
    task_root = SOURCE_DIR / "tasks"
    tasks: list[TaskBundle] = []
    for task_dir in sorted(path for path in task_root.iterdir() if path.is_dir()):
        spec = read_json(task_dir / "task_spec.json")
        tasks.append(
            TaskBundle(
                task_id=spec["task_id"],
                split=spec["split"],
                task_dir=task_dir,
                spec=spec,
                repo_before=task_dir / "repo_before",
                hidden_test=task_dir / "hidden_tests/test_hidden.py",
                golden_patch=task_dir / "golden.patch",
                rejected_patch=task_dir / "rejected.patch",
            )
        )
    return tasks


def build_challenge_patches(task: TaskBundle) -> dict[str, Path]:
    challenge_dir = OUT_DIR / "challenge_patches" / task.task_id
    challenge_dir.mkdir(parents=True, exist_ok=True)

    golden_copy = challenge_dir / "golden.patch"
    rejected_copy = challenge_dir / "rejected.patch"
    shutil.copy2(task.golden_patch, golden_copy)
    shutil.copy2(task.rejected_patch, rejected_copy)

    return {
        "golden": golden_copy,
        "rejected": rejected_copy,
        "semantic_noop": make_mutation_patch(
            task,
            "semantic_noop",
            {"app/utils.py": semantic_noop_body(task)},
        ),
        "empty": make_empty_patch(task),
        "wrong_file": make_mutation_patch(
            task,
            "wrong_file",
            {"app/__init__.py": wrong_file_body(task)},
        ),
        "public_overfit": make_mutation_patch(
            task,
            "public_overfit",
            {"app/utils.py": public_overfit_body(task)},
        ),
    }


def challenge_failed(result: dict[str, Any]) -> bool:
    return not result["solved"]


def score_task(task: TaskBundle, challenge_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    golden = challenge_results["golden"]
    rejected = challenge_results["rejected"]
    semantic_noop = challenge_results["semantic_noop"]
    empty = challenge_results["empty"]
    wrong_file = challenge_results["wrong_file"]
    public_overfit = challenge_results["public_overfit"]

    golden_passed = golden["solved"] and golden["edit_scope_ok"]
    rejected_failed = rejected["patch_check_passed"] and rejected["patch_applied"] and challenge_failed(rejected)
    semantic_noop_failed = (
        semantic_noop["patch_check_passed"]
        and semantic_noop["patch_applied"]
        and semantic_noop["edit_scope_ok"]
        and challenge_failed(semantic_noop)
    )
    empty_failed = (not empty["patch_check_passed"]) and challenge_failed(empty)
    wrong_file_failed = (
        wrong_file["patch_check_passed"]
        and wrong_file["patch_applied"]
        and not wrong_file["edit_scope_ok"]
        and challenge_failed(wrong_file)
    )
    public_overfit_caught_by_hidden = (
        public_overfit["patch_check_passed"]
        and public_overfit["patch_applied"]
        and public_overfit["post_public_passed"]
        and not public_overfit["post_hidden_passed"]
    )

    checks = {
        "golden_patch_passed": golden_passed,
        "rejected_patch_failed": rejected_failed,
        "semantic_noop_patch_failed": semantic_noop_failed,
        "empty_patch_failed": empty_failed,
        "wrong_file_patch_failed": wrong_file_failed,
        "public_overfit_caught_by_hidden": public_overfit_caught_by_hidden,
    }

    weights = {
        "golden_patch_passed": 0.25,
        "rejected_patch_failed": 0.15,
        "semantic_noop_patch_failed": 0.15,
        "empty_patch_failed": 0.10,
        "wrong_file_patch_failed": 0.10,
        "public_overfit_caught_by_hidden": 0.25,
    }
    oracle_strength_score = round(sum(weights[name] for name, passed in checks.items() if passed), 6)

    hidden_coverage_score = 1.0 if public_overfit_caught_by_hidden else 0.0
    anti_overfit_score = 1.0 if public_overfit_caught_by_hidden and wrong_file_failed else 0.0
    edit_scope_score = 1.0 if golden["edit_scope_ok"] and not wrong_file["edit_scope_ok"] else 0.0

    gate_passed = (
        oracle_strength_score >= 0.95
        and hidden_coverage_score >= 1.0
        and anti_overfit_score >= 1.0
        and edit_scope_score >= 1.0
        and all(checks.values())
    )

    return {
        "schema_version": "forgeagent.oracle_task_score.v0",
        "task_id": task.task_id,
        "split": task.split,
        "never_train_on": task.spec["never_train_on"],
        "checks": checks,
        "oracle_strength_score": oracle_strength_score,
        "hidden_coverage_score": hidden_coverage_score,
        "anti_overfit_score": anti_overfit_score,
        "edit_scope_score": edit_scope_score,
        "minimum_oracle_strength_score": 0.95,
        "gate_passed": gate_passed,
    }


def validate_hidden_and_private_isolation(tasks: list[TaskBundle]) -> dict[str, Any]:
    export_dir = SOURCE_DIR / "dataset_exports"
    training_export_paths = [
        export_dir / "patch_sft_train.jsonl",
        export_dir / "trajectory_sft_train_seed.jsonl",
        export_dir / "preference_pairs_train_seed.jsonl",
    ]
    training_blob = "\n".join(path.read_text(encoding="utf-8") for path in training_export_paths)

    hidden_leaks: list[dict[str, Any]] = []
    private_patch_leaks: list[dict[str, Any]] = []
    private_task_id_leaks: list[dict[str, Any]] = []

    for task in tasks:
        hidden_text = task.hidden_test.read_text(encoding="utf-8").strip()
        if hidden_text and hidden_text in training_blob:
            hidden_leaks.append({"task_id": task.task_id, "path": str(task.hidden_test)})

        if task.split == "private_heldout":
            private_patch_text = task.golden_patch.read_text(encoding="utf-8").strip()
            if private_patch_text and private_patch_text in training_blob:
                private_patch_leaks.append({"task_id": task.task_id, "path": str(task.golden_patch)})
            if task.task_id in training_blob:
                private_task_id_leaks.append({"task_id": task.task_id})

    private_export = (export_dir / "private_heldout_tasks.jsonl").read_text(encoding="utf-8")
    private_export_withholds_patch = "withheld_from_training_exports" in private_export

    return {
        "schema_version": "forgeagent.hidden_test_isolation_report.v0",
        "training_export_paths": [str(path) for path in training_export_paths],
        "hidden_test_leak_count": len(hidden_leaks),
        "hidden_test_leaks": hidden_leaks,
        "private_patch_leak_count": len(private_patch_leaks),
        "private_patch_leaks": private_patch_leaks,
        "private_task_id_leak_count": len(private_task_id_leaks),
        "private_task_id_leaks": private_task_id_leaks,
        "private_export_withholds_patch": private_export_withholds_patch,
        "hidden_test_isolation_passed": len(hidden_leaks) == 0,
        "private_heldout_isolation_passed": len(private_patch_leaks) == 0
        and len(private_task_id_leaks) == 0
        and private_export_withholds_patch,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    source_summary = read_json(SOURCE_DIR / "summary.json")
    tasks = load_tasks()
    challenge_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []

    for task in tasks:
        challenge_patches = build_challenge_patches(task)
        challenge_results = {
            label: verify_patch(task, label, patch_path)
            for label, patch_path in challenge_patches.items()
        }
        for result in challenge_results.values():
            append_jsonl(OUT_DIR / "patch_challenge_results.jsonl", result)
            challenge_rows.append(result)

        score = score_task(task, challenge_results)
        append_jsonl(OUT_DIR / "task_oracle_scores.jsonl", score)
        score_rows.append(score)

    isolation = validate_hidden_and_private_isolation(tasks)
    write_json(OUT_DIR / "hidden_test_isolation_report.json", isolation)

    def count_challenge(name: str, predicate: Any) -> int:
        return sum(1 for row in challenge_rows if row["challenge"] == name and predicate(row))

    summary = {
        "schema_version": "forgeagent.oracle_hidden_test_gate_summary.v0",
        "gate_name": "oracle_hidden_test_gate_v0",
        "source_step": "step29_9_internal_synthetic_micro_generator_v0",
        "source_verified_task_count": source_summary["verified_task_count"],
        "task_count": len(tasks),
        "passed_task_count": sum(1 for row in score_rows if row["gate_passed"]),
        "golden_patch_pass_count": count_challenge("golden", lambda row: row["solved"]),
        "rejected_patch_fail_count": count_challenge("rejected", challenge_failed),
        "semantic_noop_patch_fail_count": count_challenge("semantic_noop", challenge_failed),
        "empty_patch_fail_count": count_challenge("empty", challenge_failed),
        "wrong_file_patch_fail_count": count_challenge("wrong_file", challenge_failed),
        "public_overfit_hidden_catch_count": count_challenge(
            "public_overfit",
            lambda row: row["post_public_passed"] and not row["post_hidden_passed"],
        ),
        "minimum_oracle_strength_score": 0.95,
        "minimum_observed_oracle_strength_score": min(
            row["oracle_strength_score"] for row in score_rows
        ),
        "hidden_test_isolation_passed": isolation["hidden_test_isolation_passed"],
        "private_heldout_isolation_passed": isolation["private_heldout_isolation_passed"],
        "training_launch_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_11_agentic_trajectory_recorder_v1",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "task_oracle_scores": str(OUT_DIR / "task_oracle_scores.jsonl"),
            "patch_challenge_results": str(OUT_DIR / "patch_challenge_results.jsonl"),
            "hidden_test_isolation_report": str(OUT_DIR / "hidden_test_isolation_report.json"),
            "challenge_patches": str(OUT_DIR / "challenge_patches"),
        },
    }

    write_json(OUT_DIR / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("ORACLE_HIDDEN_TEST_GATE_OK")


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import shutil
import time
import uuid

from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.command_runner import CommandResult, run_shell_command
from forgeagentcoder.rewards.code_rewards import compute_patch_reward


@dataclass(frozen=True)
class PatchEvalResult:
    task_id: str
    run_id: str
    work_dir: str
    pre_test: dict
    patch_applied: bool
    patch_apply_result: dict
    post_test: dict
    reward: float
    elapsed_seconds: float

    @property
    def post_tests_passed(self) -> bool:
        return bool(self.post_test.get("passed"))


def _result_to_dict(result: CommandResult) -> dict:
    data = asdict(result)
    data["passed"] = result.passed
    return data


def prepare_workdir(task: AgentTask, *, work_root: str | Path) -> tuple[str, Path]:
    run_id = f"{task.task_id}-{uuid.uuid4().hex[:8]}"
    work_root = Path(work_root)
    work_dir = work_root / run_id
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(task.repo_dir, work_dir)
    return run_id, work_dir


def initialize_git_repo(work_dir: Path) -> None:
    run_shell_command("git init", cwd=work_dir, timeout_seconds=30)
    run_shell_command('git config user.email "forgeagent@example.local"', cwd=work_dir, timeout_seconds=30)
    run_shell_command('git config user.name "ForgeAgent"', cwd=work_dir, timeout_seconds=30)
    run_shell_command("git add .", cwd=work_dir, timeout_seconds=30)
    run_shell_command('git commit -m "baseline"', cwd=work_dir, timeout_seconds=30)


def remove_python_caches(work_dir: Path) -> None:
    """Remove Python bytecode caches to avoid stale test results after fast patching."""
    for cache_dir in work_dir.rglob("__pycache__"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir, ignore_errors=True)

    for pyc_file in work_dir.rglob("*.pyc"):
        if pyc_file.is_file():
            pyc_file.unlink(missing_ok=True)


def evaluate_patch_task(
    task: AgentTask,
    *,
    patch_file: str | Path,
    work_root: str | Path,
    output_json: str | Path | None = None,
) -> PatchEvalResult:
    started = time.time()
    task.validate()

    run_id, work_dir = prepare_workdir(task, work_root=work_root)
    initialize_git_repo(work_dir)

    remove_python_caches(work_dir)
    pre_test = run_shell_command(
        task.test_command,
        cwd=work_dir,
        timeout_seconds=task.timeout_seconds,
    )

    patch_file = Path(patch_file).resolve()
    patch_apply = run_shell_command(
        f"git apply {patch_file}",
        cwd=work_dir,
        timeout_seconds=60,
    )
    patch_applied = patch_apply.passed

    if patch_applied:
        remove_python_caches(work_dir)
        post_test = run_shell_command(
            task.test_command,
            cwd=work_dir,
            timeout_seconds=task.timeout_seconds,
        )
    else:
        post_test = CommandResult(
            command=task.test_command,
            cwd=str(work_dir),
            exit_code=1,
            stdout="",
            stderr="Patch did not apply; post-test skipped.",
            elapsed_seconds=0.0,
            timed_out=False,
        )

    reward = compute_patch_reward(
        pre_tests_passed=pre_test.passed,
        patch_applied=patch_applied,
        post_tests_passed=post_test.passed,
    )

    result = PatchEvalResult(
        task_id=task.task_id,
        run_id=run_id,
        work_dir=str(work_dir),
        pre_test=_result_to_dict(pre_test),
        patch_applied=patch_applied,
        patch_apply_result=_result_to_dict(patch_apply),
        post_test=_result_to_dict(post_test),
        reward=reward,
        elapsed_seconds=round(time.time() - started, 6),
    )

    if output_json is not None:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    return result

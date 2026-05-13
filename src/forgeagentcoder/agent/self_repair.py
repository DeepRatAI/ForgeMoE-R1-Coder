from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import time

from forgeagentcoder.agent.patch_provider import PatchCandidate, ScriptedPatchProvider
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.patch_task_eval import evaluate_patch_task


@dataclass(frozen=True)
class RepairIterationResult:
    iteration: int
    patch_id: str
    patch_path: str
    patch_applied: bool
    post_tests_passed: bool
    reward: float
    eval_result: dict


@dataclass(frozen=True)
class SelfRepairResult:
    task_id: str
    solved: bool
    iterations_used: int
    max_iterations: int
    best_reward: float
    best_patch_id: str | None
    elapsed_seconds: float
    trajectory: list[RepairIterationResult]


def run_self_repair_loop(
    *,
    task: AgentTask,
    patch_provider: ScriptedPatchProvider,
    work_root: str | Path,
    max_iterations: int,
    output_json: str | Path | None = None,
) -> SelfRepairResult:
    started = time.time()

    trajectory: list[RepairIterationResult] = []
    solved = False
    best_reward = float("-inf")
    best_patch_id: str | None = None

    for iteration in range(max_iterations):
        candidate: PatchCandidate | None = patch_provider.get_candidate(iteration)
        if candidate is None:
            break

        eval_result = evaluate_patch_task(
            task,
            patch_file=candidate.patch_path,
            work_root=work_root,
        )

        if eval_result.reward > best_reward:
            best_reward = eval_result.reward
            best_patch_id = candidate.patch_id

        iter_result = RepairIterationResult(
            iteration=iteration,
            patch_id=candidate.patch_id,
            patch_path=str(candidate.patch_path),
            patch_applied=eval_result.patch_applied,
            post_tests_passed=eval_result.post_tests_passed,
            reward=eval_result.reward,
            eval_result=asdict(eval_result),
        )
        trajectory.append(iter_result)

        if eval_result.post_tests_passed:
            solved = True
            break

    if best_reward == float("-inf"):
        best_reward = 0.0

    result = SelfRepairResult(
        task_id=task.task_id,
        solved=solved,
        iterations_used=len(trajectory),
        max_iterations=max_iterations,
        best_reward=round(best_reward, 6),
        best_patch_id=best_patch_id,
        elapsed_seconds=round(time.time() - started, 6),
        trajectory=trajectory,
    )

    if output_json is not None:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(asdict(result), indent=2, default=str), encoding="utf-8")

    return result

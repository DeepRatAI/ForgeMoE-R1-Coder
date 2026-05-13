from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import time

from forgeagentcoder.agent.patch_provider import PatchCandidate
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.patch_task_eval import evaluate_patch_task


@dataclass(frozen=True)
class VerifiedCandidate:
    patch_id: str
    patch_path: str
    patch_applied: bool
    post_tests_passed: bool
    reward: float
    elapsed_seconds: float
    eval_result: dict


@dataclass(frozen=True)
class VerifierRunResult:
    task_id: str
    selected_patch_id: str | None
    selected_reward: float
    solved: bool
    candidate_count: int
    elapsed_seconds: float
    ranked_candidates: list[VerifiedCandidate]


def _rank_key(candidate: VerifiedCandidate) -> tuple[float, int, int, float]:
    return (
        candidate.reward,
        int(candidate.post_tests_passed),
        int(candidate.patch_applied),
        -candidate.elapsed_seconds,
    )


def run_executable_verifier(
    *,
    task: AgentTask,
    candidates: list[PatchCandidate],
    work_root: str | Path,
    output_json: str | Path | None = None,
) -> VerifierRunResult:
    if not candidates:
        raise ValueError("At least one candidate patch is required")

    started = time.time()
    verified: list[VerifiedCandidate] = []

    for candidate in candidates:
        eval_result = evaluate_patch_task(
            task,
            patch_file=candidate.patch_path,
            work_root=work_root,
        )

        verified.append(
            VerifiedCandidate(
                patch_id=candidate.patch_id,
                patch_path=str(candidate.patch_path),
                patch_applied=eval_result.patch_applied,
                post_tests_passed=eval_result.post_tests_passed,
                reward=float(eval_result.reward),
                elapsed_seconds=float(eval_result.elapsed_seconds),
                eval_result=asdict(eval_result),
            )
        )

    ranked = sorted(verified, key=_rank_key, reverse=True)
    best = ranked[0]

    result = VerifierRunResult(
        task_id=task.task_id,
        selected_patch_id=best.patch_id,
        selected_reward=round(best.reward, 6),
        solved=bool(best.post_tests_passed),
        candidate_count=len(candidates),
        elapsed_seconds=round(time.time() - started, 6),
        ranked_candidates=ranked,
    )

    if output_json is not None:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(asdict(result), indent=2, default=str),
            encoding="utf-8",
        )

    return result

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import time
from typing import Iterable

from forgeagentcoder.agent.candidate_pipeline import CandidateGenerationResult


@dataclass(frozen=True)
class ExperimentTaskResult:
    task_id: str
    solved: bool
    selected_patch_id: str | None
    selected_reward: float
    raw_response_count: int
    parsed_candidate_count: int
    parse_failure_count: int
    result_path: str


@dataclass(frozen=True)
class ExperimentSummary:
    experiment_name: str
    total_tasks: int
    solved_tasks: int
    failed_tasks: int
    solve_rate: float
    average_selected_reward: float
    total_parse_failures: int
    average_parsed_candidates: float
    elapsed_seconds: float
    task_results_jsonl: str
    summary_json: str


def candidate_result_to_task_result(
    result: CandidateGenerationResult,
    *,
    result_path: str | Path,
) -> ExperimentTaskResult:
    verifier_result = result.verifier_result or {}
    selected_reward = float(verifier_result.get("selected_reward", 0.0))

    return ExperimentTaskResult(
        task_id=result.task_id,
        solved=bool(result.solved),
        selected_patch_id=result.selected_patch_id,
        selected_reward=selected_reward,
        raw_response_count=int(result.raw_response_count),
        parsed_candidate_count=int(result.parsed_candidate_count),
        parse_failure_count=int(result.parse_failure_count),
        result_path=str(result_path),
    )


def summarize_experiment(
    *,
    experiment_name: str,
    task_results: list[ExperimentTaskResult],
    elapsed_seconds: float,
    task_results_jsonl: str | Path,
    summary_json: str | Path,
) -> ExperimentSummary:
    total = len(task_results)
    solved = sum(1 for item in task_results if item.solved)
    failed = total - solved

    rewards = [item.selected_reward for item in task_results]
    parsed_counts = [item.parsed_candidate_count for item in task_results]

    return ExperimentSummary(
        experiment_name=experiment_name,
        total_tasks=total,
        solved_tasks=solved,
        failed_tasks=failed,
        solve_rate=round(solved / total, 6) if total else 0.0,
        average_selected_reward=round(sum(rewards) / len(rewards), 6) if rewards else 0.0,
        total_parse_failures=sum(item.parse_failure_count for item in task_results),
        average_parsed_candidates=round(sum(parsed_counts) / len(parsed_counts), 6)
        if parsed_counts
        else 0.0,
        elapsed_seconds=round(elapsed_seconds, 6),
        task_results_jsonl=str(task_results_jsonl),
        summary_json=str(summary_json),
    )


def write_experiment_outputs(
    *,
    experiment_name: str,
    task_results: Iterable[ExperimentTaskResult],
    output_dir: str | Path,
    started_at: float,
) -> ExperimentSummary:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    task_results = list(task_results)

    task_results_jsonl = output_dir / "task_results.jsonl"
    summary_json = output_dir / "summary.json"

    with task_results_jsonl.open("w", encoding="utf-8") as f:
        for row in task_results:
            f.write(json.dumps(asdict(row), ensure_ascii=False, default=str) + "\n")

    summary = summarize_experiment(
        experiment_name=experiment_name,
        task_results=task_results,
        elapsed_seconds=time.time() - started_at,
        task_results_jsonl=task_results_jsonl,
        summary_json=summary_json,
    )

    summary_json.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    return summary

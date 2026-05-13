from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import time
from typing import Iterable

from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.eval.patch_task_eval import evaluate_patch_task


@dataclass(frozen=True)
class PatchTaskSpec:
    task_json: Path
    patch_file: Path


@dataclass(frozen=True)
class BatchEvalSummary:
    benchmark_name: str
    total_tasks: int
    solved_tasks: int
    failed_tasks: int
    pass_rate: float
    average_reward: float
    failed_task_ids: list[str]
    elapsed_seconds: float
    results_jsonl: str


def load_task_specs(path: str | Path) -> list[PatchTaskSpec]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    specs: list[PatchTaskSpec] = []
    for item in data["tasks"]:
        task_json = Path(item["task_json"])
        patch_file = Path(item["patch_file"])

        if not task_json.is_absolute():
            task_json = (path.parent / task_json).resolve()
        if not patch_file.is_absolute():
            patch_file = (path.parent / patch_file).resolve()

        specs.append(PatchTaskSpec(task_json=task_json, patch_file=patch_file))

    return specs


def run_batch_patch_eval(
    *,
    benchmark_name: str,
    task_specs: Iterable[PatchTaskSpec],
    work_root: str | Path,
    output_dir: str | Path,
) -> BatchEvalSummary:
    started = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "results.jsonl"
    summary_path = output_dir / "summary.json"

    solved = 0
    rewards: list[float] = []
    failed_task_ids: list[str] = []
    total = 0

    with results_path.open("w", encoding="utf-8") as f:
        for spec in task_specs:
            total += 1
            task = AgentTask.from_json_file(spec.task_json)

            result = evaluate_patch_task(
                task,
                patch_file=spec.patch_file,
                work_root=work_root,
            )

            result_dict = asdict(result)
            f.write(json.dumps(result_dict, default=str) + "\n")

            rewards.append(float(result.reward))
            if result.post_tests_passed:
                solved += 1
            else:
                failed_task_ids.append(result.task_id)

    failed = total - solved
    pass_rate = solved / total if total else 0.0
    average_reward = sum(rewards) / len(rewards) if rewards else 0.0

    summary = BatchEvalSummary(
        benchmark_name=benchmark_name,
        total_tasks=total,
        solved_tasks=solved,
        failed_tasks=failed,
        pass_rate=round(pass_rate, 6),
        average_reward=round(average_reward, 6),
        failed_task_ids=failed_task_ids,
        elapsed_seconds=round(time.time() - started, 6),
        results_jsonl=str(results_path),
    )

    summary_path.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    return summary

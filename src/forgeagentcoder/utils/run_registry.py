from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import subprocess
from typing import Any


@dataclass(frozen=True)
class RunRegistryEntry:
    step: int
    name: str
    status: str
    category: str
    git_commit: str
    manifest_s3: str
    artifact_s3: str
    primary_results_s3: list[str]
    metrics: dict[str, Any]
    gpu_required: bool
    h100_purchase_required: bool


@dataclass(frozen=True)
class RunRegistry:
    project: str
    registry_version: str
    git_commit: str
    s3_bucket: str
    entries: list[RunRegistryEntry]


def current_git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
    ).strip()


def s3(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def build_run_registry(*, bucket: str, git_commit: str) -> RunRegistry:
    entries = [
        RunRegistryEntry(
            step=9,
            name="agentic_eval_harness",
            status="ok",
            category="evaluation_core",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step9_agentic_eval_harness_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step9_eval_harness_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/09_agentic_eval_harness/toy_patch_eval_result.json"),
            ],
            metrics={
                "toy_patch_eval": "ok",
                "reward": 1.25,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=10,
            name="batch_benchmark_harness",
            status="ok",
            category="evaluation_core",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step10_batch_benchmark_harness_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step10_batch_benchmark_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/10_batch_benchmark_harness/toy_benchmark_v0/results.jsonl"),
                s3(bucket, "results/10_batch_benchmark_harness/toy_benchmark_v0/summary.json"),
            ],
            metrics={
                "total_tasks": 3,
                "solved_tasks": 3,
                "pass_rate": 1.0,
                "average_reward": 1.25,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=11,
            name="self_repair_loop",
            status="ok",
            category="agent_loop",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step11_self_repair_loop_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step11_self_repair_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/11_self_repair_loop/toy_self_repair_v0/trajectory.json"),
            ],
            metrics={
                "solved": True,
                "iterations_used": 2,
                "best_reward": 1.25,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=12,
            name="trajectory_dataset_exporter",
            status="ok",
            category="data_generation",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step12_trajectory_dataset_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step12_trajectory_dataset_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/12_trajectory_dataset/toy_self_repair_v0/patch_attempts.jsonl"),
                s3(bucket, "results/12_trajectory_dataset/toy_self_repair_v0/sft_positive.jsonl"),
                s3(bucket, "results/12_trajectory_dataset/toy_self_repair_v0/summary.json"),
            ],
            metrics={
                "total_attempts": 2,
                "positive_attempts": 1,
                "negative_attempts": 1,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=13,
            name="executable_verifier_reranker",
            status="ok",
            category="verifier",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step13_executable_verifier_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step13_executable_verifier_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/13_executable_verifier/toy_executable_verifier_v0/verification.json"),
            ],
            metrics={
                "candidate_count": 3,
                "selected_patch_id": "good_patch_modulo",
                "solved": True,
                "selected_reward": 1.25,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=14,
            name="model_io_layer",
            status="ok",
            category="model_interface",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step14_model_io_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step14_model_io_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/14_model_io_layer/toy_model_io_v0/prompt_messages.json"),
                s3(bucket, "results/14_model_io_layer/toy_model_io_v0/raw_model_response.txt"),
                s3(bucket, "results/14_model_io_layer/toy_model_io_v0/parsed.patch"),
                s3(bucket, "results/14_model_io_layer/toy_model_io_v0/eval_result.json"),
            ],
            metrics={
                "patch_applied": True,
                "post_tests_passed": True,
                "reward": 1.25,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=15,
            name="candidate_generation_pipeline",
            status="ok",
            category="agent_pipeline",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step15_candidate_generation_pipeline_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step15_candidate_pipeline_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/15_candidate_generation_pipeline/toy_candidate_pipeline_v0/generation_pipeline_result.json"),
                s3(bucket, "results/15_candidate_generation_pipeline/toy_candidate_pipeline_v0/prompt_messages.json"),
            ],
            metrics={
                "raw_response_count": 3,
                "parsed_candidate_count": 2,
                "parse_failure_count": 1,
                "selected_patch_id": "raw_good_2_candidate_2",
                "solved": True,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=16,
            name="agentic_experiment_runner",
            status="ok",
            category="experiment_runner",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step16_agentic_experiment_runner_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step16_experiment_runner_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/16_agentic_experiment_runner/toy_agentic_experiment_v0/task_results.jsonl"),
                s3(bucket, "results/16_agentic_experiment_runner/toy_agentic_experiment_v0/summary.json"),
            ],
            metrics={
                "total_tasks": 2,
                "solved_tasks": 2,
                "solve_rate": 1.0,
                "average_selected_reward": 1.25,
                "total_parse_failures": 2,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=17,
            name="run_registry_index",
            status="ok",
            category="experiment_control",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step17_run_registry_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step17_run_registry_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "reports/run_registry.json"),
                s3(bucket, "reports/run_registry.md"),
            ],
            metrics={
                "registry_version": "v0",
                "entry_count_at_creation": 8,
                "covered_steps_at_creation": "9-16",
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=176,
            name="engineering_decision_records",
            status="ok",
            category="engineering_documentation",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step17_6_engineering_records_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step17_6_engineering_records_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "reports/step17_6_engineering_records_manifest.json"),
            ],
            metrics={
                "adr_min_count": 12,
                "bug_min_count": 5,
                "commit": "6611e43",
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),
        RunRegistryEntry(
            step=18,
            name="real_model_adapter_contract",
            status="ok",
            category="model_runtime_boundary",
            git_commit=git_commit,
            manifest_s3=s3(bucket, "reports/step18_model_adapter_manifest.json"),
            artifact_s3=s3(bucket, "configs/project_scaffold/forgemoe_r1_agent_coder_step18_model_adapter_v0.tar.gz"),
            primary_results_s3=[
                s3(bucket, "results/18_model_adapter/toy_model_adapter_v0/prompt_messages.json"),
                s3(bucket, "results/18_model_adapter/toy_model_adapter_v0/generated_responses.jsonl"),
                s3(bucket, "results/18_model_adapter/toy_model_adapter_v0/candidate_pipeline_result.json"),
                s3(bucket, "results/18_model_adapter/toy_model_adapter_v0/model_adapter_result.json"),
            ],
            metrics={
                "generated_response_count": 3,
                "parse_failure_count": 1,
                "selected_patch_id": "mock_good_max2_candidate_2",
                "solved": True,
                "reward": 1.25,
                "real_model_downloaded": False,
            },
            gpu_required=False,
            h100_purchase_required=False,
        ),

    ]

    return RunRegistry(
        project="ForgeMoE-R1-Agent-Coder",
        registry_version="v0",
        git_commit=git_commit,
        s3_bucket=bucket,
        entries=entries,
    )


def write_registry_json(registry: RunRegistry, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(registry), indent=2, default=str), encoding="utf-8")


def render_registry_markdown(registry: RunRegistry) -> str:
    lines = [
        "# ForgeMoE-R1-Agent-Coder Run Registry",
        "",
        f"- Project: `{registry.project}`",
        f"- Registry version: `{registry.registry_version}`",
        f"- Git commit: `{registry.git_commit}`",
        f"- S3 bucket: `{registry.s3_bucket}`",
        "",
        "## Runs",
        "",
        "| Step | Name | Category | Status | GPU | Key metrics |",
        "|---:|---|---|---|---|---|",
    ]

    for entry in registry.entries:
        metrics = ", ".join(f"{k}={v}" for k, v in entry.metrics.items())
        gpu = "yes" if entry.gpu_required else "no"
        lines.append(
            f"| {entry.step} | `{entry.name}` | `{entry.category}` | `{entry.status}` | {gpu} | {metrics} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- All listed runs are model-free foundation runs.",
            "- No H100 purchase was required.",
            "- No GPU was required.",
            "- This registry is the control-plane index before real model integration.",
            "",
        ]
    )

    return "\n".join(lines)


def write_registry_markdown(registry: RunRegistry, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_registry_markdown(registry), encoding="utf-8")

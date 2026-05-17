from __future__ import annotations

from pathlib import Path
import json
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "results/local/internal_synthetic_task_generator_design_v0"


GENERATOR_MODULES: list[dict[str, Any]] = [
    {
        "module_id": "seed_repo_registry",
        "purpose": "Track candidate seed repositories and their legal/provenance status.",
        "inputs": ["repo_url", "commit_sha", "license_metadata", "language_metadata"],
        "outputs": ["seed_repo_manifest"],
        "blocks_if_missing": True
    },
    {
        "module_id": "repo_snapshotter",
        "purpose": "Create immutable repository snapshots for reproducible task generation.",
        "inputs": ["seed_repo_manifest"],
        "outputs": ["repo_snapshot_manifest", "source_archive_ref"],
        "blocks_if_missing": True
    },
    {
        "module_id": "task_mutation_engine",
        "purpose": "Create controlled bugs, feature gaps, migrations, refactors and config issues.",
        "inputs": ["repo_snapshot_manifest", "task_family_config"],
        "outputs": ["candidate_task_spec"],
        "blocks_if_missing": True
    },
    {
        "module_id": "oracle_builder",
        "purpose": "Build executable pre/post oracle commands and expected behavior checks.",
        "inputs": ["candidate_task_spec"],
        "outputs": ["oracle_manifest"],
        "blocks_if_missing": True
    },
    {
        "module_id": "hidden_test_builder",
        "purpose": "Generate hidden tests that reduce shallow patch overfitting.",
        "inputs": ["candidate_task_spec", "oracle_manifest"],
        "outputs": ["hidden_test_manifest"],
        "blocks_if_missing": True
    },
    {
        "module_id": "difficulty_estimator",
        "purpose": "Score task difficulty, edit locality, file span and semantic depth.",
        "inputs": ["candidate_task_spec", "oracle_manifest"],
        "outputs": ["difficulty_report"],
        "blocks_if_missing": False
    },
    {
        "module_id": "patch_verifier",
        "purpose": "Verify that candidate patches apply and solve executable tests.",
        "inputs": ["candidate_patch", "oracle_manifest", "hidden_test_manifest"],
        "outputs": ["patch_verification_result"],
        "blocks_if_missing": True
    },
    {
        "module_id": "negative_patch_miner",
        "purpose": "Preserve wrong-file, non-applying, overbroad and test-failing patches as training signal.",
        "inputs": ["patch_verification_result", "model_response"],
        "outputs": ["negative_patch_record"],
        "blocks_if_missing": False
    },
    {
        "module_id": "trajectory_recorder",
        "purpose": "Record inspect-plan-edit-test-repair trajectories for agentic SFT and preference learning.",
        "inputs": ["tool_events", "patch_attempts", "oracle_results"],
        "outputs": ["agentic_trajectory_record"],
        "blocks_if_missing": True
    },
    {
        "module_id": "split_and_holdout_allocator",
        "purpose": "Assign generated artifacts to train, eval or private heldout with strict isolation.",
        "inputs": ["task_spec", "repo_snapshot_manifest", "dedup_signature"],
        "outputs": ["split_assignment"],
        "blocks_if_missing": True
    },
    {
        "module_id": "contamination_scanner",
        "purpose": "Detect overlap with public benchmarks, previous train data and private holdout.",
        "inputs": ["task_spec", "patch_text", "repo_snapshot_manifest"],
        "outputs": ["contamination_report"],
        "blocks_if_missing": True
    },
    {
        "module_id": "provenance_manifest_writer",
        "purpose": "Persist lineage for every task, patch, trajectory and split assignment.",
        "inputs": ["all_generation_artifacts"],
        "outputs": ["provenance_manifest"],
        "blocks_if_missing": True
    },
    {
        "module_id": "quality_scorer",
        "purpose": "Score utility, correctness, difficulty, agentic value and risk.",
        "inputs": ["task_spec", "oracle_result", "trajectory_record"],
        "outputs": ["quality_score_report"],
        "blocks_if_missing": True
    }
]


TASK_SCHEMA: dict[str, Any] = {
    "schema_version": "forgeagent.synthetic_executable_task.v0",
    "required_fields": [
        "task_id",
        "source_repo",
        "repo_snapshot",
        "task_family",
        "instruction",
        "pre_failure_command",
        "post_success_command",
        "hidden_tests",
        "expected_edit_scope",
        "difficulty",
        "split",
        "provenance",
        "quality_scores",
        "contamination_report"
    ],
    "task_families": [
        "single_file_bugfix",
        "multi_file_bugfix",
        "regression_test_creation",
        "api_migration",
        "refactor_with_behavior_preservation",
        "dependency_upgrade",
        "typing_or_static_analysis_repair",
        "security_hardening",
        "performance_micro_optimization",
        "configuration_or_packaging_fix",
        "integration_edge_case_fix",
        "fullstack_vertical_slice_change"
    ],
    "split_values": ["train", "eval", "private_heldout"],
    "private_heldout_rule": "never_train_on_private_heldout"
}


TRAJECTORY_SCHEMA: dict[str, Any] = {
    "schema_version": "forgeagent.agentic_trajectory.v0",
    "required_fields": [
        "trajectory_id",
        "task_id",
        "model_id",
        "adapter_id",
        "run_id",
        "events",
        "patch_attempts",
        "test_results",
        "repair_steps",
        "final_status",
        "reward",
        "provenance",
        "privacy_scan"
    ],
    "event_types": [
        "read_file",
        "list_files",
        "search",
        "plan",
        "generate_patch",
        "apply_patch",
        "run_tests",
        "observe_failure",
        "repair",
        "final_answer"
    ],
    "reward_values": [
        "solved",
        "partial",
        "patch_did_not_apply",
        "tests_failed",
        "wrong_file",
        "overbroad_patch",
        "unsafe_or_secret_leak"
    ]
}


PRIVATE_HELDOUT_PROTOCOL: dict[str, Any] = {
    "schema_version": "forgeagent.private_heldout_protocol.v0",
    "purpose": "Provide contamination-resistant north-star evaluation for autonomous e2e coding agents.",
    "rules": [
        "private_heldout_tasks_are_never_used_for_training",
        "private_heldout_expected_patches_are_not_stored_in_training_paths",
        "private_heldout_repos_are_snapshot_versioned",
        "access_is_restricted",
        "public_benchmark_overlap_is_scanned",
        "train_eval_holdout_near_duplicate_scan_is_required",
        "promotion_claims_require_private_heldout_results"
    ],
    "task_requirements": [
        "reproducible_environment",
        "strong_oracle",
        "hidden_tests",
        "clear_instruction",
        "expected_behavior",
        "difficulty_label",
        "provenance_manifest",
        "contamination_report"
    ],
    "promotion_metrics": [
        "private_heldout_solve_rate",
        "patch_apply_rate",
        "visible_test_pass_rate",
        "hidden_test_pass_rate",
        "repair_success_rate",
        "wrong_file_rate",
        "cost_per_solved_task",
        "latency_per_solved_task",
        "trajectory_efficiency",
        "regression_rate"
    ]
}


MILESTONES: list[dict[str, Any]] = [
    {
        "step": "29.8",
        "name": "internal_synthetic_generator_design",
        "status": "this_step",
        "deliverable": "architecture, schemas, heldout protocol, ADR"
    },
    {
        "step": "29.9",
        "name": "task_schema_and_micro_generator_scaffold",
        "status": "next",
        "deliverable": "executable tiny repo task generator with one deterministic task family"
    },
    {
        "step": "29.10",
        "name": "oracle_and_hidden_test_gate",
        "status": "planned",
        "deliverable": "pre/post oracle runner and hidden-test contract"
    },
    {
        "step": "29.11",
        "name": "trajectory_recorder_v1",
        "status": "planned",
        "deliverable": "event schema and trajectory export from local agentic runs"
    },
    {
        "step": "29.12",
        "name": "private_heldout_seed_set",
        "status": "planned",
        "deliverable": "small isolated heldout set with strict no-train policy"
    },
    {
        "step": "30",
        "name": "training_grade_tokenization_or_tiny_training_only_after_gates",
        "status": "blocked",
        "deliverable": "only allowed after data gates and explicit approval"
    }
]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def append_once(path: Path, marker: str, text: str) -> None:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in current:
        path.write_text(current.rstrip() + "\n\n" + text.strip() + "\n", encoding="utf-8")


def build_generator_doc(design: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Internal Synthetic Executable Task Generator v0")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("This generator is the core internal data engine for ForgeMoE.")
    lines.append("It is designed to create executable repository-level tasks, agentic trajectories, negative patch records, preference pairs and private evaluation tasks.")
    lines.append("")
    lines.append("The goal is not to make toy rows. The goal is to produce training-grade data that can teach and evaluate autonomous software engineering behavior.")
    lines.append("")
    lines.append("## Modules")
    lines.append("")
    for module in GENERATOR_MODULES:
        lines.append("### " + module["module_id"])
        lines.append("")
        lines.append("- Purpose: " + module["purpose"])
        lines.append("- Inputs: " + ", ".join(module["inputs"]))
        lines.append("- Outputs: " + ", ".join(module["outputs"]))
        lines.append("- Blocks if missing: " + str(module["blocks_if_missing"]))
        lines.append("")
    lines.append("## Task families")
    lines.append("")
    for family in TASK_SCHEMA["task_families"]:
        lines.append("- " + family)
    lines.append("")
    lines.append("## Output dataset types")
    lines.append("")
    for output_type in design["output_dataset_types"]:
        lines.append("- " + output_type)
    lines.append("")
    lines.append("## Non-negotiable rules")
    lines.append("")
    for rule in design["non_negotiable_rules"]:
        lines.append("- " + rule)
    return "\n".join(lines)


def build_heldout_doc(protocol: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Private Heldout Protocol v0")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(protocol["purpose"])
    lines.append("")
    lines.append("## Rules")
    lines.append("")
    for rule in protocol["rules"]:
        lines.append("- " + rule)
    lines.append("")
    lines.append("## Task requirements")
    lines.append("")
    for req in protocol["task_requirements"]:
        lines.append("- " + req)
    lines.append("")
    lines.append("## Promotion metrics")
    lines.append("")
    for metric in protocol["promotion_metrics"]:
        lines.append("- " + metric)
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append("Private heldout tasks are not training data. They are a promotion gate.")
    lines.append("Any model claim that ignores private heldout results is incomplete.")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    source_gate = json.loads(
        (PROJECT_ROOT / "results/local/dataset_source_matrix_gate_v0/dataset_acquisition_gate_report.json").read_text(encoding="utf-8")
    )

    design = {
        "schema_version": "forgeagent.internal_synthetic_task_generator_design.v0",
        "design_name": "internal_synthetic_executable_task_generator_v0",
        "parent_gate": "dataset_source_matrix_gate_v0",
        "source_gate_training_launch_allowed": source_gate["training_launch_allowed"],
        "source_gate_large_dataset_download_allowed": source_gate["large_dataset_download_allowed"],
        "generator_modules": GENERATOR_MODULES,
        "task_schema": TASK_SCHEMA,
        "trajectory_schema": TRAJECTORY_SCHEMA,
        "private_heldout_protocol": PRIVATE_HELDOUT_PROTOCOL,
        "output_dataset_types": [
            "patch_sft_rows",
            "structured_intent_rows",
            "trajectory_sft_rows",
            "preference_pairs",
            "verifier_training_rows",
            "private_eval_tasks"
        ],
        "non_negotiable_rules": [
            "every_training_grade_task_must_have_an_execution_oracle",
            "private_heldout_is_never_training_data",
            "every_task_requires_provenance",
            "every_task_requires_contamination_scan",
            "failed_patches_are_preserved_as_negative_signal",
            "train_eval_holdout_splits_must_be_isolated",
            "training_launch_requires_explicit_approval",
            "large_external_dataset_downloads_remain_blocked"
        ],
        "milestones": MILESTONES,
        "launches_training_job": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_9_task_schema_and_micro_generator_scaffold"
    }

    risk_register = {
        "schema_version": "forgeagent.synthetic_data_engine_risk_register.v0",
        "risks": [
            {
                "risk_id": "template_overfit",
                "severity": "high",
                "description": "Synthetic tasks may become repetitive and teach template matching instead of reasoning.",
                "mitigation": "difficulty diversity, repo diversity, hidden tests, mutation family diversity and eval isolation"
            },
            {
                "risk_id": "weak_oracle",
                "severity": "critical",
                "description": "Tasks with weak tests can reward incorrect patches.",
                "mitigation": "hidden tests, oracle strength score and post-hoc verifier checks"
            },
            {
                "risk_id": "contamination",
                "severity": "critical",
                "description": "Generated tasks may overlap with public benchmark or train data.",
                "mitigation": "dedup signatures, benchmark overlap scans and private heldout isolation"
            },
            {
                "risk_id": "license_violation",
                "severity": "critical",
                "description": "Seed repositories may have incompatible terms or licenses.",
                "mitigation": "repo license gate before snapshotting and provenance manifests"
            },
            {
                "risk_id": "trajectory_secret_leak",
                "severity": "high",
                "description": "Tool traces may capture secrets or private content.",
                "mitigation": "privacy scan and secret scan before trajectory export"
            },
            {
                "risk_id": "reward_hacking",
                "severity": "high",
                "description": "RL or verifier optimization may learn to exploit tests.",
                "mitigation": "hidden tests, regression tests, private heldout and adversarial negatives"
            }
        ]
    }

    write_json(OUT_DIR / "generator_design.json", design)
    write_json(OUT_DIR / "synthetic_task_schema_v0.json", TASK_SCHEMA)
    write_json(OUT_DIR / "agentic_trajectory_schema_v0.json", TRAJECTORY_SCHEMA)
    write_json(OUT_DIR / "private_heldout_protocol_v0.json", PRIVATE_HELDOUT_PROTOCOL)
    write_json(OUT_DIR / "synthetic_data_engine_risk_register.json", risk_register)

    write_text(PROJECT_ROOT / "docs/data/INTERNAL_SYNTHETIC_EXECUTABLE_TASK_GENERATOR.md", build_generator_doc(design))
    write_text(PROJECT_ROOT / "docs/data/PRIVATE_HELDOUT_PROTOCOL.md", build_heldout_doc(PRIVATE_HELDOUT_PROTOCOL))

    adr = """
# ADR-0034 - Internal Synthetic Executable Task Generator and Private Heldout Protocol

Status: Accepted
Date: 2026-05-17

## Context

Step 29.7 classified external data sources and confirmed that training remains blocked.

The highest-priority path is now internal data generation: executable repository-level tasks, agentic trajectories, negative examples, preference pairs and private heldout evaluation.

## Decision

Design the Forge internal synthetic executable task generator as a first-class data engine.

The generator must include seed repository governance, immutable snapshots, controlled task mutation, executable oracles, hidden tests, difficulty scoring, patch verification, negative patch mining, trajectory recording, contamination scans, provenance manifests and split isolation.

Private heldout tasks are never training data. They are a promotion gate for north-star claims.

## Consequence

Step 30 remains blocked.

The next implementation step is a small deterministic micro-generator that creates one executable repo-level task family end to end.
"""
    write_text(PROJECT_ROOT / "docs/engineering/ADR_0034_INTERNAL_SYNTHETIC_GENERATOR_AND_HELDOUT.md", adr)

    append_once(
        PROJECT_ROOT / "docs/engineering/ENGINEERING_DECISION_RECORD.md",
        "## Update - Step 29.8 Internal Synthetic Generator and Heldout Design",
        """
---

## Update - Step 29.8 Internal Synthetic Generator and Heldout Design

Step 29.8 designed the internal synthetic executable task generator and private heldout protocol.

The central decision is that ForgeMoE needs its own data engine for executable repository-level tasks, trajectories, negative patch records, preference pairs and private heldout tasks.

Step 30 remains blocked until generator, oracle, hidden-test, contamination and split-isolation gates exist.
""",
    )

    append_once(
        PROJECT_ROOT / "docs/engineering/PROJECT_RECAP_AND_ROADMAP.md",
        "## Step 29.8 Recap - Internal Synthetic Generator and Private Heldout",
        """
---

## Step 29.8 Recap - Internal Synthetic Generator and Private Heldout

The project now has a formal design for the internal data engine.

Current state:

- External datasets remain gated.
- Public benchmarks remain reference or evaluation sources by default.
- Internal executable task generation is the critical path.
- Private heldout eval is now a formal promotion boundary.
- Step 30 training remains blocked.

Recommended next step:

Step 29.9 - Task schema and deterministic micro-generator scaffold.
""",
    )

    print(json.dumps(
        {
            "schema_version": design["schema_version"],
            "generator_module_count": len(GENERATOR_MODULES),
            "task_family_count": len(TASK_SCHEMA["task_families"]),
            "trajectory_event_type_count": len(TRAJECTORY_SCHEMA["event_types"]),
            "private_heldout_metric_count": len(PRIVATE_HELDOUT_PROTOCOL["promotion_metrics"]),
            "risk_count": len(risk_register["risks"]),
            "launches_training_job": design["launches_training_job"],
            "downloads_large_dataset": design["downloads_large_dataset"],
            "gpu_required": design["gpu_required"],
            "next_recommended_step": design["next_recommended_step"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print("INTERNAL_SYNTHETIC_GENERATOR_DESIGN_OK")


if __name__ == "__main__":
    main()

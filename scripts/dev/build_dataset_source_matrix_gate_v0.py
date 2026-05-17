from __future__ import annotations

from pathlib import Path
import json
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "results/local/dataset_source_matrix_gate_v0"


SOURCE_ROWS: list[dict[str, Any]] = [
    {
        "source_id": "the_stack_v2",
        "source_name": "The Stack v2",
        "source_class": "large_code_corpus",
        "owner_or_project": "BigCode and Software Heritage ecosystem",
        "primary_role": "continued_pretraining_candidate",
        "secondary_roles": ["language_balance_analysis", "license_provenance_reference"],
        "training_phase_fit": ["continued_pretraining", "domain_adaptation"],
        "recommended_decision": "block_ingestion_pending_review",
        "priority": "high_but_blocked",
        "why_relevant": "Large-scale code corpus with provenance fields and language coverage suitable as a pretraining candidate after strict review.",
        "blocking_gates": [
            "terms_and_access_review",
            "bulk_download_agreement_review",
            "license_policy_review",
            "provenance_field_validation",
            "pii_secret_filter_plan",
            "malware_filter_plan",
            "deduplication_plan",
            "benchmark_contamination_plan"
        ],
        "non_negotiable_constraints": [
            "do_not_bulk_download_without_access_terms_review",
            "do_not_train_without_license_policy",
            "do_not_mix_into_eval_holdout",
            "preserve_provenance_per_file"
        ],
        "status": "candidate_blocked_pending_review"
    },
    {
        "source_id": "the_stack_v2_dedup_or_train_ids",
        "source_name": "The Stack v2 dedup or train id subsets",
        "source_class": "large_code_corpus_filtered_subset",
        "owner_or_project": "BigCode and Software Heritage ecosystem",
        "primary_role": "filtered_pretraining_candidate",
        "secondary_roles": ["repo_context_pretraining_candidate"],
        "training_phase_fit": ["continued_pretraining", "domain_adaptation"],
        "recommended_decision": "block_ingestion_pending_review",
        "priority": "high_but_blocked",
        "why_relevant": "Potentially more suitable than raw full corpus because it already reflects deduplication and training subset concepts.",
        "blocking_gates": [
            "same_terms_as_parent_dataset",
            "subset_definition_review",
            "license_distribution_report",
            "near_duplicate_leakage_review",
            "repo_grouping_policy"
        ],
        "non_negotiable_constraints": [
            "do_not_treat_dedup_as_sufficient",
            "do_not_assume_license_safety_from_subset_name",
            "verify_actual_available_files_and_ids"
        ],
        "status": "candidate_blocked_pending_review"
    },
    {
        "source_id": "swe_bench_verified",
        "source_name": "SWE-bench Verified",
        "source_class": "repo_level_eval_benchmark",
        "owner_or_project": "SWE-bench",
        "primary_role": "evaluation_reference",
        "secondary_roles": ["difficulty_calibration", "agentic_metric_reference"],
        "training_phase_fit": ["evaluation_only", "calibration_only"],
        "recommended_decision": "allow_reference_only",
        "priority": "high_reference",
        "why_relevant": "Human-filtered repository-level benchmark useful for measuring agentic patching behavior.",
        "blocking_gates": [
            "do_not_train_on_eval_instances",
            "contamination_boundary_record",
            "benchmark_snapshot_versioning",
            "public_private_eval_split_policy"
        ],
        "non_negotiable_constraints": [
            "reference_only_until_contamination_policy_is_implemented",
            "never_mix_verified_eval_into_training_without_explicit_ablation_boundary",
            "track_model_exposure_to_public_instances"
        ],
        "status": "approved_for_reference_only"
    },
    {
        "source_id": "swe_bench_full_lite_multilingual_multimodal",
        "source_name": "SWE-bench family",
        "source_class": "repo_level_eval_family",
        "owner_or_project": "SWE-bench",
        "primary_role": "evaluation_reference",
        "secondary_roles": ["multilingual_repo_task_reference", "visual_issue_reference", "cost_reduced_eval_reference"],
        "training_phase_fit": ["evaluation_only", "benchmark_design_reference"],
        "recommended_decision": "allow_reference_only",
        "priority": "high_reference",
        "why_relevant": "Useful to define repository-level evaluation dimensions, cost profiles, language breadth and visual issue variants.",
        "blocking_gates": [
            "benchmark_snapshot_versioning",
            "contamination_policy",
            "heldout_policy",
            "task_license_review"
        ],
        "non_negotiable_constraints": [
            "public_benchmark_is_not_training_corpus",
            "avoid_leaderboard_overfitting"
        ],
        "status": "approved_for_reference_only"
    },
    {
        "source_id": "swe_smith",
        "source_name": "SWE-smith",
        "source_class": "synthetic_repo_task_generation_methodology",
        "owner_or_project": "SWE-bench ecosystem",
        "primary_role": "methodology_reference",
        "secondary_roles": ["synthetic_executable_task_generation", "agentic_training_data_reference"],
        "training_phase_fit": ["synthetic_task_generation", "trajectory_generation", "patch_sft", "preference_pairs"],
        "recommended_decision": "allow_reference_only",
        "priority": "critical_methodology_reference",
        "why_relevant": "Directly aligned with ForgeMoE direction: generate many executable software-engineering tasks from repositories and train coding agents from them.",
        "blocking_gates": [
            "code_license_review_before_reuse",
            "implementation_reproduction_plan",
            "internal_generator_design",
            "generated_task_quality_gate",
            "anti_template_overfit_gate"
        ],
        "non_negotiable_constraints": [
            "do_not_copy_method_without_license_review",
            "build_forge_native_generator",
            "validate_generated_tasks_with_execution_oracle"
        ],
        "status": "candidate_external_methodology_reference"
    },
    {
        "source_id": "livecodebench",
        "source_name": "LiveCodeBench",
        "source_class": "contamination_aware_code_eval",
        "owner_or_project": "LiveCodeBench",
        "primary_role": "auxiliary_evaluation",
        "secondary_roles": ["date_based_contamination_analysis", "self_repair_eval_reference"],
        "training_phase_fit": ["evaluation_only", "contamination_method_reference"],
        "recommended_decision": "allow_reference_only",
        "priority": "medium_high_reference",
        "why_relevant": "Useful for time-based contamination discipline and broader code scenarios beyond pure generation.",
        "blocking_gates": [
            "public_eval_boundary",
            "timestamp_split_policy",
            "do_not_train_on_heldout_eval"
        ],
        "non_negotiable_constraints": [
            "reference_for_eval_design_not_primary_training_data",
            "preserve_release_date_metadata"
        ],
        "status": "approved_for_reference_only"
    },
    {
        "source_id": "bigcodebench",
        "source_name": "BigCodeBench",
        "source_class": "practical_code_generation_eval",
        "owner_or_project": "BigCodeBench",
        "primary_role": "auxiliary_evaluation",
        "secondary_roles": ["function_call_complexity_reference", "instruction_vs_completion_eval_reference"],
        "training_phase_fit": ["evaluation_only", "capability_diagnostics"],
        "recommended_decision": "allow_reference_only",
        "priority": "medium_reference",
        "why_relevant": "Useful for practical coding tasks involving diverse libraries and multi-call reasoning, but not enough for full repository-level agentic e2e.",
        "blocking_gates": [
            "contamination_policy",
            "public_eval_boundary",
            "benchmark_snapshot_versioning"
        ],
        "non_negotiable_constraints": [
            "do_not_optimize_only_for_bigcodebench",
            "treat_as_auxiliary_not_north_star"
        ],
        "status": "approved_for_reference_only"
    },
    {
        "source_id": "forge_synthetic_executable_tasks",
        "source_name": "Forge synthetic executable task generator",
        "source_class": "internal_synthetic_data_engine",
        "owner_or_project": "ForgeMoE",
        "primary_role": "primary_training_data_engine_candidate",
        "secondary_roles": ["patch_sft", "trajectory_sft", "preference_pairs", "verifiable_rl"],
        "training_phase_fit": ["synthetic_executable_tasks", "agentic_trajectories", "preference_optimization"],
        "recommended_decision": "allow_internal_build",
        "priority": "critical_immediate",
        "why_relevant": "This is the controllable path to training-grade agentic data without relying blindly on public benchmarks.",
        "blocking_gates": [
            "task_generator_design",
            "execution_oracle",
            "hidden_test_generation",
            "difficulty_curriculum",
            "anti_template_overfit",
            "repo_license_review_for_seed_repos"
        ],
        "non_negotiable_constraints": [
            "every_task_must_be_executable",
            "every_task_must_have_oracle",
            "store_failed_attempts_and_repairs",
            "separate_train_eval_holdout"
        ],
        "status": "candidate_internal_build"
    },
    {
        "source_id": "forge_agentic_trajectories",
        "source_name": "Forge agentic trajectories",
        "source_class": "internal_trajectory_dataset",
        "owner_or_project": "ForgeMoE",
        "primary_role": "trajectory_sft_and_preference_data",
        "secondary_roles": ["repair_learning", "tool_use_learning", "failure_mode_learning"],
        "training_phase_fit": ["trajectory_sft", "dpo_or_equivalent", "verifiable_rl"],
        "recommended_decision": "allow_internal_build",
        "priority": "critical_immediate",
        "why_relevant": "Agentic capability requires traces of inspect, plan, edit, test, failure, repair and final verification.",
        "blocking_gates": [
            "trajectory_schema_v1",
            "tool_trace_privacy_filter",
            "reward_attribution",
            "chosen_rejected_pair_extraction",
            "storage_format",
            "dedup_and_split_policy"
        ],
        "non_negotiable_constraints": [
            "do_not_store_secrets",
            "do_not_train_on_unverified_success",
            "preserve_failure_context",
            "version_every_trace"
        ],
        "status": "candidate_internal_build"
    },
    {
        "source_id": "forge_private_heldout_eval",
        "source_name": "Forge private heldout eval",
        "source_class": "internal_hidden_eval",
        "owner_or_project": "ForgeMoE",
        "primary_role": "north_star_eval_gate",
        "secondary_roles": ["contamination_control", "promotion_gate", "agentic_e2e_validation"],
        "training_phase_fit": ["evaluation_only"],
        "recommended_decision": "allow_internal_build",
        "priority": "critical_immediate",
        "why_relevant": "The project needs a private, frozen, uncontaminated evaluation suite that measures actual e2e software engineering capability.",
        "blocking_gates": [
            "holdout_isolation_protocol",
            "repo_selection_policy",
            "task_authoring_protocol",
            "hidden_test_strength",
            "no_train_overlap_verification",
            "evaluation_harness_versioning"
        ],
        "non_negotiable_constraints": [
            "never_train_on_private_holdout",
            "limit_access_and_version_snapshots",
            "store_oracle_and_expected_behavior_separately",
            "require_strong_tests"
        ],
        "status": "candidate_internal_build"
    },
    {
        "source_id": "unreviewed_web_or_random_github_scrapes",
        "source_name": "Unreviewed web or random GitHub scrapes",
        "source_class": "unsafe_unreviewed_data",
        "owner_or_project": "unknown",
        "primary_role": "none",
        "secondary_roles": [],
        "training_phase_fit": [],
        "recommended_decision": "block_training_use",
        "priority": "reject",
        "why_relevant": "Explicit rejection class to prevent accidental low-discipline ingestion.",
        "blocking_gates": [
            "unknown_license",
            "unknown_provenance",
            "unknown_pii_secret_risk",
            "unknown_malware_risk",
            "unknown_contamination"
        ],
        "non_negotiable_constraints": [
            "do_not_ingest",
            "do_not_train",
            "do_not_use_as_eval"
        ],
        "status": "rejected_for_training_until_further_notice"
    }
]


GATE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "gate_id": "legal_terms_gate",
        "purpose": "Verify dataset terms, access conditions and allowed use before acquisition.",
        "blocks": ["bulk_download", "training_use", "redistribution"],
        "required_artifacts": ["terms_review.md", "allowed_use_decision.json"]
    },
    {
        "gate_id": "license_gate",
        "purpose": "Verify source licenses and attribution obligations.",
        "blocks": ["training_use", "model_release_claims"],
        "required_artifacts": ["license_distribution.json", "license_policy_decision.md"]
    },
    {
        "gate_id": "provenance_gate",
        "purpose": "Preserve datapoint lineage sufficient for audit and removals.",
        "blocks": ["training_grade_label"],
        "required_artifacts": ["provenance_schema.json", "source_snapshot_manifest.json"]
    },
    {
        "gate_id": "pii_secret_security_gate",
        "purpose": "Remove or block secrets, PII and risky content before training.",
        "blocks": ["training_use"],
        "required_artifacts": ["secret_scan_report.json", "pii_scan_report.json"]
    },
    {
        "gate_id": "malware_gate",
        "purpose": "Reduce risk of training on malicious code patterns without labeling or policy.",
        "blocks": ["training_use"],
        "required_artifacts": ["malware_scan_policy.md", "risky_sample_report.json"]
    },
    {
        "gate_id": "deduplication_gate",
        "purpose": "Prevent near-duplicate leakage across train, eval and heldout.",
        "blocks": ["train_eval_split"],
        "required_artifacts": ["dedup_report.json", "similarity_thresholds.json"]
    },
    {
        "gate_id": "contamination_gate",
        "purpose": "Separate public benchmark material from training data.",
        "blocks": ["evaluation_claims", "model_promotion"],
        "required_artifacts": ["benchmark_overlap_report.json", "heldout_isolation_manifest.json"]
    },
    {
        "gate_id": "execution_oracle_gate",
        "purpose": "Require executable verification for repo-level tasks.",
        "blocks": ["patch_sft_training_grade", "trajectory_sft_training_grade"],
        "required_artifacts": ["task_oracle_manifest.json", "environment_repro_report.json"]
    },
    {
        "gate_id": "quality_scoring_gate",
        "purpose": "Score rows by utility, difficulty, correctness and agentic value.",
        "blocks": ["training_mixture_manifest"],
        "required_artifacts": ["quality_score_report.json", "row_filter_policy.md"]
    },
    {
        "gate_id": "split_and_holdout_gate",
        "purpose": "Create train, eval and private heldout splits with strict isolation.",
        "blocks": ["training_launch"],
        "required_artifacts": ["split_manifest.json", "private_holdout_manifest.json"]
    }
]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def append_once(path: Path, marker: str, text: str) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in original:
        path.write_text(original.rstrip() + "\n\n" + text.strip() + "\n", encoding="utf-8")


def build_markdown(matrix: dict[str, Any], gate_report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Dataset Source Matrix and Acquisition Gate v0")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("This document converts the Step 29.6 dataset strategy into an operational source matrix.")
    lines.append("The default decision is to block ingestion until legal, provenance, safety, deduplication and contamination gates pass.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Candidate sources: {matrix['source_count']}")
    lines.append(f"- Sources allowed for reference only: {gate_report['decision_counts'].get('allow_reference_only', 0)}")
    lines.append(f"- Internal build candidates: {gate_report['decision_counts'].get('allow_internal_build', 0)}")
    lines.append(f"- Blocked pending review: {gate_report['decision_counts'].get('block_ingestion_pending_review', 0)}")
    lines.append(f"- Blocked for training use: {gate_report['decision_counts'].get('block_training_use', 0)}")
    lines.append(f"- Launches training job: {matrix['launches_training_job']}")
    lines.append(f"- Downloads large dataset: {matrix['downloads_large_dataset']}")
    lines.append("")
    lines.append("## Source decisions")
    lines.append("")

    for row in matrix["sources"]:
        lines.append(f"### {row['source_id']}")
        lines.append("")
        lines.append(f"- Name: {row['source_name']}")
        lines.append(f"- Class: {row['source_class']}")
        lines.append(f"- Primary role: {row['primary_role']}")
        lines.append(f"- Status: {row['status']}")
        lines.append(f"- Recommended decision: {row['recommended_decision']}")
        lines.append(f"- Priority: {row['priority']}")
        lines.append(f"- Why relevant: {row['why_relevant']}")
        lines.append(f"- Blocking gates: {', '.join(row['blocking_gates'])}")
        lines.append(f"- Non-negotiable constraints: {', '.join(row['non_negotiable_constraints'])}")
        lines.append("")

    lines.append("## Gate definitions")
    lines.append("")

    for gate in GATE_DEFINITIONS:
        lines.append(f"### {gate['gate_id']}")
        lines.append("")
        lines.append(f"- Purpose: {gate['purpose']}")
        lines.append(f"- Blocks: {', '.join(gate['blocks'])}")
        lines.append(f"- Required artifacts: {', '.join(gate['required_artifacts'])}")
        lines.append("")

    lines.append("## Next decision")
    lines.append("")
    lines.append("Build the internal Forge synthetic executable task generator and private heldout protocol before any serious training-grade GPU run.")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    governance = json.loads(
        (PROJECT_ROOT / "results/local/sota_dataset_strategy_v0/dataset_governance_plan.json").read_text(encoding="utf-8")
    )

    decision_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    training_phase_counts: dict[str, int] = {}

    for row in SOURCE_ROWS:
        decision_counts[row["recommended_decision"]] = decision_counts.get(row["recommended_decision"], 0) + 1
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        for phase in row["training_phase_fit"]:
            training_phase_counts[phase] = training_phase_counts.get(phase, 0) + 1

    matrix = {
        "schema_version": "forgeagent.dataset_source_matrix_gate.v0",
        "matrix_name": "dataset_source_matrix_gate_v0",
        "parent_governance_plan": governance["plan_name"],
        "source_count": len(SOURCE_ROWS),
        "gate_count": len(GATE_DEFINITIONS),
        "sources": SOURCE_ROWS,
        "gate_definitions": GATE_DEFINITIONS,
        "decision_counts": decision_counts,
        "status_counts": status_counts,
        "training_phase_counts": training_phase_counts,
        "launches_training_job": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "requires_explicit_approval_before_training": True,
        "next_recommended_step": "step29_8_internal_synthetic_task_generator_design",
    }

    gate_report = {
        "schema_version": "forgeagent.dataset_acquisition_gate_report.v0",
        "matrix_name": matrix["matrix_name"],
        "source_count": matrix["source_count"],
        "gate_count": matrix["gate_count"],
        "decision_counts": decision_counts,
        "status_counts": status_counts,
        "training_phase_counts": training_phase_counts,
        "blocked_before_ingestion": [
            row["source_id"]
            for row in SOURCE_ROWS
            if row["recommended_decision"] in {"block_ingestion_pending_review", "block_training_use"}
        ],
        "internal_build_candidates": [
            row["source_id"]
            for row in SOURCE_ROWS
            if row["recommended_decision"] == "allow_internal_build"
        ],
        "reference_only_sources": [
            row["source_id"]
            for row in SOURCE_ROWS
            if row["recommended_decision"] == "allow_reference_only"
        ],
        "training_launch_allowed": False,
        "large_dataset_download_allowed": False,
        "reason_training_launch_blocked": "No source is yet promoted to training-grade. Legal, provenance, quality, contamination and holdout gates are still pending.",
        "next_recommended_step": matrix["next_recommended_step"],
    }

    write_json(OUT_DIR / "dataset_source_matrix_gate.json", matrix)
    write_json(OUT_DIR / "dataset_acquisition_gate_report.json", gate_report)
    write_text(PROJECT_ROOT / "docs/data/DATASET_SOURCE_MATRIX_AND_ACQUISITION_GATE.md", build_markdown(matrix, gate_report))

    adr = """
# ADR-0033 - Dataset Source Matrix and Acquisition Gate

Status: Accepted
Date: 2026-05-15

## Context

Step 29.6 established that the current synthetic datasets are scaffold data, not final training-grade data.

The next engineering requirement is to convert dataset strategy into an operational acquisition gate.

## Decision

Create a dataset source matrix with explicit source roles, allowed uses, blocking gates and acquisition decisions.

Public benchmarks are reference and evaluation sources by default, not ordinary training corpora.

Large code corpora are blocked from ingestion until terms, license, provenance, safety, deduplication and contamination gates pass.

Forge internal synthetic executable tasks, agentic trajectories and private heldout eval are promoted as critical internal build targets.

## Consequence

Step 30 training remains blocked.

The next technical direction is to build internal task generation and heldout infrastructure rather than ingest arbitrary public data.
"""
    write_text(PROJECT_ROOT / "docs/engineering/ADR_0033_DATASET_SOURCE_MATRIX_AND_ACQUISITION_GATE.md", adr)

    append_once(
        PROJECT_ROOT / "docs/engineering/ENGINEERING_DECISION_RECORD.md",
        "## Update - Step 29.7 Dataset Source Matrix and Acquisition Gate",
        """
---

## Update - Step 29.7 Dataset Source Matrix and Acquisition Gate

Step 29.7 converted the SOTA dataset strategy into an operational source matrix.

The source matrix classifies candidate sources by role, training phase fit, decision status, blocking gates and non-negotiable constraints.

The key decision is that public benchmarks remain reference or evaluation sources by default, while serious training-grade data must come from gated code corpora, internal synthetic executable tasks, agentic trajectories and private heldout infrastructure.
""",
    )

    append_once(
        PROJECT_ROOT / "docs/engineering/PROJECT_RECAP_AND_ROADMAP.md",
        "## Step 29.7 Recap - Dataset Source Matrix and Acquisition Gate",
        """
---

## Step 29.7 Recap - Dataset Source Matrix and Acquisition Gate

The project now has an operational dataset source matrix.

Current state:

- Large code corpora are blocked pending legal, provenance, safety, deduplication and contamination review.
- SWE-bench family, LiveCodeBench and BigCodeBench are reference or evaluation sources, not default training data.
- SWE-smith is a critical methodology reference.
- Forge synthetic executable tasks, Forge agentic trajectories and Forge private heldout eval are critical internal build targets.
- Step 30 training remains blocked.

Recommended next step:

Step 29.8 - Internal synthetic executable task generator and private heldout protocol design.
""",
    )

    print(json.dumps(
        {
            "schema_version": matrix["schema_version"],
            "source_count": matrix["source_count"],
            "gate_count": matrix["gate_count"],
            "decision_counts": decision_counts,
            "status_counts": status_counts,
            "training_launch_allowed": gate_report["training_launch_allowed"],
            "large_dataset_download_allowed": gate_report["large_dataset_download_allowed"],
            "next_recommended_step": matrix["next_recommended_step"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print("DATASET_SOURCE_MATRIX_GATE_OK")


if __name__ == "__main__":
    main()

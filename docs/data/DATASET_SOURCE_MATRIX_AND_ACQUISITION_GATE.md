# Dataset Source Matrix and Acquisition Gate v0

## Purpose

This document converts the Step 29.6 dataset strategy into an operational source matrix.
The default decision is to block ingestion until legal, provenance, safety, deduplication and contamination gates pass.

## Summary

- Candidate sources: 11
- Sources allowed for reference only: 5
- Internal build candidates: 3
- Blocked pending review: 2
- Blocked for training use: 1
- Launches training job: False
- Downloads large dataset: False

## Source decisions

### the_stack_v2

- Name: The Stack v2
- Class: large_code_corpus
- Primary role: continued_pretraining_candidate
- Status: candidate_blocked_pending_review
- Recommended decision: block_ingestion_pending_review
- Priority: high_but_blocked
- Why relevant: Large-scale code corpus with provenance fields and language coverage suitable as a pretraining candidate after strict review.
- Blocking gates: terms_and_access_review, bulk_download_agreement_review, license_policy_review, provenance_field_validation, pii_secret_filter_plan, malware_filter_plan, deduplication_plan, benchmark_contamination_plan
- Non-negotiable constraints: do_not_bulk_download_without_access_terms_review, do_not_train_without_license_policy, do_not_mix_into_eval_holdout, preserve_provenance_per_file

### the_stack_v2_dedup_or_train_ids

- Name: The Stack v2 dedup or train id subsets
- Class: large_code_corpus_filtered_subset
- Primary role: filtered_pretraining_candidate
- Status: candidate_blocked_pending_review
- Recommended decision: block_ingestion_pending_review
- Priority: high_but_blocked
- Why relevant: Potentially more suitable than raw full corpus because it already reflects deduplication and training subset concepts.
- Blocking gates: same_terms_as_parent_dataset, subset_definition_review, license_distribution_report, near_duplicate_leakage_review, repo_grouping_policy
- Non-negotiable constraints: do_not_treat_dedup_as_sufficient, do_not_assume_license_safety_from_subset_name, verify_actual_available_files_and_ids

### swe_bench_verified

- Name: SWE-bench Verified
- Class: repo_level_eval_benchmark
- Primary role: evaluation_reference
- Status: approved_for_reference_only
- Recommended decision: allow_reference_only
- Priority: high_reference
- Why relevant: Human-filtered repository-level benchmark useful for measuring agentic patching behavior.
- Blocking gates: do_not_train_on_eval_instances, contamination_boundary_record, benchmark_snapshot_versioning, public_private_eval_split_policy
- Non-negotiable constraints: reference_only_until_contamination_policy_is_implemented, never_mix_verified_eval_into_training_without_explicit_ablation_boundary, track_model_exposure_to_public_instances

### swe_bench_full_lite_multilingual_multimodal

- Name: SWE-bench family
- Class: repo_level_eval_family
- Primary role: evaluation_reference
- Status: approved_for_reference_only
- Recommended decision: allow_reference_only
- Priority: high_reference
- Why relevant: Useful to define repository-level evaluation dimensions, cost profiles, language breadth and visual issue variants.
- Blocking gates: benchmark_snapshot_versioning, contamination_policy, heldout_policy, task_license_review
- Non-negotiable constraints: public_benchmark_is_not_training_corpus, avoid_leaderboard_overfitting

### swe_smith

- Name: SWE-smith
- Class: synthetic_repo_task_generation_methodology
- Primary role: methodology_reference
- Status: candidate_external_methodology_reference
- Recommended decision: allow_reference_only
- Priority: critical_methodology_reference
- Why relevant: Directly aligned with ForgeMoE direction: generate many executable software-engineering tasks from repositories and train coding agents from them.
- Blocking gates: code_license_review_before_reuse, implementation_reproduction_plan, internal_generator_design, generated_task_quality_gate, anti_template_overfit_gate
- Non-negotiable constraints: do_not_copy_method_without_license_review, build_forge_native_generator, validate_generated_tasks_with_execution_oracle

### livecodebench

- Name: LiveCodeBench
- Class: contamination_aware_code_eval
- Primary role: auxiliary_evaluation
- Status: approved_for_reference_only
- Recommended decision: allow_reference_only
- Priority: medium_high_reference
- Why relevant: Useful for time-based contamination discipline and broader code scenarios beyond pure generation.
- Blocking gates: public_eval_boundary, timestamp_split_policy, do_not_train_on_heldout_eval
- Non-negotiable constraints: reference_for_eval_design_not_primary_training_data, preserve_release_date_metadata

### bigcodebench

- Name: BigCodeBench
- Class: practical_code_generation_eval
- Primary role: auxiliary_evaluation
- Status: approved_for_reference_only
- Recommended decision: allow_reference_only
- Priority: medium_reference
- Why relevant: Useful for practical coding tasks involving diverse libraries and multi-call reasoning, but not enough for full repository-level agentic e2e.
- Blocking gates: contamination_policy, public_eval_boundary, benchmark_snapshot_versioning
- Non-negotiable constraints: do_not_optimize_only_for_bigcodebench, treat_as_auxiliary_not_north_star

### forge_synthetic_executable_tasks

- Name: Forge synthetic executable task generator
- Class: internal_synthetic_data_engine
- Primary role: primary_training_data_engine_candidate
- Status: candidate_internal_build
- Recommended decision: allow_internal_build
- Priority: critical_immediate
- Why relevant: This is the controllable path to training-grade agentic data without relying blindly on public benchmarks.
- Blocking gates: task_generator_design, execution_oracle, hidden_test_generation, difficulty_curriculum, anti_template_overfit, repo_license_review_for_seed_repos
- Non-negotiable constraints: every_task_must_be_executable, every_task_must_have_oracle, store_failed_attempts_and_repairs, separate_train_eval_holdout

### forge_agentic_trajectories

- Name: Forge agentic trajectories
- Class: internal_trajectory_dataset
- Primary role: trajectory_sft_and_preference_data
- Status: candidate_internal_build
- Recommended decision: allow_internal_build
- Priority: critical_immediate
- Why relevant: Agentic capability requires traces of inspect, plan, edit, test, failure, repair and final verification.
- Blocking gates: trajectory_schema_v1, tool_trace_privacy_filter, reward_attribution, chosen_rejected_pair_extraction, storage_format, dedup_and_split_policy
- Non-negotiable constraints: do_not_store_secrets, do_not_train_on_unverified_success, preserve_failure_context, version_every_trace

### forge_private_heldout_eval

- Name: Forge private heldout eval
- Class: internal_hidden_eval
- Primary role: north_star_eval_gate
- Status: candidate_internal_build
- Recommended decision: allow_internal_build
- Priority: critical_immediate
- Why relevant: The project needs a private, frozen, uncontaminated evaluation suite that measures actual e2e software engineering capability.
- Blocking gates: holdout_isolation_protocol, repo_selection_policy, task_authoring_protocol, hidden_test_strength, no_train_overlap_verification, evaluation_harness_versioning
- Non-negotiable constraints: never_train_on_private_holdout, limit_access_and_version_snapshots, store_oracle_and_expected_behavior_separately, require_strong_tests

### unreviewed_web_or_random_github_scrapes

- Name: Unreviewed web or random GitHub scrapes
- Class: unsafe_unreviewed_data
- Primary role: none
- Status: rejected_for_training_until_further_notice
- Recommended decision: block_training_use
- Priority: reject
- Why relevant: Explicit rejection class to prevent accidental low-discipline ingestion.
- Blocking gates: unknown_license, unknown_provenance, unknown_pii_secret_risk, unknown_malware_risk, unknown_contamination
- Non-negotiable constraints: do_not_ingest, do_not_train, do_not_use_as_eval

## Gate definitions

### legal_terms_gate

- Purpose: Verify dataset terms, access conditions and allowed use before acquisition.
- Blocks: bulk_download, training_use, redistribution
- Required artifacts: terms_review.md, allowed_use_decision.json

### license_gate

- Purpose: Verify source licenses and attribution obligations.
- Blocks: training_use, model_release_claims
- Required artifacts: license_distribution.json, license_policy_decision.md

### provenance_gate

- Purpose: Preserve datapoint lineage sufficient for audit and removals.
- Blocks: training_grade_label
- Required artifacts: provenance_schema.json, source_snapshot_manifest.json

### pii_secret_security_gate

- Purpose: Remove or block secrets, PII and risky content before training.
- Blocks: training_use
- Required artifacts: secret_scan_report.json, pii_scan_report.json

### malware_gate

- Purpose: Reduce risk of training on malicious code patterns without labeling or policy.
- Blocks: training_use
- Required artifacts: malware_scan_policy.md, risky_sample_report.json

### deduplication_gate

- Purpose: Prevent near-duplicate leakage across train, eval and heldout.
- Blocks: train_eval_split
- Required artifacts: dedup_report.json, similarity_thresholds.json

### contamination_gate

- Purpose: Separate public benchmark material from training data.
- Blocks: evaluation_claims, model_promotion
- Required artifacts: benchmark_overlap_report.json, heldout_isolation_manifest.json

### execution_oracle_gate

- Purpose: Require executable verification for repo-level tasks.
- Blocks: patch_sft_training_grade, trajectory_sft_training_grade
- Required artifacts: task_oracle_manifest.json, environment_repro_report.json

### quality_scoring_gate

- Purpose: Score rows by utility, difficulty, correctness and agentic value.
- Blocks: training_mixture_manifest
- Required artifacts: quality_score_report.json, row_filter_policy.md

### split_and_holdout_gate

- Purpose: Create train, eval and private heldout splits with strict isolation.
- Blocks: training_launch
- Required artifacts: split_manifest.json, private_holdout_manifest.json

## Next decision

Build the internal Forge synthetic executable task generator and private heldout protocol before any serious training-grade GPU run.

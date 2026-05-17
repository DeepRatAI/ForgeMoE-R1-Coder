# Internal Synthetic Executable Task Generator v0

## Purpose

This generator is the core internal data engine for ForgeMoE.
It is designed to create executable repository-level tasks, agentic trajectories, negative patch records, preference pairs and private evaluation tasks.

The goal is not to make toy rows. The goal is to produce training-grade data that can teach and evaluate autonomous software engineering behavior.

## Modules

### seed_repo_registry

- Purpose: Track candidate seed repositories and their legal/provenance status.
- Inputs: repo_url, commit_sha, license_metadata, language_metadata
- Outputs: seed_repo_manifest
- Blocks if missing: True

### repo_snapshotter

- Purpose: Create immutable repository snapshots for reproducible task generation.
- Inputs: seed_repo_manifest
- Outputs: repo_snapshot_manifest, source_archive_ref
- Blocks if missing: True

### task_mutation_engine

- Purpose: Create controlled bugs, feature gaps, migrations, refactors and config issues.
- Inputs: repo_snapshot_manifest, task_family_config
- Outputs: candidate_task_spec
- Blocks if missing: True

### oracle_builder

- Purpose: Build executable pre/post oracle commands and expected behavior checks.
- Inputs: candidate_task_spec
- Outputs: oracle_manifest
- Blocks if missing: True

### hidden_test_builder

- Purpose: Generate hidden tests that reduce shallow patch overfitting.
- Inputs: candidate_task_spec, oracle_manifest
- Outputs: hidden_test_manifest
- Blocks if missing: True

### difficulty_estimator

- Purpose: Score task difficulty, edit locality, file span and semantic depth.
- Inputs: candidate_task_spec, oracle_manifest
- Outputs: difficulty_report
- Blocks if missing: False

### patch_verifier

- Purpose: Verify that candidate patches apply and solve executable tests.
- Inputs: candidate_patch, oracle_manifest, hidden_test_manifest
- Outputs: patch_verification_result
- Blocks if missing: True

### negative_patch_miner

- Purpose: Preserve wrong-file, non-applying, overbroad and test-failing patches as training signal.
- Inputs: patch_verification_result, model_response
- Outputs: negative_patch_record
- Blocks if missing: False

### trajectory_recorder

- Purpose: Record inspect-plan-edit-test-repair trajectories for agentic SFT and preference learning.
- Inputs: tool_events, patch_attempts, oracle_results
- Outputs: agentic_trajectory_record
- Blocks if missing: True

### split_and_holdout_allocator

- Purpose: Assign generated artifacts to train, eval or private heldout with strict isolation.
- Inputs: task_spec, repo_snapshot_manifest, dedup_signature
- Outputs: split_assignment
- Blocks if missing: True

### contamination_scanner

- Purpose: Detect overlap with public benchmarks, previous train data and private holdout.
- Inputs: task_spec, patch_text, repo_snapshot_manifest
- Outputs: contamination_report
- Blocks if missing: True

### provenance_manifest_writer

- Purpose: Persist lineage for every task, patch, trajectory and split assignment.
- Inputs: all_generation_artifacts
- Outputs: provenance_manifest
- Blocks if missing: True

### quality_scorer

- Purpose: Score utility, correctness, difficulty, agentic value and risk.
- Inputs: task_spec, oracle_result, trajectory_record
- Outputs: quality_score_report
- Blocks if missing: True

## Task families

- single_file_bugfix
- multi_file_bugfix
- regression_test_creation
- api_migration
- refactor_with_behavior_preservation
- dependency_upgrade
- typing_or_static_analysis_repair
- security_hardening
- performance_micro_optimization
- configuration_or_packaging_fix
- integration_edge_case_fix
- fullstack_vertical_slice_change

## Output dataset types

- patch_sft_rows
- structured_intent_rows
- trajectory_sft_rows
- preference_pairs
- verifier_training_rows
- private_eval_tasks

## Non-negotiable rules

- every_training_grade_task_must_have_an_execution_oracle
- private_heldout_is_never_training_data
- every_task_requires_provenance
- every_task_requires_contamination_scan
- failed_patches_are_preserved_as_negative_signal
- train_eval_holdout_splits_must_be_isolated
- training_launch_requires_explicit_approval
- large_external_dataset_downloads_remain_blocked

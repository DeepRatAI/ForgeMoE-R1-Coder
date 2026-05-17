# Private Heldout Protocol v0

## Purpose

Provide contamination-resistant north-star evaluation for autonomous e2e coding agents.

## Rules

- private_heldout_tasks_are_never_used_for_training
- private_heldout_expected_patches_are_not_stored_in_training_paths
- private_heldout_repos_are_snapshot_versioned
- access_is_restricted
- public_benchmark_overlap_is_scanned
- train_eval_holdout_near_duplicate_scan_is_required
- promotion_claims_require_private_heldout_results

## Task requirements

- reproducible_environment
- strong_oracle
- hidden_tests
- clear_instruction
- expected_behavior
- difficulty_label
- provenance_manifest
- contamination_report

## Promotion metrics

- private_heldout_solve_rate
- patch_apply_rate
- visible_test_pass_rate
- hidden_test_pass_rate
- repair_success_rate
- wrong_file_rate
- cost_per_solved_task
- latency_per_solved_task
- trajectory_efficiency
- regression_rate

## Boundary

Private heldout tasks are not training data. They are a promotion gate.
Any model claim that ignores private heldout results is incomplete.

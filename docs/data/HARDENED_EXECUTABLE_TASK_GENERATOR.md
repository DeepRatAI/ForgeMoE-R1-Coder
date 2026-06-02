# Hardened Executable Task Generator

Step 29.31 turns the Step 29.30 hardened blueprints into executable temporary-repository tasks.

The generator is deterministic and model-free. Each task is created in a real Git repository, emits patches with `git diff`, validates candidate patches with `git apply --check` and requires public tests to fail before the patch and public plus hidden tests to pass after the golden patch.

## Current Result

```text
STEP29_31_DOCTOR_OK
task_count = 12
verified_task_count = 12
split_counts = {"train": 4, "eval": 3, "private_heldout": 3, "public_eval": 2}
multi_file_task_count = 12
challenge_result_count = 60
patch_build_temp_git_repo_count = 60
verification_temp_git_repo_count = 60
pre_public_fail_count = 12
git_apply_check_pass_count = 12
post_public_pass_count = 12
post_hidden_pass_count = 12
rejected_patch_fail_count = 12
public_overfit_hidden_catch_count = 12
wrong_file_negative_fail_count = 12
semantic_noop_negative_fail_count = 12
training_grade_candidate_count = 0
training_grade_data_release_allowed = false
training_launch_allowed = false
model_release_allowed = false
local_model_execution_used = false
remote_inference_invoked = false
```

## Verification Contract

Every task has five verified patches:

- `golden`: applies, fixes the public failure and passes hidden tests;
- `rejected`: applies but does not solve the task;
- `public_overfit`: passes public tests but fails hidden tests;
- `wrong_file`: applies but edits outside the expected behavioral scope and does not solve the task;
- `semantic_noop`: applies inside code but preserves the failing behavior.

The golden patch for every task edits two files: `app/service.py` and `app/policy.py`.

## Release State

The generated tasks are stronger than the toy scaffolds, but they are still not training-grade data. Release remains blocked until:

- public benchmark corpus scanning is complete;
- license policy is upgraded from scaffold-only;
- Step 29.31 tasks receive integrated oracle-quality certification;
- final training-grade release policy is implemented.

## Artifacts

```text
results/local/hardened_executable_task_generator_v1/summary.json
results/local/hardened_executable_task_generator_v1/task_results.jsonl
results/local/hardened_executable_task_generator_v1/patch_challenge_results.jsonl
results/local/hardened_executable_task_generator_v1/dataset_exports/hardened_executable_task_manifest.jsonl
results/local/hardened_executable_task_generator_v1/dataset_exports/patch_sft_train_scaffold_manifest.jsonl
results/local/hardened_executable_task_generator_v1/hardened_executable_task_generator_gate_decision.json
results/local/hardened_executable_task_generator_v1/public_safe_hardened_executable_task_generator_report.json
results/local/hardened_executable_task_generator_v1/hardened_executable_task_generator_privacy_report.json
results/local/hardened_executable_task_generator_v1/tasks/
```

## Public Safety Contract

The public-safe report excludes raw task IDs, raw rows, raw task text, patch content, hidden-test content, private identifier values and model outputs.

## Next Step

```text
Step 29.32 - hardened oracle quality and data release integration v1
```

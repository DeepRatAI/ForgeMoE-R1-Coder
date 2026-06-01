# Dedup and Near-Duplicate Scanner

Step 29.28 adds an executable deduplication and near-duplicate scanner for the current governed internal data scaffold.

The scanner consumes Step 29.27 provenance/license/contamination outputs and Step 29.25 row admission metadata. It computes hash-only row features, compares all governed rows pairwise, reports exact duplicate groups, near-duplicate groups, split collision counts and row-level dedup decisions.

This gate does not make rows training-grade. It proves that the near-duplicate scanner exists and runs, while keeping release blocked until task-family bundle isolation, public benchmark contamination scanning, license policy and oracle-quality certification are complete.

## Current Result

```text
STEP29_28_DOCTOR_OK
source_row_count = 10
training_row_count = 6
eval_row_count = 2
private_heldout_row_count = 2
pairwise_comparison_count = 45
exact_row_duplicate_group_count = 0
same_task_multi_product_group_count = 3
train_same_task_multi_product_group_count = 1
train_same_task_multi_product_row_count = 6
cross_split_high_near_duplicate_pair_count = 2
train_eval_high_near_duplicate_pair_count = 0
train_private_high_near_duplicate_pair_count = 0
near_duplicate_scanner_complete = true
split_isolation_high_similarity_passed = false
deduplication_passed = false
training_grade_dedup_pass_count = 0
training_grade_data_release_allowed = false
training_launch_allowed = false
model_release_allowed = false
local_model_execution_used = false
remote_inference_invoked = false
```

## Why The Gate Remains Closed

The scanner found same-task multi-product groups. This is expected for the current scaffold because one task can produce patch SFT, trajectory SFT, preference and repair-trace rows. That can eventually be valid, but only after the project defines task-family bundle IDs, sampler policies and split-isolation rules that prevent train/eval/private leakage at the task-family level.

The scanner also found high-similarity eval/private-heldout scaffold pairs. That does not expose private content in public reports, but it does mean current eval/private scaffold families are too toy-like and template-similar to support a serious private generalization claim without task-family isolation and harder generated tasks.

The scanner also keeps training blocked because public benchmark contamination scanning, license approval for training-grade use and oracle-quality certification are not yet integrated into the release gate.

## Artifacts

```text
results/local/dedup_near_duplicate_scanner_v1/summary.json
results/local/dedup_near_duplicate_scanner_v1/dedup_row_features.jsonl
results/local/dedup_near_duplicate_scanner_v1/pairwise_similarity_results.jsonl
results/local/dedup_near_duplicate_scanner_v1/dedup_row_decisions.jsonl
results/local/dedup_near_duplicate_scanner_v1/exact_duplicate_groups.json
results/local/dedup_near_duplicate_scanner_v1/near_duplicate_groups.json
results/local/dedup_near_duplicate_scanner_v1/split_collision_matrix.json
results/local/dedup_near_duplicate_scanner_v1/dedup_near_duplicate_gate_decision.json
results/local/dedup_near_duplicate_scanner_v1/public_safe_dedup_near_duplicate_report.json
results/local/dedup_near_duplicate_scanner_v1/dedup_near_duplicate_privacy_report.json
```

## Public Safety Contract

The public report contains counts and gate states only. It excludes raw rows, raw text, private identifier values, patch content, prompts, withheld-eval content and model outputs.

## Next Step

```text
Step 29.29 - task-family bundle isolation and oracle-quality certification
```

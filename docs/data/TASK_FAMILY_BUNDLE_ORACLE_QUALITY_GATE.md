# Task-Family Bundle and Oracle-Quality Gate

Step 29.29 adds an executable gate for task-family bundle isolation and row-level oracle-quality certification.

The gate consumes Step 29.28 dedup/near-duplicate outputs, Step 29.25 row governance metadata and Step 29.10 oracle evidence. It resolves the missing bundle-policy blocker by allowing same-task multi-product rows only inside a single-split task bundle. It separately certifies whether a row is backed by a strong executable oracle.

This gate does not make rows training-grade. It separates evidence from release approval: rows can be task-oracle-certified while still being blocked by withheld references, license policy, public benchmark contamination scanning, eval/private similarity or other governance controls.

## Current Result

```text
STEP29_29_DOCTOR_OK
source_row_count = 10
bundle_count = 3
train_bundle_count = 1
eval_bundle_count = 1
private_heldout_bundle_count = 1
cross_split_task_bundle_count = 0
same_task_multi_product_bundle_count = 3
same_task_multi_product_blocker_resolved_row_count = 10
train_bundle_isolation_passed = true
eval_private_distinctness_passed = false
split_bundle_isolation_passed = false
task_oracle_certified_count = 3
row_task_oracle_certified_count = 10
row_training_payload_oracle_certified_count = 4
withheld_reference_row_count = 6
training_grade_candidate_after_step29_29_count = 0
task_family_bundle_policy_complete = true
oracle_quality_certification_complete = true
private_generalization_claim_allowed = false
training_grade_data_release_allowed = false
training_launch_allowed = false
model_release_allowed = false
local_model_execution_used = false
remote_inference_invoked = false
```

## Why The Gate Remains Closed

The task-family bundle blocker is now implemented, but the current data still cannot be released for training-grade use.

The remaining blockers are:

- eval/private-heldout task scaffolds are too similar to support strong private generalization claims;
- some train rows contain withheld-eval references and are not training payload safe;
- license policy still allows scaffold-only data;
- public benchmark contamination scanning remains incomplete;
- contamination release policy is not integrated into final training-grade promotion.

## Artifacts

```text
results/local/task_family_bundle_oracle_quality_v1/summary.json
results/local/task_family_bundle_oracle_quality_v1/task_family_bundle_manifest.json
results/local/task_family_bundle_oracle_quality_v1/split_bundle_isolation_report.json
results/local/task_family_bundle_oracle_quality_v1/oracle_quality_certifications.jsonl
results/local/task_family_bundle_oracle_quality_v1/task_oracle_quality_report.json
results/local/task_family_bundle_oracle_quality_v1/training_candidate_decisions.jsonl
results/local/task_family_bundle_oracle_quality_v1/task_family_bundle_oracle_quality_gate_decision.json
results/local/task_family_bundle_oracle_quality_v1/public_safe_task_family_bundle_oracle_quality_report.json
results/local/task_family_bundle_oracle_quality_v1/task_family_bundle_oracle_quality_privacy_report.json
```

## Public Safety Contract

The public report contains counts and gate states only. It excludes raw rows, raw text, private identifier values, patch content, prompts, withheld-eval content and model outputs.

## Next Step

```text
Step 29.30 - hardened task generation and public benchmark contamination registry
```

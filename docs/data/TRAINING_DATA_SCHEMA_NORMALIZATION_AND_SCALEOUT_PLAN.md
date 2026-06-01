# Training Data Schema Normalization and Scaleout Plan

Status: Step 29.26 accepted  
Visibility: public-safe

## Purpose

Step 29.26 defines the canonical data product schemas needed before ForgeMoE can safely scale internal data generation.

This step does not create training-grade data. It creates the schema and scaleout control plane needed to avoid accidental debt:

```text
current governed exports
  -> source-schema mapping
  -> canonical schema registry
  -> manifest-ref scaffold normalization
  -> generator scaleout phases
  -> future training-grade gate
```

## Canonical Data Products

The canonical registry defines five data products:

```text
patch_sft
trajectory_sft
preference_pair
repair_trace
executable_task_ref
```

Each product declares required references and required controls. The current normalized scaffold rows are manifest references only; they do not include raw patches, prompts, private identifiers or withheld-eval content.

## Current Result

Current aggregate result:

```text
source_row_count = 10
canonical_schema_count = 5
mapped_source_row_count = 10
unmapped_source_row_count = 0
normalized_scaffold_row_count = 6
training_grade_row_count = 0
scaleout_phase_count = 5
training_launch_allowed = false
model_release_allowed = false
```

All current source schemas are mapped, but training-grade release remains blocked.

## Blocking Gaps

The current blockers are explicit:

```text
training_grade_rows_absent
license_provenance_not_complete_for_all_training_rows
contamination_scan_not_complete_for_all_rows
row_level_oracle_quality_not_certified_for_all_training_products
scaleout_seed_repo_license_registry_not_implemented
deduplication_and_near_duplicate_scanner_not_implemented
large_scale_generator_not_yet_executed
```

## Scaleout Phases

The scaleout plan is:

```text
schema_lock_v1
provenance_and_license_registry
contamination_and_dedup_scanners
oracle_quality_certification
bounded_generator_scaleout_dry_run
```

Every phase remains control-plane only by default. No training job, local model execution or remote inference is authorized by this step.

## Artifacts

The doctor writes:

```text
results/local/training_data_schema_normalization_scaleout_plan_v1/summary.json
results/local/training_data_schema_normalization_scaleout_plan_v1/canonical_schema_registry.json
results/local/training_data_schema_normalization_scaleout_plan_v1/source_to_canonical_schema_map.json
results/local/training_data_schema_normalization_scaleout_plan_v1/row_schema_mapping.jsonl
results/local/training_data_schema_normalization_scaleout_plan_v1/normalized_scaffold_manifest.jsonl
results/local/training_data_schema_normalization_scaleout_plan_v1/schema_gap_report.json
results/local/training_data_schema_normalization_scaleout_plan_v1/generator_scaleout_plan.json
results/local/training_data_schema_normalization_scaleout_plan_v1/training_data_schema_normalization_gate_decision.json
results/local/training_data_schema_normalization_scaleout_plan_v1/public_safe_training_data_schema_normalization_report.json
results/local/training_data_schema_normalization_scaleout_plan_v1/training_data_schema_normalization_privacy_report.json
```

## Next Step

The next recommended step is:

```text
Step 29.27 - provenance, license and contamination scanner implementation
```

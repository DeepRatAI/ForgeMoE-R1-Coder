# Training Data Governance Scaleout

Status: Step 29.25 accepted  
Visibility: public-safe  

## Purpose

Step 29.25 turns the current internal dataset exports into an auditable admission surface.

The gate separates three concepts that must not be conflated:

```text
raw generated rows
  -> scaffold-only rows for schema and tooling validation
  -> future training-grade rows after provenance, contamination and oracle controls pass
```

The current ForgeMoE data is useful as deterministic scaffold data. It is not yet training-grade data.

## Inputs

The gate consumes current local artifacts from:

```text
Step 29.7 dataset source matrix
Step 29.24 private heldout aggregate candidate gate
Step 29.9 internal synthetic micro generator exports
Step 29.11 agentic trajectory recorder exports
```

No external dataset is downloaded. No local model is loaded. No remote inference is invoked. No training job is launched.

## Admission Policy

A row can be admitted as scaffold-only when:

```text
split == train
never_train_on is not true
no private heldout identifier is present
no credential-like secret pattern is present
```

A row can be admitted as training-grade only when the scaffold checks pass and all stronger controls pass:

```text
explicit license and generator provenance
completed public benchmark contamination scan
certified execution oracle quality for the row
no withheld-eval reference exported into the row
explicit never-train field
```

The current gate intentionally admits zero rows as training-grade.

## Current Result

Current aggregate result:

```text
export_file_count = 10
raw_row_count = 10
train_split_row_count = 6
eval_split_row_count = 2
private_heldout_row_count = 2
scaffold_admitted_row_count = 6
training_grade_admitted_row_count = 0
training_launch_allowed = false
model_release_allowed = false
```

Eval and private heldout rows are rejected for training use. Private heldout identifiers are not included in public reports.

## Artifacts

The doctor writes:

```text
results/local/training_data_governance_scaleout_v1/summary.json
results/local/training_data_governance_scaleout_v1/dataset_export_inventory.json
results/local/training_data_governance_scaleout_v1/row_admission_results.jsonl
results/local/training_data_governance_scaleout_v1/admitted_scaffold_manifest.jsonl
results/local/training_data_governance_scaleout_v1/rejected_rows.jsonl
results/local/training_data_governance_scaleout_v1/split_integrity_report.json
results/local/training_data_governance_scaleout_v1/license_provenance_report.json
results/local/training_data_governance_scaleout_v1/contamination_report.json
results/local/training_data_governance_scaleout_v1/public_safe_training_data_governance_report.json
results/local/training_data_governance_scaleout_v1/training_data_governance_gate_decision.json
results/local/training_data_governance_scaleout_v1/training_data_governance_privacy_report.json
```

## Next Step

The next recommended step is schema normalization and generator scaleout planning:

```text
Step 29.26 - Training data schema normalization and generator scaleout plan
```

That step should define the canonical row schemas and controls needed before any large-scale generation or training job.

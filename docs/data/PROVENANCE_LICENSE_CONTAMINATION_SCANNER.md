# Provenance, License and Contamination Scanner

Status: Step 29.27 accepted  
Visibility: public-safe

## Purpose

Step 29.27 turns the Step 29.26 schema gaps into executable scanners.

The scanner inspects current governed rows and emits public-safe evidence for:

```text
provenance references
license classification
train/eval/private identifier overlap
hash-only fingerprints
training-grade blocking reasons
```

It does not download external datasets, run local models, invoke remote inference or launch training.

## Current Result

Current aggregate result:

```text
source_row_count = 10
training_row_count = 6
eval_row_count = 2
private_heldout_row_count = 2
provenance_scanned_row_count = 10
license_scanned_row_count = 10
contamination_scanned_row_count = 10
training_grade_provenance_pass_count = 0
training_grade_license_pass_count = 0
train_private_identifier_overlap_count = 0
train_eval_identifier_overlap_count = 0
public_benchmark_scan_complete_count = 0
near_duplicate_scanner_complete = false
training_grade_pass_count = 0
training_launch_allowed = false
```

This is the expected current state. The scanner proves that current train rows do not overlap with known eval/private identifiers, but it still blocks training-grade release because the license policy is scaffold-only, public benchmark scanning is incomplete and near-duplicate scanning is not implemented.

## Public-Safe Policy

Scanner outputs do not include:

```text
raw rows
private identifier values
patch content
prompt content
withheld-eval content
model outputs
```

Fingerprints are hashes only.

## Artifacts

The doctor writes:

```text
results/local/provenance_license_contamination_scanner_v1/summary.json
results/local/provenance_license_contamination_scanner_v1/provenance_scan_results.jsonl
results/local/provenance_license_contamination_scanner_v1/license_scan_results.jsonl
results/local/provenance_license_contamination_scanner_v1/contamination_scan_results.jsonl
results/local/provenance_license_contamination_scanner_v1/row_scanner_decisions.jsonl
results/local/provenance_license_contamination_scanner_v1/fingerprint_index.json
results/local/provenance_license_contamination_scanner_v1/scan_summary.json
results/local/provenance_license_contamination_scanner_v1/provenance_license_contamination_gate_decision.json
results/local/provenance_license_contamination_scanner_v1/public_safe_provenance_license_contamination_report.json
results/local/provenance_license_contamination_scanner_v1/provenance_license_contamination_privacy_report.json
```

## Next Step

The next recommended step is:

```text
Step 29.28 - dedup and near-duplicate scanner implementation
```

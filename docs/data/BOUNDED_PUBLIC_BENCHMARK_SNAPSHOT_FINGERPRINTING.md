# Bounded Public Benchmark Snapshot Fingerprinting

Step 29.34 performs the first bounded content-aware fingerprinting pass over official public benchmark sources.

The gate is deliberately not a training-data ingestion step. It uses official Hugging Face and GitHub sources, reads only capped metadata and capped content prefixes, persists hashes and aggregate metadata, and keeps raw public benchmark content out of ForgeMoE training payloads.

## Current Result

```text
STEP29_34_DOCTOR_OK
benchmark_snapshot_count = 12
bounded_snapshot_complete_count = 12
bounded_snapshot_fingerprinting_complete = true
snapshot_train_candidate_overlap_pair_count = 48
exact_public_benchmark_snapshot_collision_count = 0
high_public_benchmark_snapshot_similarity_count = 0
content_prefix_bytes_persisted = 0
full_public_benchmark_corpus_scan_complete = false
training_payload_materialization_authorized = false
training_grade_data_release_allowed = false
```

## What Is Fingerprinted

The gate fingerprints:

- Hugging Face dataset revision identifiers when present;
- Hugging Face sibling/path manifests as hash-only sets;
- GitHub default-branch tree manifests when a repository source exists;
- bounded content prefixes from selected official metadata, repository or dataset files;
- overlap between those public snapshot fingerprints and Forge-native oracle-certified train candidates.

The gate does not persist raw file bodies. Content-prefix downloads are bounded by explicit byte caps and only their hashes are retained.

## Budget Guardrails

```text
max_metadata_bytes_per_request = 1,000,000
max_content_prefix_bytes_per_file = 32,768
max_content_files_per_benchmark = 4
max_bytes_per_benchmark = 131,072
max_total_content_bytes = 2,000,000
```

These limits are part of the gate contract. If they are exceeded, the gate fails closed.

## Release State

Step 29.34 strengthens public benchmark contamination evidence beyond Step 29.33 metadata/license attestation, but it is still not a full corpus materialization pass. It does not mark data as training-grade and does not authorize training payload materialization.

Remaining blockers:

- full public benchmark corpus materialization and contamination scan;
- training payload materialization authorization.

## Artifacts

```text
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/summary.json
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/public_benchmark_snapshot_fingerprints.jsonl
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/public_benchmark_content_prefix_fingerprints.jsonl
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/benchmark_snapshot_train_candidate_overlap_results.jsonl
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/bounded_snapshot_fingerprinting_budget_report.json
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/step29_34_training_release_policy_delta.json
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/public_benchmark_snapshot_fingerprinting_gate_decision.json
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/public_safe_public_benchmark_snapshot_fingerprinting_report.json
results/local/bounded_public_benchmark_snapshot_fingerprinting_v1/public_benchmark_snapshot_fingerprinting_privacy_report.json
```

## Public Safety Contract

The public-safe report excludes raw benchmark tasks, raw task IDs, raw rows, raw text, content-prefix hashes, path values, patch content, hidden tests, private identifiers and model outputs.

## Next Step

```text
Step 29.35 - full public benchmark corpus materialization and contamination scan v1
```

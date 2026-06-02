# Full Public Benchmark Corpus Materialization Scan

Step 29.35 streams and hashes the full official public benchmark corpora tracked by the ForgeMoE public benchmark registry.

The gate is not a training ingestion step. It reads official public benchmark bytes to compute fingerprints, persists only hash/manifests, compares Forge-native train candidates against the full public benchmark fingerprint set, and keeps raw benchmark content out of training payloads.

## Current Result

```text
STEP29_35_DOCTOR_OK
benchmark_registry_entry_count = 12
benchmark_complete_scan_count = 12
source_file_count = 2328
observed_total_bytes_hashed = 9679147849
full_public_benchmark_corpus_scan_complete = true
content_bytes_persisted = 0
exact_full_public_benchmark_corpus_collision_count = 0
updated_release_policy_passed_requirement_count = 7
updated_release_policy_failed_requirement_count = 1
training_payload_materialization_authorized = false
training_grade_data_release_allowed = false
```

## Method

The gate:

- reads Step 29.33 source attestations;
- requires Step 29.34 bounded snapshot fingerprinting to be complete;
- enumerates Hugging Face dataset files and GitHub repository blob trees;
- streams each official file/blob under a total byte budget;
- computes full-file SHA-256 fingerprints;
- caches hash-only fingerprints for repeatable post-commit doctors;
- compares Forge-native train candidate hashes against the public corpus fingerprint set.

Raw benchmark file bodies are never persisted.

## Release State

The full public benchmark corpus scan blocker is resolved only when every enumerated official source file is hashed successfully and the overlap scan observes zero exact collisions.

Training-grade release remains blocked until training payload materialization is explicitly authorized by the release policy.

## Artifacts

```text
results/local/full_public_benchmark_corpus_materialization_scan_v1/summary.json
results/local/full_public_benchmark_corpus_materialization_scan_v1/public_benchmark_full_corpus_source_manifest.jsonl
results/local/full_public_benchmark_corpus_materialization_scan_v1/public_benchmark_full_corpus_file_fingerprints.jsonl
results/local/full_public_benchmark_corpus_materialization_scan_v1/full_corpus_train_candidate_contamination_results.jsonl
results/local/full_public_benchmark_corpus_materialization_scan_v1/full_corpus_streaming_budget_report.json
results/local/full_public_benchmark_corpus_materialization_scan_v1/step29_35_training_release_policy_delta.json
results/local/full_public_benchmark_corpus_materialization_scan_v1/full_public_benchmark_corpus_materialization_gate_decision.json
results/local/full_public_benchmark_corpus_materialization_scan_v1/public_safe_full_public_benchmark_corpus_materialization_report.json
results/local/full_public_benchmark_corpus_materialization_scan_v1/full_public_benchmark_corpus_materialization_privacy_report.json
```

## Next Step

```text
Step 29.36 - training payload materialization authorization v1
```

# ADR-0061: Full Public Benchmark Corpus Materialization Scan

## Status

Accepted.

## Context

Step 29.34 completed bounded public benchmark snapshot fingerprinting, but training-grade release still required a full public benchmark corpus scan. The project standard requires evidence strong enough to defend no-contamination claims before any training payload is materialized.

## Decision

Implement Step 29.35 as a streaming full-corpus materialization scan.

The gate streams official Hugging Face and GitHub public benchmark content, computes full-file hashes, persists only fingerprints/manifests, and compares Forge-native train candidates against the resulting public corpus fingerprint set.

The implementation uses a hash-only local cache so that post-commit doctors can revalidate the complete fingerprint set without repeatedly downloading the same multi-gigabyte corpus when official revisions have not changed.

## Consequences

This resolves the full public benchmark corpus scan blocker when all enumerated public benchmark files are hashed and no exact collisions are observed.

It does not authorize training. Training payload materialization remains a separate gate because data release must be explicit, auditable and reversible.

## Validation

```text
./scripts/dev/step29_35_doctor.sh
```

Expected result:

```text
STEP29_35_DOCTOR_OK
```

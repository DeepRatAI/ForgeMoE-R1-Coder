# ADR-0054: Dedup and Near-Duplicate Scanner

## Status

Accepted.

## Context

Step 29.27 created executable provenance, license and contamination scanner evidence, but intentionally left near-duplicate scanning incomplete. That meant the project could prove basic split identifier isolation, but could not yet prove that train, eval and private heldout rows were isolated at the task-family and semantic-similarity levels.

ForgeMoE needs this gate before any data scaleout can be treated as training-grade. A model-specialization factory that trains on duplicated task families or near-duplicates of evaluation rows would produce misleading scores and contaminate downstream agent evaluation.

## Decision

Add a fail-closed deduplication and near-duplicate scanner.

The scanner reads the current governed rows, computes hash-only row features, compares every row pair, emits exact duplicate groups, near-duplicate groups, split collision counts and row-level dedup decisions. It reports only hashes and aggregate counts, not raw task text, private identifiers, patch content or prompts.

The scanner marks `near_duplicate_scanner_complete = true` because the executable gate now exists. It keeps `deduplication_passed = false` because current rows contain same-task multi-product groups and there is not yet a task-family bundle policy for training-grade release.

## Consequences

ForgeMoE now has executable evidence for dedup and near-duplicate risk in the current scaffold. This removes the previous “scanner not implemented” gap but exposes the next real blocker: task-family bundle isolation and oracle-quality certification.

Training remains blocked. No row is training-grade. No model execution, remote inference, large dataset download or training job is required by this gate.

## Validation

The gate is validated by:

```text
./scripts/dev/step29_28_doctor.sh
```

Expected terminal marker:

```text
STEP29_28_DOCTOR_OK
```

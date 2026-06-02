# ADR-0060: Bounded Public Benchmark Snapshot Fingerprinting

## Status

Accepted.

## Context

Step 29.33 verified official public benchmark metadata and license evidence, but it did not inspect content-level public benchmark snapshots. That left the contamination story stronger than a registry-only check but weaker than the standard needed before releasing any training-grade payload.

ForgeMoE needs a staged path toward full public benchmark contamination scanning that is reproducible and cost-aware. The local workstation is not suitable for local model execution, and the current gate does not require inference or training. It does require bounded network access to official benchmark sources.

## Decision

Implement Step 29.34 as a bounded public benchmark snapshot fingerprinting gate.

The gate:

- reads Step 29.33 official source attestations;
- refreshes official Hugging Face and GitHub source metadata;
- fingerprints dataset revisions, dataset file manifests and GitHub repository trees;
- reads only bounded content prefixes from selected official files;
- stores only hashes and aggregate metadata;
- compares those public snapshot fingerprints against Forge-native train candidate hashes;
- keeps public benchmark corpora reference/eval-only and direct-training forbidden.

## Consequences

This adds content-aware public benchmark contamination evidence without promoting any row to training-grade data.

Training-grade release remains blocked until a full public benchmark corpus materialization and contamination scan is implemented, and until training payload materialization is explicitly authorized by the release policy.

The gate is budget-aware and fails closed when byte caps are exceeded.

## Validation

The gate is validated by:

```text
./scripts/dev/step29_34_doctor.sh
```

Expected result:

```text
STEP29_34_DOCTOR_OK
```

The doctor asserts twelve benchmark snapshots, bounded fingerprint completion, zero exact public benchmark snapshot collisions, zero high-similarity public benchmark snapshot matches, zero persisted content bytes, public-safe reporting and privacy scan success.

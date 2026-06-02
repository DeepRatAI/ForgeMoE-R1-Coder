# ADR-0058: Hardened Oracle Quality and Data Release Integration

## Status

Accepted.

## Context

Step 29.31 generated hardened executable tasks with real temporary Git repositories, `git diff` patches, `git apply --check`, public pre-fail, public post-pass, hidden post-pass and negative patch challenges.

Those properties are necessary but not sufficient for training-grade release. The project also requires explicit release policy integration, split isolation, benchmark contamination gates, license/provenance gates and public-safe reporting.

## Decision

Add Step 29.32 as a fail-closed integration gate.

The gate certifies all Step 29.31 hardened task oracles and emits hash-only release decisions. Train split tasks may become oracle-certified train candidates, but they are not promoted to training-grade until full public benchmark corpus scanning, upgraded license/provenance attestation and training payload materialization authorization are complete.

## Rationale

This separates oracle quality from data release. A task can be executable and strongly verified while still being unsafe to train on if contamination, license or payload-materialization evidence is incomplete.

The gate resolves two prior blockers:

- hardened tasks now have integrated oracle-quality certification;
- the final release policy is now executable and auditable.

It preserves the remaining blockers instead of hiding them behind a broad success claim.

## Consequences

Positive:

- all twelve hardened tasks receive oracle-quality certifications;
- four train split tasks become oracle-certified train candidates;
- public reports remain aggregate-safe;
- release blockers are represented per task and in aggregate;
- future corpus/license work has a concrete policy to satisfy.

Negative:

- zero rows are still training-grade;
- training remains blocked until public benchmark corpus scanning and license/provenance attestation are implemented;
- raw training payload materialization is intentionally deferred.

## Validation

```text
./scripts/dev/step29_32_doctor.sh
STEP29_32_DOCTOR_OK
```

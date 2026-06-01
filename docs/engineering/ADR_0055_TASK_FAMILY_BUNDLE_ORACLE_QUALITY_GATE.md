# ADR-0055: Task-Family Bundle and Oracle-Quality Gate

## Status

Accepted.

## Context

Step 29.28 implemented deduplication and near-duplicate scanning. That gate exposed two distinct issues: same-task multi-product rows need an explicit bundle policy, and eval/private-heldout task scaffolds are too similar for strong private generalization claims.

The same-task multi-product issue is not inherently bad. A single executable task can legitimately produce patch SFT, trajectory SFT, repair-trace and preference rows. The project needs a policy that allows this only when all products remain inside the same split and are sampled as a controlled task-family bundle.

The oracle-quality issue is separate. Rows should be able to reference strong executable oracle evidence without being promoted to training-grade prematurely.

## Decision

Add a fail-closed task-family bundle and oracle-quality gate.

The gate:

- groups rows into hash-only task-family bundles;
- allows same-task multi-product rows only inside one split;
- rejects cross-split task bundles;
- blocks private generalization claims when eval/private similarity is high;
- certifies rows against Step 29.10 oracle evidence;
- keeps training-grade release blocked until all remaining governance controls pass.

## Consequences

ForgeMoE now has executable evidence for bundle policy and oracle-quality certification. The same-task bundle-policy blocker is resolved as a policy mechanism, but no row is training-grade yet.

Remaining blockers include eval/private scaffold similarity, withheld-reference rows, scaffold-only license policy, incomplete public benchmark contamination scanning and missing final contamination release integration.

No local model execution, remote inference, large dataset download or training job is required by this gate.

## Validation

The gate is validated by:

```text
./scripts/dev/step29_29_doctor.sh
```

Expected terminal marker:

```text
STEP29_29_DOCTOR_OK
```

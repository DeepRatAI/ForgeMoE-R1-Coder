# ADR-0057: Hardened Executable Task Generator

## Status

Accepted.

## Context

Step 29.30 created a fail-closed blueprint and public benchmark registry gate. That was necessary but not sufficient: metadata blueprints do not prove executable task quality.

The project needs generated tasks that exercise repository editing behavior, not single-function toy completion. The next gate must prove real Git patch generation, executable public/hidden tests and negative oracle checks.

## Decision

Add a deterministic hardened executable task generator.

The generator:

- instantiates all twelve Step 29.30 blueprints;
- creates real temporary Git repositories;
- emits patches using `git diff`;
- validates patches with `git apply --check`;
- requires public tests to fail before the golden patch;
- requires public and hidden tests to pass after the golden patch;
- requires rejected, public-overfit, wrong-file and semantic-noop negatives to fail appropriately;
- keeps all generated rows scaffold-only until downstream certification and release gates pass.

## Consequences

ForgeMoE now has a stronger internal executable task source. The tasks are still small, but they are multi-file, split-aware and oracle-checked against overfitting and wrong-file edits.

This gate does not execute local models, invoke remote inference, download large datasets, launch training or release data as training-grade.

## Validation

The gate is validated by:

```text
./scripts/dev/step29_31_doctor.sh
```

Expected terminal marker:

```text
STEP29_31_DOCTOR_OK
```

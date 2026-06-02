# ADR-0062: Training Payload Materialization Authorization

## Status

Accepted.

## Context

Step 29.35 closed the full public benchmark corpus scan blocker. The remaining release-policy blocker was explicit training payload materialization authorization.

The project needs a concrete training payload before any tokenization, training, remote execution or model release gate can be meaningful. The payload must be useful for patch SFT while preserving eval integrity.

## Decision

Implement Step 29.36 as an authorization and materialization gate for Forge-native train split tasks.

The gate materializes only oracle-certified train candidates whose license/provenance, split-isolation and full public benchmark contamination checks have passed. It exports repo-before files, public tests, task instructions and target git diff patches for patch SFT.

Hidden tests, private-heldout tasks, eval tasks, public-eval tasks and negative patches are not exported into the training payload. Hidden tests remain validation-only evidence.

Training execution remains a later gate because payload authorization, tokenization, training launch, candidate evaluation and model release are separate auditable decisions.

## Consequences

ForgeMoE now has a first training-grade internal patch SFT payload with four rows. The payload is intentionally small; it is suitable as a correctness and governance seed, not as a sufficient final training corpus.

The next gate must validate schema quality, estimate tokenization/cost characteristics and decide whether the payload is ready to feed a remote training job or whether more governed data scaleout is required first.

## Validation

```text
./scripts/dev/step29_36_doctor.sh
```

Expected result:

```text
STEP29_36_DOCTOR_OK
```

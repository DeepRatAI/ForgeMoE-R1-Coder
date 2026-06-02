# ADR-0063: Training Payload Schema Quality and Tokenization Gate

## Status

Accepted.

## Context

Step 29.36 materialized the first Forge-native training-grade patch SFT payload. Before training can be launched, the payload must pass schema quality checks and token-length planning.

The current workspace does not provide `transformers`, `tokenizers`, `sentencepiece` or `tiktoken`. Loading a local model is also out of scope for this host. Tokenizer validation must therefore be separated from model execution and handled as a tokenizer-only remote/local tooling gate.

## Decision

Implement Step 29.37 as a strict schema-quality and tokenizer-proxy gate.

The gate validates payload schema, hashes, manifest consistency, hidden-test exclusion, negative-patch exclusion and canonical SFT rendering. It estimates token budgets with a deterministic conservative proxy and emits a fail-closed training readiness decision.

Model-specific tokenizer validation is required before training launch. Step 29.37 can pass payload quality while still keeping `training_launch_allowed = false` until a later tokenizer/cost gate validates the selected base-model tokenizer.

## Consequences

The project gains a reproducible, auditable training payload quality gate without pretending that proxy estimates are exact model tokens.

The next gate must select the target base-model tokenizer, validate tokenization without loading model weights, estimate remote training cost and decide whether the small seed payload is sufficient for a first remote training dry run or whether governed data scaleout must happen first.

## Validation

```text
./scripts/dev/step29_37_doctor.sh
```

Expected result:

```text
STEP29_37_DOCTOR_OK
```

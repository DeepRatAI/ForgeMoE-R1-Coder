# ADR-0017 — First Real Model Runtime Before Useful Baseline

Status: Accepted  
Date: 2026-05-14

## Context

Step 19 proved that the project can run a real model through the `LocalTransformersModelAdapter`.

The model used was:

```text
sshleifer/tiny-gpt2
```

The purpose was not quality. The purpose was to validate runtime integration.

Observed Step 19 result:

```text
model_load_ok = true
real_generation_ok = true
generated_response_count = 1
parsed_candidate_count = 0
parse_failure_count = 1
candidate_pipeline_attempted = false
solve_required = false
```

## Decision

Treat Step 19 as a successful runtime smoke test, not a model-quality baseline.

The next useful model step must be a real code-model baseline with an explicit target model, task suite, generation configuration, and artifact lineage.

## Rationale

A tiny non-code model is useful for validating the adapter boundary, dependency installation, real generation metadata, and parse-failure accounting. It should not be used to infer coding capability.

## Consequences

Step 20 can now focus on model capability rather than runtime mechanics.

Step 20 should answer:

```text
Can a real code model produce parseable patches?
What is its parse failure rate?
What is its solve rate on toy/early tasks?
What generation settings are stable?
What artifacts and metadata are required for base-vs-tuned comparison?
```

## Boundary

Step 19 proves:

```text
mock generation -> real local Transformers generation
```

Step 20 begins:

```text
real generation -> useful code-model baseline
```

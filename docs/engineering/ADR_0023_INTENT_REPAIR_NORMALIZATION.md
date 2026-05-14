# ADR-0023 — Intent Repair and Normalization

Status: Accepted
Date: 2026-05-14

## Context

Step 24 proved that the real Qwen2.5-Coder 0.5B model can emit parseable JSON under the Structured Edit Intent contract. Step 24.1 showed that all generated intents failed semantic validation because `find_text` was non-code and did not match the current file.

## Decision

Introduce an Intent Repair and Normalization layer between model intent generation and canonical patch construction.

The repair layer is allowed to use grounded context already present in the prompt and artifacts:

- current file text
- tests
- expected behavior
- parsed model intent
- validation error

It is not allowed to bypass verification. Every repaired intent must be revalidated, converted into a canonical patch, applied with `git apply`, and verified with tests.

## Rationale

This layer converts partially useful model outputs into executable trajectories. The model may identify the task shape and emit parseable structure while failing exact field grounding. Repair lets the system recover useful supervision signal instead of discarding the sample.

## Consequences

Intent repair creates high-value training data:

```text
raw_model_intent -> repaired_intent -> canonical_patch -> verifier_result -> reward
```

This is a direct bridge toward SFT and later verifier-guided optimization.

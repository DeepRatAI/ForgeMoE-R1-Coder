# ADR-0016 — Tiny Real Model Smoke Test Before Baseline

Status: Accepted  
Date: 2026-05-13

## Context

Step 18 introduced a runtime-independent model adapter contract. Before using a meaningful coding model, the system must prove that it can load a real model runtime, generate real text, capture metadata, and route the result through the existing candidate parsing path.

## Decision

Run a tiny Hugging Face Transformers causal language model as the first real model smoke test.

The default model is:

```text
sshleifer/tiny-gpt2
```

This model is not selected for coding quality. It is selected because it is tiny and suitable for validating runtime mechanics.

## Expected result

A successful Step 19 does not require a valid patch or solved task.

Required:

```text
model loads
generation runs
GeneratedResponse objects are produced
model metadata is recorded
parse failures are measured
artifacts are uploaded
```

Optional:

```text
patch parsed
candidate pipeline attempted
task solved
```

## Rationale

The first real model step should test runtime integration rather than model capability. This reduces risk before spending GPU budget or moving to larger code models.

## Consequences

Step 20 can then focus on a meaningful real coding baseline with fewer unknowns.

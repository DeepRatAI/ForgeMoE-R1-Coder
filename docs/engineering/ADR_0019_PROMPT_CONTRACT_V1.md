# ADR-0019 — Prompt Contract v1 Before Training

Status: Accepted  
Date: 2026-05-14

## Context

Step 20 established the first useful real code-model baseline with `Qwen/Qwen2.5-Coder-0.5B-Instruct`.

The model generated three parseable unified diffs, but none applied successfully. Forensics showed that the model edited or invented `app/__init__.py`, hallucinated unrelated classes, and generated hunks that did not match the repository.

## Decision

Introduce Prompt Contract v1 before any tuning step.

Prompt Contract v1 defines a strict repository patching interface:

```text
output only unified diff
no Markdown fences
no prose
edit only allowed files
use exact repository paths
do not invent files
do not create unrelated classes
hunks must match existing context
prefer minimal patches
```

## Rationale

Training on top of a weak or ambiguous prompt interface would contaminate the signal. The correct order is:

```text
runtime -> baseline -> forensics -> prompt contract -> rerun baseline -> then training data / SFT / RL
```

## Expected impact

Prompt Contract v1 should primarily improve:

```text
patch_apply_success_count
wrong_file_edit_rate
hallucinated_context_rate
```

It may or may not improve solve rate immediately. Applicability is the first gate.

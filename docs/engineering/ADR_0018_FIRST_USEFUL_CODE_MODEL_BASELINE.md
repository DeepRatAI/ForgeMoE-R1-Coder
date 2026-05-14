# ADR-0018 — First Useful Real Code-Model Baseline

Status: Accepted  
Date: 2026-05-14

## Context

Step 19 validated real model runtime mechanics with `sshleifer/tiny-gpt2`. Step 20 starts the first useful baseline with a real code-specialized model.

The selected model is:

```text
Qwen/Qwen2.5-Coder-0.5B-Instruct
```

## Decision

Use Qwen2.5-Coder 0.5B Instruct as the first real code-model baseline because it is small enough for CPU-bound validation while still being a code-oriented instruction model.

## Expected result

Step success does not require solving all tasks.

Required:

```text
model loads
real generation runs
task-level outputs are recorded
parseability is measured
candidate pipeline is attempted when patches are parseable
solve rate is computed
artifacts are uploaded
```

## Rationale

The purpose of this step is to establish a measurable baseline, not to claim SOTA performance. The result gives us the first base-model reference point before prompt improvements, larger models, QLoRA, verifier-guided selection, or training.

## Consequences

Future steps can compare against this baseline using the same task schema, adapter contract, prompt pipeline, parser, verifier, and registry discipline.

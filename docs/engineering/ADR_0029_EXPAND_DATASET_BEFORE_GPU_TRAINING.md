# ADR-0029 - Expand Structured SFT Dataset Before GPU Training

Status: Accepted
Date: 2026-05-15

## Context

Step 29.0 proved that the GPU training launch path can be prepared, but the current seed dataset is too small for meaningful model improvement.

Launching a GPU job with only a few rows would validate plumbing, but it would not advance the objective of producing a materially stronger coding-agent model.

## Decision

Before launching real GPU LoRA SFT, expand the structured SFT dataset.

The first expansion targets structured edit intent, not raw patch generation. The dataset should teach the model to express clear, constrained, executable edit plans before producing patches.

## Dataset coverage

The expansion covers:

- localized bugfix
- wrong-file avoidance
- missing test addition
- small multi-file edit
- safe refactor
- import and typing fix
- invalid patch repair intent
- semantic patch repair intent

## Consequence

The project delays paid GPU training until the dataset is less trivial. This does not lower the standard. It improves the probability that the first paid training run produces a meaningful signal.

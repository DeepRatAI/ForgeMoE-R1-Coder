# ADR-0024 — Structured Intent SFT Dataset Export

Status: Accepted  
Date: 2026-05-15

## Context

The project has reached the point where real model outputs can be converted into verified training trajectories.

Step 24 showed that Qwen2.5-Coder 0.5B can emit parseable structured JSON, but the semantic fields were invalid. Step 25 repaired those intents using grounded prompt context, built canonical patches, applied them, and solved the toy benchmark.

## Decision

Export the first supervised fine-tuning dataset from the structured-intent trajectory.

The training target is not raw unified diff text. The training target is the repaired structured edit intent JSON. Canonical patches remain system-generated.

## Rationale

Raw patch generation is a brittle interface for small models. Structured edit intent is a better learning target because it separates semantic edit prediction from deterministic patch construction.

The dataset preserves both:

1. SFT rows for supervised training.
2. Full trajectory records for future reward modeling, rejection sampling, DPO, or verifier-guided optimization.

## Consequence

This step marks the transition from pure evaluation infrastructure to dataset production. Future work can train adapters or LoRA checkpoints on this schema and then evaluate whether model-generated intents improve before repair.

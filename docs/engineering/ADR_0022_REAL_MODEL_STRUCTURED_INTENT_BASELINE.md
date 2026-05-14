# ADR-0022 — Real Model Structured Edit Intent Baseline

Status: Accepted
Date: 2026-05-14

## Context

Step 20 and Step 21 showed that Qwen2.5-Coder 0.5B can generate code-like patch text, but raw unified diff generation is brittle. Step 22 classified the failure as non-actionable diff-like output. Step 23 proved that Structured Edit Intent plus a deterministic Canonical Patch Builder can solve the toy tasks when the intent is correct.

## Decision

Run the real Qwen2.5-Coder 0.5B model against the Structured Edit Intent contract.

The model is asked to output a constrained JSON object containing file path, exact find text, exact replacement text, and rationale. The system validates the JSON intent, builds the canonical patch, applies it, and runs tests.

## Rationale

This separates model responsibilities from system responsibilities:

- model: localize and propose the semantic edit
- system: validate intent, construct patch, apply patch, verify behavior

This is a stronger interface for small and mid-sized models than raw diff generation.

## Consequence

Step 24 measures real-model behavior under the new interface. It does not require success on all tasks. The key signal is whether structured intent improves parse validity, patch applicability, and solve rate relative to raw diff baselines.

# ADR-0026 — Memory-Safe Local LoRA SFT Dry Run Boundary

Status: Accepted
Date: 2026-05-15

## Context

The first Step 28 attempt loaded Qwen2.5-Coder 0.5B weights in AWS CloudShell. CloudShell killed the process during weight loading, which indicates local memory/process limits rather than a model, PEFT, or dataset error.

## Decision

Do not retry full 0.5B weight loading inside CloudShell.

Use a memory-safe architecture dry run:

1. Load the real model config through AutoConfig.
2. Instantiate a tiny Qwen2-compatible architecture locally.
3. Infer LoRA target modules from Qwen2 module names.
4. Attach PEFT LoRA adapters.
5. Count trainable adapter parameters.
6. Validate the Step 27 train/eval dataset and tokenization path.
7. Emit a GPU training job specification for the real model.

## Rationale

The purpose of this boundary is to validate adapter wiring before GPU spend. Full weight loading in CloudShell is not a reliable requirement and creates false negatives.

## Consequence

Step 28 proves the LoRA architecture contract without requiring CloudShell to host the real 0.5B model in memory. Step 29 should move the real weight load and training to a GPU runtime.

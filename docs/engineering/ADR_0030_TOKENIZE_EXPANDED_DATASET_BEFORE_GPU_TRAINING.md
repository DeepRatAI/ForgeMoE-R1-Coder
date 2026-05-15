# ADR-0030 - Tokenize Expanded Structured SFT Dataset Before GPU Training

Status: Accepted
Date: 2026-05-15

## Context

Step 29.2 expanded the structured-intent SFT dataset to 48 rows. Before launching a paid GPU training job, the dataset must be validated against the target model tokenizer.

## Decision

Create a tokenizer-only validation step before GPU training.

Step 29.3 renders each SFT row into chat-style training text, tokenizes with the target Qwen tokenizer, measures token lengths, validates structured-intent JSON targets, checks truncation risk, and emits a training manifest.

No model weights are loaded and no training job is launched.

## Rationale

Tokenization failures, malformed targets, and excessive sequence lengths should be found before spending GPU budget.

## Consequence

The training launch path becomes safer and more reproducible. The cost gate remains active.

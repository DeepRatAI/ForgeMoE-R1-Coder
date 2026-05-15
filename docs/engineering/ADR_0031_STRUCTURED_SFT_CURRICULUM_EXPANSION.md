# ADR-0031 - Structured SFT Curriculum Expansion Before Paid GPU Training

Status: Accepted
Date: 2026-05-15

## Context

Step 29.2 expanded the structured-intent SFT dataset to 48 rows, and Step 29.3 validated that dataset against the Qwen tokenizer with zero truncation risk.

That dataset is sufficient for plumbing validation, but it is still too small for the project's target standard.

## Decision

Expand the structured-intent SFT curriculum to 192 rows before launching paid GPU training.

The curriculum remains synthetic and deterministic, but expands coverage across more code-edit categories and implementation scenarios. The target remains structured JSON intent rather than raw patches.

## Rationale

The first paid GPU training job should train on a dataset that is large enough to produce a meaningful signal. Launching with only 48 rows would be operationally valid but strategically weak.

## Consequence

The project delays Step 30 training launch and preserves the cost gate. This improves data quality and reduces the risk of wasting GPU budget.

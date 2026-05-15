# ADR-0025 — Local Adapter Training Data Contract

Status: Accepted  
Date: 2026-05-15

## Context

Step 26 exported the first supervised fine-tuning dataset from structured intent trajectories. Before training an adapter, the project needs a stable training data contract, deterministic split, and tokenization report.

## Decision

Create a local adapter training preparation layer.

This layer validates SFT rows, checks target JSON, renders chat messages, performs deterministic train/eval splitting, and tokenizes examples with the same tokenizer as the intended base model.

## Rationale

Fine-tuning should not start until the dataset has passed structural and tokenization validation. This avoids wasting GPU time on malformed chat records, broken targets, or inconsistent train/eval splits.

## Consequence

The project now has a bridge from verified trajectories to adapter training. The next step can implement an actual local LoRA dry run or prepare a GPU-backed training job.

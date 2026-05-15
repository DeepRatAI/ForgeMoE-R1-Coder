# ADR-0028 - GPU Training Cost Gate

Status: Accepted
Date: 2026-05-15

## Context

The project has reached the boundary where real model training must move out of CloudShell and into a compute plane.

Step 28 validated LoRA attachment using a memory-safe architecture probe. The next technical action is real adapter SFT on GPU.

## Decision

Introduce a hard cost gate before launching managed GPU training.

Step 29.0 may validate configuration, datasets, IAM, S3, SageMaker API access, and launch specifications. It must not create a real training job.

A later step may launch training only after explicit approval.

## Rationale

Launching SageMaker training can incur AWS charges. The project must remain professional, reproducible, and cost-aware.

## Consequence

The standard is preserved. We do not reduce the technical objective; we move heavy compute into the proper runtime with explicit approval.

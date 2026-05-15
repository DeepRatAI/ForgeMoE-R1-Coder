# ADR-0027 - CloudShell Is Control Plane, Not Compute Plane

Status: Accepted
Date: 2026-05-15

## Context

During Step 28, AWS CloudShell killed the process while attempting to load full Qwen2.5-Coder 0.5B weights on CPU. The failure was environmental, not an adapter design failure.

CloudShell remains useful for Git, AWS CLI, S3 operations, manifests, documentation, and lightweight validation. It is not the correct place for real model training or large full-weight model loading.

## Decision

Treat CloudShell as a control plane.

Allowed CloudShell work:

- Git operations
- S3 artifact movement
- manifest creation
- registry generation
- documentation updates
- small Python validators
- model config inspection
- tiny architecture probes

Disallowed CloudShell work:

- full model training
- full model weight loading for medium or large models
- long-running GPU/CPU jobs
- expensive benchmark loops
- anything that should produce a trained artifact

Heavy work moves to a compute plane:

- SageMaker Training
- EC2 GPU
- AWS Batch GPU
- portable external GPU runner if AWS quota blocks progress

## Consequence

The project standard is not lowered. The architecture becomes more professional: CloudShell orchestrates, S3 persists, GPU runtimes train and evaluate.

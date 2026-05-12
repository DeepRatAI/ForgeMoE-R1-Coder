# ForgeMoE-R1-Agent-Coder

ForgeMoE-R1-Agent-Coder is an AWS-native AI Engineering project focused on adapting a strong open-weight code model into a fullstack software development agent.

## Current fixed decision

- Primary GPU target: NVIDIA H100 80GB
- AWS instance target: p5.4xlarge / ml.p5.4xlarge
- Primary model target: Qwen/Qwen3-Coder-30B-A3B-Instruct
- Budget target: ~200 USD
- Artifact store: S3

## Objective

Build a reproducible pipeline that pushes an open-weight coding model toward frontier-level fullstack e2e software engineering behavior through:

- QLoRA / LoRA adaptation
- agentic trajectory supervised fine-tuning
- verifiable code rewards
- test-driven self-repair loops
- verifier/reranker-guided inference
- repo-level evaluation
- cost-aware AWS execution

## Non-goals for v1

- Training a model from scratch
- Full dense-to-MoE upcycling
- Long continued pretraining
- Purchasing H100 capacity before the pipeline is ready

## AWS state

Completed:

- S3 artifact bucket
- budget guardrail
- non-root operator
- SageMaker execution role
- H100 quota requests

Pending:

- P5 Capacity Block approval
- EC2 On-Demand P quota approval
- SageMaker ml.p5.4xlarge quota approval

## Project principle

No experiment counts unless it produces:

- config
- manifest
- logs
- metrics
- reproducible artifact path in S3

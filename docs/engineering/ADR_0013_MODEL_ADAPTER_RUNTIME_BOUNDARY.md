# ADR-0013 — Model Adapter Runtime Boundary

Status: Accepted  
Date: 2026-05-13

## Context

The project is transitioning from model-free validation to real model integration. The current agentic pipeline already supports prompt construction, patch parsing, executable verification, candidate reranking, and experiment aggregation.

The next risk is coupling the pipeline directly to one model runtime.

Potential runtimes include:

```text
mock deterministic generation
local Hugging Face Transformers
SageMaker training/inference
vLLM server
OpenAI-compatible HTTP APIs
future Bedrock or custom endpoints
```

## Decision

Introduce a runtime-independent `ModelAdapter` contract before running real model baselines.

The core types are:

```text
GenerationConfig
ModelMetadata
GeneratedResponse
ModelAdapter protocol
```

The first concrete adapters are:

```text
DeterministicMockModelAdapter
LocalTransformersModelAdapter skeleton
```

A bridge converts `GeneratedResponse` into the existing `RawModelResponse` consumed by the candidate pipeline.

## Rationale

This avoids binding the agentic system to one backend. It also makes model metadata and generation parameters explicit artifacts of every run.

## Tradeoffs

The adapter layer adds abstraction before the first real model run. The benefit is reproducibility, backend portability, and cleaner experiment lineage.

## Consequences

Step 19 can introduce a tiny real local model without changing the candidate pipeline. Later SageMaker and vLLM adapters can implement the same contract.

## Security

No model adapter should store credentials in source code. Runtime credentials must come from environment variables, IAM roles, or managed secret systems.

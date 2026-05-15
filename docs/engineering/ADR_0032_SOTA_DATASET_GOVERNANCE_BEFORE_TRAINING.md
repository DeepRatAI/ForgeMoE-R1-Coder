# ADR-0032 - SOTA Dataset Governance Before Training-Grade GPU Runs

Status: Accepted
Date: 2026-05-15

## Context

The project has validated a complete scaffold for structured SFT data, tokenization, manifests, registry and GPU preflight.

However, the current datasets are deterministic scaffold data. They are not sufficient to support the project's North Star: transforming 7B/9B/14B code models into autonomous fullstack e2e coding agents competitive with frontier systems.

## Decision

Do not treat Step 29.2 or Step 29.5 synthetic data as final training-grade data.

Before any serious paid GPU training run, the project must define and enforce a SOTA dataset strategy covering:

- source code corpora;
- instruction code tasks;
- repository-level issue tasks;
- synthetic executable tasks;
- agentic trajectories;
- negative patch attempts;
- chosen/rejected preference pairs;
- hidden eval holdouts;
- provenance and licensing;
- deduplication and contamination controls;
- quality scoring and training mixture manifests.

## Rationale

For this project, data quality is a primary model capability lever.

A model cannot be expected to acquire frontier-level agentic software engineering behavior from a small synthetic scaffold. The data engine must become a core product of the system.

## Consequence

Step 30 GPU training is deferred until the data plane is sufficiently governed.

The project preserves the cost gate and moves next toward dataset acquisition, scoring, validation and heldout design.

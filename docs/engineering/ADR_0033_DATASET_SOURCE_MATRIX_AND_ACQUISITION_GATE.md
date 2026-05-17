# ADR-0033 - Dataset Source Matrix and Acquisition Gate

Status: Accepted
Date: 2026-05-15

## Context

Step 29.6 established that the current synthetic datasets are scaffold data, not final training-grade data.

The next engineering requirement is to convert dataset strategy into an operational acquisition gate.

## Decision

Create a dataset source matrix with explicit source roles, allowed uses, blocking gates and acquisition decisions.

Public benchmarks are reference and evaluation sources by default, not ordinary training corpora.

Large code corpora are blocked from ingestion until terms, license, provenance, safety, deduplication and contamination gates pass.

Forge internal synthetic executable tasks, agentic trajectories and private heldout eval are promoted as critical internal build targets.

## Consequence

Step 30 training remains blocked.

The next technical direction is to build internal task generation and heldout infrastructure rather than ingest arbitrary public data.

# ADR-0034 - Internal Synthetic Executable Task Generator and Private Heldout Protocol

Status: Accepted
Date: 2026-05-17

## Context

Step 29.7 classified external data sources and confirmed that training remains blocked.

The highest-priority path is now internal data generation: executable repository-level tasks, agentic trajectories, negative examples, preference pairs and private heldout evaluation.

## Decision

Design the Forge internal synthetic executable task generator as a first-class data engine.

The generator must include seed repository governance, immutable snapshots, controlled task mutation, executable oracles, hidden tests, difficulty scoring, patch verification, negative patch mining, trajectory recording, contamination scans, provenance manifests and split isolation.

Private heldout tasks are never training data. They are a promotion gate for north-star claims.

## Consequence

Step 30 remains blocked.

The next implementation step is a small deterministic micro-generator that creates one executable repo-level task family end to end.

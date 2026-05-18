# ADR-0037 - Agentic Trajectory Recorder v1

Status: Accepted
Date: 2026-05-18

## Context

Step 29.10 proved that the current micro-tasks have discriminative oracles. They can reject public-overfit, wrong-file, empty, no-op and rejected patches.

The next layer is to record the agentic process around those tasks. Future SFT, preference optimization and verifiable RL need traces of attempts, failures, repair signals and final patch selection, not only final patches.

## Decision

Add a deterministic trajectory recorder that consumes Step 29.10 gated tasks and emits agentic repair trajectories.

Each trajectory contains a negative public-overfit attempt that passes public tests and fails hidden tests, followed by a repaired golden patch that passes public and hidden tests. Training exports are produced only for the train split. Eval and private heldout trajectories remain isolated.

The recorder runs a privacy scan before export and records hidden-test hashes instead of hidden-test contents.

## Consequence

ForgeMoE now has the first bridge from executable oracle-gated tasks to agentic trajectory data.

This prepares the project for trajectory SFT, repair-trace learning, preference-pair extraction and future verifier-guided optimization without training prematurely.

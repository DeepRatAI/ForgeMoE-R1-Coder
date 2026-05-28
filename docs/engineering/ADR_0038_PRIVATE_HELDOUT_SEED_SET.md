# ADR-0038 - Private Heldout Seed Set v1

Status: Accepted
Date: 2026-05-28

## Context

Step 29.11 created oracle-gated agentic trajectories, but the project still needs a stronger protected evaluation substrate before any serious training expansion.

Training on small synthetic tasks without a private heldout discipline would create an early contamination risk. The project needs private tasks that are generated, validated, hashed, isolated and explicitly excluded from training exports.

## Decision

Add a deterministic private heldout seed set generator and doctor.

The generator creates three private-only executable tasks across boundary, string and collection semantics. Each task has a golden patch, rejected patch and public-overfit patch generated through real `git diff` in temporary repositories. The doctor requires public tests to fail before the patch, golden patches to pass public and hidden tests, rejected patches to fail, public-overfit patches to pass public tests but fail hidden tests, and edit scope to remain constrained.

The only export intended for broader consumption is a public-safe manifest containing hashes and metadata. Patch content and hidden-test content remain out of training exports.

## Consequence

ForgeMoE now has an explicit private heldout seed layer before training scale-up.

This blocks premature optimization against visible tasks and prepares the project for heldout-aware evaluation protocols, contamination checks and future model-improvement gates.

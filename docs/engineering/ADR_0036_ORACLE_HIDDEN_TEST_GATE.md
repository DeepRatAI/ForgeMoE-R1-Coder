# ADR-0036 - Oracle and Hidden-Test Gate

Status: Accepted
Date: 2026-05-18

## Context

Step 29.9 created the first deterministic executable micro-generator. It verified three tasks end-to-end with golden patches, public tests and hidden tests.

That is necessary but not sufficient for SOTA-grade data engineering. A task can have tests and still be weak if public tests are enough to overfit, if wrong-file edits are not rejected, or if private heldout data leaks into training exports.

## Decision

Add a separate oracle and hidden-test gate that consumes Step 29.9 artifacts and evaluates every task against adversarial patch challenges.

The gate requires golden patches to pass and rejected, semantic no-op, empty and wrong-file patches to fail. It also requires a public-overfit patch to pass public tests and fail hidden tests for each task.

The gate emits per-task oracle scores, patch challenge results, hidden-test isolation reports and a summary doctor marker.

## Consequence

ForgeMoE now distinguishes executable tasks from training-quality task candidates.

This gate blocks premature scaling and training until generated tasks demonstrate discriminative oracle strength, hidden-test usefulness, edit-scope enforcement and private heldout isolation.

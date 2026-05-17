# ADR-0035 - Deterministic Synthetic Micro-Generator Scaffold

Status: Accepted
Date: 2026-05-17

## Context

Step 29.8 designed the internal synthetic executable task generator and private heldout protocol.

The next required step is to turn that design into executable machinery without launching training or ingesting external datasets.

## Decision

Implement a deterministic micro-generator that creates a minimal set of executable repository-level tasks.

The scaffold generates train, eval and private heldout splits. It builds golden
and rejected patches through `git diff` inside temporary repositories with a
committed baseline, then verifies that public tests fail before the golden
patch, `git apply --check` passes, the golden patch applies, and public and
hidden tests pass after the patch.

The private heldout task is marked never-train-on and is not exported into training rows.

## Consequence

ForgeMoE now has its first executable internal data-generation scaffold.

The next step is to harden the oracle and hidden-test gate, then expand from deterministic micro tasks to broader generated task families.

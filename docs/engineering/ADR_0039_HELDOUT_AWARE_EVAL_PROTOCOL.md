# ADR-0039 - Heldout-Aware Eval Protocol v1

Status: Accepted
Date: 2026-05-29

## Context

Step 29.12 created private heldout seed tasks. Without a formal protocol, those tasks could accidentally become another visible optimization target.

The project needs an explicit boundary between development data, model-selection data and private final-gate data before any training or model candidate evaluation is scaled.

## Decision

Add a heldout-aware eval protocol generator and doctor.

The protocol consumes Step 29.12 private heldout artifacts and Step 29.11 trajectory split counts. It emits a split policy, reference candidate scorecards, a gate decision, a public-safe aggregate report and a privacy report.

The doctor requires the golden reference to pass, public-overfit and rejected references to fail, the private seed isolation report to pass, and the public-safe report to exclude private task ids, patch contents and hidden-test contents.

## Consequence

ForgeMoE now has an enforceable evaluation boundary before real model candidate evaluation.

Private heldout results can block training or release, but cannot be used as training data or prompt-iteration feedback.

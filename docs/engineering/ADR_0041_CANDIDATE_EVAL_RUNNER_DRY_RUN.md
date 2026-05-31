# ADR-0041 - Candidate Eval Runner Dry Run v1

Status: Accepted
Date: 2026-05-31

## Context

Step 29.14 defined a model candidate eval package contract. The next requirement is to prove that a runner can emit an actual package, validation result, gate decision and public-safe report.

Doing this with a real model is premature because the evaluation package mechanics should be validated before spending compute or risking private heldout leakage.

## Decision

Add a candidate eval runner dry run.

The runner emits one dry-run reference candidate package and validates it against the Step 29.14 contract. The package is structurally valid but not release-eligible because it is not a real model candidate. The runner also emits a trace, gate decision, public-safe report and privacy report.

## Consequence

ForgeMoE now has the first end-to-end candidate evaluation package path.

The next step can replace the dry-run reference with a real smoke candidate package while preserving the same contract and privacy gates.

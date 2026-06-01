# ADR-0045 - Remote Inference Execution Candidate Eval v1

Status: Accepted
Date: 2026-06-01

## Context

Step 29.18 introduced a cost approval gate for remote inference. The project still needs a concrete execution harness so the first paid model call is not performed manually or outside the candidate evaluation contract.

The harness must preserve the current safety constraints: no local model execution, no paid remote inference without explicit approval, no private heldout prompt iteration and no release claim without patch validation evidence.

## Decision

Add a fail-closed remote inference execution candidate eval harness.

The harness validates the Step 29.17 request hash against Step 29.18, checks approval and pricing evidence, emits the exact Bedrock Runtime invocation plan and blocks execution unless every authorization check passes.

Approval and pricing evidence are external config artifacts under `configs/eval/` so the Step 29.18 generated unapproved record remains immutable evidence rather than the operational approval mechanism.

When authorized in a future run, the same harness will call Bedrock Converse once, parse the response text, extract a unified diff, validate it with `git apply --check`, apply it in a temporary git repository, run public tests and validate the candidate package against the model candidate eval contract.

## Consequence

ForgeMoE now has the controlled execution path needed for the first real remote smoke candidate eval.

The current state remains intentionally blocked: no approval, no pricing evidence, no remote inference, no local model execution, no training and no model release. This is the correct behavior until an explicit cost approval record and official pricing evidence exist.

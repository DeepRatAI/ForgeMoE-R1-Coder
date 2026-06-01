# ADR-0049 - Public Eval Remote Batch Execution v1

Status: Accepted
Date: 2026-06-01

## Context

Step 29.22 created a prepared public eval remote batch with one Bedrock Converse request per public eval task. The next risk is unsafe execution: the project needs a runnable harness, but it must not spend inference budget or mutate candidate state unless approval and pricing evidence exactly match the prepared request set.

## Decision

Add a fail-closed public eval remote batch execution harness.

The harness validates the selected model id, all per-task request hashes, the batch request hash, an explicit execution flag, approval evidence, call limits, cost limits and official pricing evidence before invoking Bedrock Runtime.

In the default state, execution is unauthorized. The doctor proves that no remote inference is invoked, no local model is used and the candidate package remains invalid/release-blocked.

If authorized in a future run, the same harness will invoke each request, parse unified diff patches, validate `git apply --check`, run public tests, run the public-suite hidden oracle and aggregate candidate metrics.

## Consequence

ForgeMoE now has the controlled execution boundary needed for real remote candidate evaluation.

This still does not satisfy model release or training-readiness requirements. Release remains blocked until a real candidate passes public eval, private heldout aggregate checks, privacy checks, provenance checks and cost controls.

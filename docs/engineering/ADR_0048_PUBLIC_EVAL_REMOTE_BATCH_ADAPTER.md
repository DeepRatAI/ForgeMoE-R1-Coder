# ADR-0048 - Public Eval Remote Batch Adapter v1

Status: Accepted
Date: 2026-06-01

## Context

Step 29.21 proved that ForgeMoE can aggregate public eval candidate behavior across six deterministic tasks. The next risk is remote execution drift: a future model candidate must be evaluated against the whole public suite, but execution must remain auditable, cost-controlled and impossible to trigger accidentally.

Local model execution is not allowed on the current hardware. Remote inference is allowed only after explicit approval and official pricing evidence.

## Decision

Add a prepared-not-executed public eval remote batch adapter.

The adapter builds one Bedrock Converse request per public eval task, stores each request hash, stores a batch request hash, records public pre-test failures and emits an execution plan. The plan is fail-closed: the generated approval record is unapproved, pricing evidence is absent and execution authorization is false.

The adapter also emits a blocked candidate package through the model candidate eval contract so future real executions can reuse the same package and reporting shape.

## Consequence

ForgeMoE now has a reproducible bridge from public eval suite to remote candidate execution without running a model or spending remote inference budget.

The next execution step can require approval over the exact model id, per-task request hashes, batch hash, token ceiling, call count and pricing evidence before invoking Bedrock Runtime.

Release remains blocked until a real model candidate produces patches, passes public eval, passes aggregate-only private heldout gates, and satisfies privacy, provenance and cost controls.

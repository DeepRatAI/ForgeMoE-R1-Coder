# ADR-0044 - Remote Inference Cost Approval Gate v1

Status: Accepted
Date: 2026-06-01

## Context

Step 29.17 prepared a reproducible Bedrock Converse request for a public smoke code task, but did not invoke remote inference. That boundary is necessary because local hardware must not run models and paid remote inference requires an explicit cost decision.

The next engineering risk is not technical request construction. It is uncontrolled execution: a prepared command could be run against the wrong model, with the wrong prompt hash, without cost bounds, without pricing evidence or without a clear audit trail.

## Decision

Add a remote inference cost approval gate before executing any paid model call.

The gate consumes the Step 29.17 request, computes a conservative token ceiling, records the selected model id, hashes the request body, writes an execution plan, writes an unapproved approval record and keeps execution blocked.

The gate requires a future approval to bind to the exact model id and request SHA-256. It also requires an official provider pricing source or billing API quote before execution.

The gate does not call Bedrock Runtime, does not load a local model, does not launch training and does not allow model release.

## Consequence

ForgeMoE now has an auditable cost and authorization boundary for the first remote candidate smoke inference.

Step 29.19 can execute remote inference only after explicit approval is recorded for the selected model, request hash, call count and cost limit. If any of those values drift, the execution step must fail closed.

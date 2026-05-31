# ADR-0043 - Remote Code-Model Candidate Smoke Eval v1

Status: Accepted
Date: 2026-05-31

## Context

Step 29.16 verified AWS remote-candidate control-plane readiness and explicitly blocked local model execution. The next requirement is to move from generic remote preflight to a code-model evaluation request that can be executed remotely.

Executing inference may incur cost and requires explicit approval. The useful progress before that approval is to make the remote request reproducible, inspectable and privacy-safe.

## Decision

Add a remote code-model candidate smoke eval harness in prepared-not-executed mode.

The harness creates a public executable bugfix task, verifies that tests fail before any patch, builds model prompt messages, selects an available Bedrock on-demand text model, emits a Bedrock Converse request body and writes the exact AWS CLI command plan.

The harness does not invoke Bedrock Runtime, does not load a local model and does not launch training. It emits an execution authorization artifact with `authorized=false`.

## Consequence

ForgeMoE now has the request and task harness required for a first remote model candidate smoke eval.

The next step can execute remote inference only after explicit approval for the selected model and cost boundary, then attach parsed patch, apply-check and test evidence to the same candidate package contract.

# ADR-0042 - Remote Candidate Smoke Preflight v1

Status: Accepted
Date: 2026-05-31

## Context

Step 29.15 proved candidate evaluation mechanics with a dry-run package. The next requirement is to move toward a real model candidate path.

The local machine must not be used for model execution because the hardware is not suitable. Running local Ollama or local Transformers would create an unreliable gate and consume the wrong execution surface.

## Decision

Step 29.16 becomes a remote candidate smoke preflight.

The preflight verifies AWS identity, S3 access, SageMaker inventory access and Bedrock foundation-model inventory access. It emits a remote execution plan and a blocked preflight candidate package under the existing Step 29.14 contract.

No local model is loaded. No local inference is executed. No remote inference is invoked. No training job is launched. No GPU or large dataset is required.

The model candidate contract is extended to recognize `bedrock_on_demand` as a remote inference runtime. Local runtimes remain represented in the broader system, but this step explicitly disallows them.

## Consequence

ForgeMoE now has a verified AWS remote-candidate control-plane gate while respecting the no-local-model constraint.

The next step can execute a remote code-model smoke eval only after explicit approval for the selected remote inference surface and expected cost.

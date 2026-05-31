# Remote Candidate Smoke Preflight v1

Step 29.16 prepares the first remote model candidate evaluation path without executing a model locally.

The user constraint is explicit: local hardware must not be used for model execution. This step therefore verifies AWS control-plane readiness, records available remote inference surfaces, emits a blocked candidate preflight package, and keeps training, release and paid inference disabled until explicit authorization.

## What It Verifies

The preflight checks:

- AWS identity is usable through the configured profile;
- the ForgeMoE S3 bucket is accessible;
- SageMaker model and endpoint inventory can be queried;
- Bedrock foundation-model inventory can be queried;
- no local model execution surface is used;
- no remote inference request is invoked;
- no training job is launched.

## What It Produces

The runner emits:

- `cloud_preflight.json`;
- `remote_execution_plan.json`;
- a blocked preflight candidate package;
- a contract validation result;
- a gate decision;
- a public-safe preflight report;
- a privacy report.

## Boundary

This is not a model-quality claim. No real model candidate is evaluated in this step.

The emitted package is intentionally blocked from release. It exists to prove that ForgeMoE can prepare a remote candidate evaluation under the same contract and privacy controls without spending compute or using local hardware.

## Next Step

Step 29.17 should execute a remote code-model candidate smoke eval only after an explicit approval for the chosen remote inference surface and expected cost.

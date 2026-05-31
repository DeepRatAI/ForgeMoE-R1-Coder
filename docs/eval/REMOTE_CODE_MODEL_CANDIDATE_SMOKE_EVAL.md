# Remote Code-Model Candidate Smoke Eval v1

Step 29.17 prepares the first remote code-model candidate smoke evaluation request without invoking remote inference.

This step exists because model execution must not use local hardware. It builds the exact public-task prompt and Bedrock Converse request artifacts needed for a remote smoke eval, but keeps execution blocked until explicit cost approval.

## What It Verifies

The doctor verifies:

- Step 29.16 remote preflight is ready;
- a public executable smoke task exists;
- public tests fail before any candidate patch;
- a Bedrock Converse request artifact can be built;
- a command plan exists but is marked `prepared_not_executed`;
- execution authorization is false;
- no local model execution is used;
- no remote inference is invoked;
- no training or model release is allowed.

## What It Produces

The runner emits:

- prompt messages for the public smoke task;
- a Bedrock Converse request body;
- an AWS CLI command plan;
- an execution authorization record;
- a public smoke pre-test result;
- a blocked candidate package;
- a candidate validation result;
- a gate decision;
- a public-safe report;
- a privacy report.

## Boundary

This is not a model-quality result. It prepares a remote candidate evaluation request but does not execute it.

The emitted package remains release-blocked because it contains no model response, no parsed patch, no `git apply --check`, no post-test evidence and no private heldout aggregate result.

## Next Step

Step 29.18 should obtain explicit authorization for remote inference cost, then execute the prepared request against the selected remote model and run patch parsing, `git apply --check`, public tests and contract validation.

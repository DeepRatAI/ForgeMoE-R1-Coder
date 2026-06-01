# Remote Inference Cost Approval Gate v1

Step 29.18 adds a cost and authorization gate before any paid remote inference is executed.

This step is intentionally non-executing. It consumes the Step 29.17 Bedrock Converse request, computes a conservative token ceiling, binds the future approval boundary to the selected model id and request hash, and writes the artifacts required to decide whether the first remote smoke inference may be executed later.

## What It Verifies

The doctor verifies:

- Step 29.17 request artifacts are ready;
- Step 29.17 did not invoke remote inference;
- Step 29.17 did not use local model execution;
- no local model runtime or Bedrock Runtime inference command is active during the gate;
- a token budget artifact exists;
- a cost approval policy exists;
- an execution plan exists but is blocked;
- an approval record exists and is not approved;
- execution authorization is false;
- no remote response is present;
- candidate evaluation is not executed;
- training and model release remain blocked;
- public-safe reports do not expose private heldout ids, patches, hidden tests or raw candidate outputs.

## What It Produces

The runner emits:

- `token_budget.json`;
- `cost_approval_policy.json`;
- `remote_inference_execution_plan.json`;
- `approval_record.json`;
- `remote_inference_cost_approval_gate_decision.json`;
- `public_safe_remote_inference_cost_approval_report.json`;
- `remote_inference_cost_approval_privacy_report.json`;
- `summary.json`.

## Approval Boundary

The approval boundary is model and request specific. A future execution step must fail closed unless all of the following are true:

- the selected model id matches the approved model id;
- the request SHA-256 matches the approved request SHA-256;
- the approved call count is at least one and not exceeded;
- the token ceiling remains within the approved budget;
- an official provider pricing source or billing API quote has been recorded;
- the user has explicitly approved the cost boundary;
- no local model runtime is used;
- no private heldout contents are present in the prompt or public report.

## Boundary

This step does not measure model quality. It does not call Bedrock Runtime, does not parse a model response, does not create a candidate patch, does not run post-patch tests and does not evaluate private heldout.

The system remains release-blocked because no real model response or patch validation evidence exists yet.

## Next Step

Step 29.19 may execute the prepared remote request only after explicit approval and pricing evidence are attached to the approval record.

The first execution step must capture provider usage, raw response, parsed patch, `git apply --check`, public post-test results, contract validation, public-safe reporting and aggregate-only private-gate handling.

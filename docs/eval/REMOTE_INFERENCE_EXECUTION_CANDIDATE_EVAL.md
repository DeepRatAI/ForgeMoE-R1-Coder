# Remote Inference Execution Candidate Eval v1

Step 29.19 adds the approved-execution harness for the first remote code-model smoke candidate evaluation.

In the current repository state the harness runs in fail-closed mode. It verifies the Step 29.17 request and Step 29.18 cost gate, checks approval and pricing prerequisites, writes the exact invocation plan and refuses to call Bedrock Runtime because approval and pricing evidence are not present.

## What It Verifies

The doctor verifies:

- Step 29.17 request artifacts are ready;
- Step 29.18 cost approval artifacts are ready;
- the request SHA-256 has not drifted;
- the execution flag is not set in the doctor;
- the approval record is not approved;
- official pricing evidence is missing and therefore required;
- execution authorization is false;
- no Bedrock Runtime call is made;
- no local model execution is used;
- no raw response or patch is present;
- the blocked candidate package is not release-eligible;
- public-safe reports do not expose private heldout ids, patches, hidden tests, raw responses or patch content.

## What It Produces

The runner emits:

- `pricing_evidence_requirement.json`;
- `execution_authorization_check.json`;
- `remote_inference_invocation_plan.json`;
- `remote_inference_response_status.json`;
- `candidate_response_parse_result.json`;
- `patch_validation_result.json`;
- `candidate_packages/remote_inference_execution_candidate.json`;
- `candidate_validation_result.json`;
- `remote_inference_execution_candidate_eval_gate_decision.json`;
- `public_safe_remote_inference_execution_candidate_eval_report.json`;
- `remote_inference_execution_privacy_report.json`;
- `summary.json`.

## Execution Boundary

The harness can execute only when all authorization checks pass:

- `FORGEMOE_EXECUTE_REMOTE_INFERENCE=1`;
- approval evidence exists in `configs/eval/remote_inference_execution_approval_v1.json`;
- approval record is approved;
- approved model id matches the selected model id;
- approved request SHA-256 matches the current request SHA-256;
- approved call count and cost are positive and within policy;
- official pricing evidence exists in `configs/eval/remote_inference_pricing_evidence_v1.json`;
- pricing evidence matches model id, request hash and region;
- estimated cost is within approval;
- token ceiling remains within policy.

The default doctor intentionally sets `FORGEMOE_EXECUTE_REMOTE_INFERENCE=0`, so this step is safe to run repeatedly without cost.

## Boundary

This step does not claim model quality in the current fail-closed state. It prepares and validates the execution path but does not invoke the remote model until approval and pricing evidence exist.

Even after a future authorized single-call smoke run, model release remains blocked until broader public eval and aggregate-only private heldout gates are satisfied.

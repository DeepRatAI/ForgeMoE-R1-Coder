# Public Eval Remote Batch Adapter v1

Step 29.22 prepares the remote public-eval batch path without executing inference.

The adapter consumes the six-task Step 29.20 public eval suite and the Step 29.21 candidate runner gate. It builds one Bedrock Converse request per public eval task, records per-task request hashes, records a batch request hash and emits a fail-closed batch execution plan.

## What It Verifies

The doctor verifies:

- the Step 29.21 public eval candidate runner is ready;
- all six public eval tasks still fail their public tests before candidate generation;
- exactly six Bedrock Converse requests are prepared;
- each request is bound to a task id and request hash;
- the batch has a batch request SHA-256;
- execution remains unauthorized without explicit approval and official pricing evidence;
- no local model execution is used;
- no remote inference is invoked;
- public-safe reports exclude prompt text, test bodies, patches, hidden-test content, raw responses and private ids.

## What It Produces

The runner emits:

- `public_eval_batch_request_manifest.json`;
- `bedrock_converse_requests/*.json`;
- `bedrock_converse_messages/*.json`;
- `public_eval_batch_pretest_results.jsonl`;
- `public_eval_remote_batch_cost_policy.json`;
- `public_eval_remote_batch_approval_record.json`;
- `public_eval_remote_batch_pricing_evidence_requirement.json`;
- `public_eval_remote_batch_authorization_check.json`;
- `public_eval_remote_batch_execution_plan.json`;
- a blocked candidate package;
- `public_safe_public_eval_remote_batch_adapter_report.json`;
- `public_eval_remote_batch_adapter_privacy_report.json`;
- `summary.json`.

## Boundary

This step does not evaluate model quality. It prepares the batch execution contract for a future approved remote model candidate.

No Bedrock Runtime call is made. No local model is loaded. No training job is launched. No model release is allowed.

## Next Step

Step 29.23 should execute this batch only after explicit approval is bound to the exact selected model id, every per-task request hash, the batch request hash, official pricing evidence and a maximum approved call and cost ceiling.

# Public Eval Remote Batch Execution v1

Step 29.23 adds the fail-closed execution harness for the public eval remote batch.

The harness consumes the Step 29.22 request manifest and can execute one Bedrock Converse call per public eval task only after explicit authorization. In the default doctor state, authorization is absent and execution is blocked.

## What It Verifies

The doctor verifies:

- Step 29.22 produced a ready request manifest;
- the selected model id is stable;
- all per-task request hashes match the prepared request files;
- the batch request hash matches the request-hash list;
- approval evidence is required and currently not approved;
- official pricing evidence is required and currently absent;
- the execution flag is off;
- no Bedrock Runtime calls are made;
- no local model execution is used;
- six response rows, parse rows and patch-validation rows are emitted in blocked state;
- candidate packaging remains invalid and release-blocked;
- public-safe reports exclude prompts, raw responses, patch content, hidden-test content and private ids.

## Future Authorized Path

When explicit approval and official pricing evidence exist, the same harness can:

- invoke Bedrock Converse for each public eval task;
- extract unified diff patches;
- validate patches with `git apply --check`;
- run public tests;
- run the public-suite hidden oracle;
- aggregate parse, public pass, hidden pass and solved-task metrics;
- package the candidate through the model candidate eval contract.

## Boundary

This step does not itself authorize paid inference. It proves the execution gate and blocks by default.

Model release remains blocked until a real candidate passes public eval, aggregate-only private heldout, privacy checks, provenance checks and cost controls.

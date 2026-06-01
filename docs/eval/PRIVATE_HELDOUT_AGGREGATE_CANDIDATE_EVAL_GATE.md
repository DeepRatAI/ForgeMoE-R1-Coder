# Private Heldout Aggregate Candidate Eval Gate v1

Step 29.24 adds a fail-closed gate for private heldout aggregate candidate evaluation.

The gate does not expose private heldout tasks. It validates only aggregate evidence and binds that evidence to the exact candidate package, public batch request hash and heldout protocol version.

## What It Verifies

The doctor verifies:

- Step 29.23 produced a candidate package;
- the heldout-aware protocol is ready;
- the private heldout seed set remains isolated;
- the candidate package SHA-256 is recorded;
- aggregate private evidence is required and currently absent;
- private task ids are not present in public outputs;
- patch content, hidden-test content, prompts and raw outputs are excluded from public reports;
- no local model execution is used;
- no remote inference is invoked by this gate;
- the candidate remains release-blocked.

## Evidence Contract

Future private aggregate evidence must live at:

```text
configs/eval/private_heldout_aggregate_candidate_eval_evidence_v1.json
```

It must include aggregate metrics only. It must not include task ids, per-task results, patch content, hidden-test content, prompts or raw model outputs.

The evidence must match:

- candidate id;
- candidate package SHA-256;
- public batch request SHA-256;
- heldout protocol version;
- private heldout task count.

## Boundary

This step does not authorize model execution, paid inference, training or release. It creates the private aggregate gate that future real candidates must pass after public eval execution.

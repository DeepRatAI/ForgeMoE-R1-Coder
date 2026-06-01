# Public Eval Suite Scaleout v1

Step 29.20 expands the public executable evaluation suite beyond the single remote smoke task.

The suite creates six deterministic public eval tasks across boundary, string, collection, parsing and iteration bug classes. Every task is built as a real temporary repository and every reference patch is generated with `git diff` from a committed baseline.

## What It Verifies

The doctor verifies:

- six public eval tasks exist;
- every task fails public tests before patching;
- every golden patch passes `git apply --check`, public tests and hidden oracle tests;
- every rejected patch fails the oracle;
- every public-overfit patch passes public tests but fails hidden oracle tests;
- every patch edits only `app/utils.py`;
- public-safe manifests contain hashes and metadata, not test bodies, hidden tests or patch contents;
- no candidate model evaluation is executed;
- no local model or remote inference is used;
- no training or model release is allowed.

## What It Produces

The runner emits:

- `public_eval_task_scores.jsonl`;
- `public_eval_oracle_results.jsonl`;
- `dataset_exports/public_eval_suite_manifest.jsonl`;
- `public_safe_public_eval_suite_report.json`;
- `public_eval_suite_privacy_report.json`;
- task repositories and oracle artifacts under `public_eval_tasks/`.

## Boundary

This step does not evaluate a model candidate. It strengthens the public evaluation surface that a future candidate must face.

Private heldout remains separate. Public-overfit hidden oracle tests are used to make the public eval tasks discriminative, but public-safe reports include only hashes and aggregate metadata.

## Next Step

Step 29.21 should wire real candidate evaluation over the expanded public eval suite, preserving aggregate-only private heldout handling and the Step 29.19 approval boundary for remote inference.

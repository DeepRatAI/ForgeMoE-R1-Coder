# Public Eval Candidate Runner Scaleout v1

Step 29.21 connects the expanded public eval suite to a candidate runner.

This is still a reference runner, not a model run. It consumes the Step 29.20 oracle results and builds three deterministic reference candidates: golden, rejected and public-overfit. The goal is to prove that the runner correctly aggregates multi-task public eval outcomes before a real remote model candidate is evaluated.

## What It Verifies

The doctor verifies:

- the Step 29.20 public eval suite is ready;
- the golden reference candidate passes the public eval gate across all six tasks;
- the rejected reference candidate fails hidden-oracle and regression-free checks;
- the public-overfit reference candidate passes public tests but is detected by hidden oracle checks;
- every reference candidate remains non-releaseable because it is not a real model candidate and no private heldout aggregate candidate result exists;
- no local model execution is used;
- no remote inference is invoked;
- public-safe reports exclude private ids, test bodies, patch contents and raw outputs.

## What It Produces

The runner emits:

- `reference_candidate_scorecards.jsonl`;
- `candidate_validation_results.jsonl`;
- reference candidate packages;
- `public_eval_candidate_runner_trace.json`;
- `public_eval_candidate_runner_gate_decision.json`;
- `public_safe_public_eval_candidate_runner_report.json`;
- `public_eval_candidate_runner_privacy_report.json`;
- `summary.json`.

## Boundary

This step proves the public eval runner, not model quality.

The model candidate contract remains release-blocked because the reference candidates are deterministic fixtures, not real model candidates, and private heldout aggregate evaluation has not run for any real candidate.

## Next Step

Step 29.22 should connect a real or approved remote candidate adapter to the expanded public eval runner, or prepare the batch adapter needed to evaluate one approved remote model call per public eval task.

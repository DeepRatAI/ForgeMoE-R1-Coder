# Oracle and Hidden-Test Gate v0

Step 29.10 turns the Step 29.9 executable micro-tasks into a formal oracle-quality gate.

The goal is not only to prove that a golden patch passes. The goal is to prove that each task can reject weak or overfit patches before any generated data is allowed to influence training.

## Inputs

The gate consumes Step 29.9 artifacts:

- task specs;
- repository snapshots;
- public tests;
- hidden tests;
- golden patches;
- rejected patches;
- train, eval and private heldout exports.

## Patch Challenges

For every task, the gate evaluates six patch classes:

- `golden`: must apply and pass public plus hidden tests.
- `rejected`: must fail public or hidden behavior.
- `semantic_noop`: changes only non-behavioral text in the expected file and must fail.
- `empty`: must fail `git apply --check` and must not solve the task.
- `wrong_file`: must apply outside the expected edit scope and must fail.
- `public_overfit`: must pass public tests but fail hidden tests.

The `public_overfit` challenge is the key hidden-test proof. A task is not accepted by this gate unless hidden tests catch a patch that satisfies the public tests.

## Scores

Each task receives:

- `oracle_strength_score`;
- `hidden_coverage_score`;
- `anti_overfit_score`;
- `edit_scope_score`.

The current scaffold requires all three Step 29.9 tasks to pass with `oracle_strength_score >= 0.95`.

## Isolation

The gate verifies that hidden tests do not appear in training exports, private heldout golden patches do not appear in training exports, and private heldout exports withhold patch paths.

## Boundary

This step does not launch training, does not require a GPU and does not download external datasets.

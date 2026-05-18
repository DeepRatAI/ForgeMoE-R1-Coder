# Agentic Trajectory Recorder v1

Step 29.11 records deterministic agentic repair trajectories from Step 29.10 gated tasks.

The goal is to move beyond static patch rows. A useful code-agent model needs examples of the workflow: read task, inspect files, run tests, try a patch, observe failure, repair, validate and select the final patch.

## Inputs

The recorder consumes:

- Step 29.9 task specs and repository snapshots;
- Step 29.10 oracle scores;
- Step 29.10 patch challenge results;
- golden patches;
- public-overfit challenge patches.

Only tasks that passed the Step 29.10 gate are recorded.

## Trajectory Shape

Each trajectory includes events for:

- reading the task;
- listing files;
- reading the target source file;
- inspecting public tests;
- running public tests;
- planning;
- generating a public-overfit patch;
- checking and applying the patch;
- seeing public pass but hidden fail;
- repairing to the golden patch;
- validating public and hidden tests;
- final answer selection.

The public-overfit attempt is intentionally negative. It creates a repair signal that teaches the future model not to overfit visible tests.

## Exports

Train split exports:

- `trajectory_sft_train.jsonl`;
- `repair_trace_train.jsonl`;
- `trajectory_preference_train.jsonl`.

Eval and private heldout trajectories are exported separately and are not training rows.

## Privacy

The recorder stores hidden-test hashes and hidden-test outcomes, not hidden-test contents in training exports. It also runs a local secret scan over generated trajectory outputs.

This step does not train a model, launch a GPU job or download external datasets.

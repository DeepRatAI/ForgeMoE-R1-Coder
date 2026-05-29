# Heldout-Aware Eval Protocol v1

Step 29.13 formalizes how ForgeMoE can use train, eval and private heldout signals without contaminating future training.

This step is intentionally a protocol gate, not a model-quality claim. It proves that the private seed set can be used as an aggregate final gate while keeping private task contents out of optimization loops.

## Split Policy

Train split:

- may be used for training rows;
- may be used for prompt or pipeline iteration;
- may expose patch content.

Eval split:

- may be used for model selection;
- must not be used for training;
- must not be used for repeated prompt iteration.

Private heldout split:

- must not be used for training;
- must not be used for prompt iteration;
- must not expose patch or hidden-test content;
- must report only aggregate public-safe metrics.

## Reference Candidates

The protocol evaluates three reference candidate classes from existing oracle artifacts:

- `oracle_reference_golden`: the expected upper-bound reference;
- `oracle_reference_public_overfit`: a canary that passes public tests but must fail hidden tests;
- `oracle_reference_rejected`: a negative canary that must fail the private gate.

These are not model candidates. They exist to prove the gate behaves correctly before real candidate evaluation is allowed.

## Public-Safe Reporting

The public-safe report excludes:

- private task ids;
- private patch content;
- hidden-test source;
- task-level private results.

It may include aggregate counts, pass rates and overfit-detection counts.

## Training Boundary

This step does not authorize training or release. It establishes the heldout-aware contract needed before a real model candidate eval contract can be added.

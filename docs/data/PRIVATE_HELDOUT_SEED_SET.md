# Private Heldout Seed Set v1

Step 29.12 creates the first dedicated private heldout seed set.

The purpose is not to increase training data. The purpose is to create a protected evaluation seed with executable tasks that can later detect overfitting, contamination and weak generalization.

## Contract

The seed set contains only `private_heldout` tasks. They are marked `never_train_on=true` and must not be exported into any training row.

Each task includes:

- a repository snapshot;
- public tests that fail before the patch;
- hidden tests that add behavioral signal;
- a golden patch generated with `git diff` from a temporary git repository;
- a rejected patch;
- a public-overfit patch that passes public tests and fails hidden tests;
- a public-safe manifest row with hashes only.

## Generated Families

The current seed set covers three micro families:

- boundary condition bugfix;
- string normalization bugfix;
- collection semantics bugfix.

This is still a scaffold-scale seed set. Its value is the enforceable isolation and validation contract, not dataset size.

## Isolation

The doctor scans existing Step 29.9 and Step 29.11 training exports and asserts that no private task id, private patch content or private hidden-test content appears in training rows.

The public-safe manifest exports hashes and metadata only. It does not include patch content or hidden-test source.

## Cost Boundary

This step does not train a model, launch a GPU job or download external datasets.

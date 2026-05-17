# Internal Synthetic Micro-Generator v0

Step 29.9 implements the first deterministic executable micro-generator for ForgeMoE.

It creates three single-file bugfix tasks:

- one train task;
- one eval task;
- one private heldout task.

Each task includes:

- a generated repository snapshot;
- public tests;
- hidden tests;
- a golden patch;
- a rejected patch;
- executable verification;
- provenance metadata;
- split metadata.

The train split exports seed rows for:

- patch SFT;
- trajectory SFT;
- preference pairs.

The private heldout task is not exported to training rows. Its patch reference is withheld from training exports.

This is not final training-grade scale. It is the first executable generator scaffold that validates the data-engine contract.

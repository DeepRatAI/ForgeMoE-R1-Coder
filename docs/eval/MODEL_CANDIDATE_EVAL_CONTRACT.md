# Model Candidate Eval Contract v1

Step 29.14 defines the package a real model candidate must submit before ForgeMoE can evaluate it against public eval and private heldout gates.

This step does not evaluate a real model. It defines and tests the contract that future real model evaluations must satisfy.

## Required Sections

Candidate packages must include:

- candidate identity;
- model metadata;
- run provenance;
- generation config;
- eval scope;
- aggregate metrics;
- privacy attestation;
- cost profile.

## Required Metrics

The contract requires at least:

- raw response count;
- parsed candidate count;
- parse failure count;
- parse validity rate;
- public eval task count;
- public eval solve rate;
- private heldout task count;
- private heldout pass rate;
- public overfit detection rate;
- regression-free patch rate.

## Release Gates

The initial scaffold thresholds are intentionally conservative:

- parse validity rate at least `0.95`;
- public eval solve rate at least `0.80`;
- private heldout pass rate at least `0.80`;
- public overfit detection rate exactly `1.0`;
- regression-free patch rate at least `0.95`.

These thresholds do not assert frontier-level quality. They define the minimum package quality before a candidate could even be considered for a later release gate.

## Privacy Boundary

Candidate packages must attest that private heldout was not used for training or prompt iteration. Public reports must not contain private task ids, private patch content or private hidden-test content.

## Current Scope

The doctor validates one structurally valid fixture and rejects fixtures with private leakage, weak metrics and missing provenance.

No training, GPU job, release or large dataset download is authorized by this step.

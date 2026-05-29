# ADR-0040 - Model Candidate Eval Contract v1

Status: Accepted
Date: 2026-05-29

## Context

Step 29.13 established a heldout-aware evaluation boundary, but the project still needs a formal interface for future real model candidates.

Without a candidate package contract, model runs could be hard to reproduce, hard to compare, or contaminated by private heldout feedback.

## Decision

Add a model candidate eval contract and doctor.

The contract requires candidate identity, model metadata, run provenance, generation config, eval scope, aggregate metrics, privacy attestation and cost profile. It also defines minimum scaffold release thresholds for parse validity, public eval solve rate, private heldout pass rate, public-overfit detection and regression-free patch rate.

The doctor validates fixture packages: one structurally valid fixture passes the contract but remains release-ineligible because it is not a real model candidate; fixtures with private leakage, weak metrics and missing provenance are rejected.

## Consequence

ForgeMoE now has a reproducible package boundary for future candidate evaluations.

This prepares the next step: a dry-run candidate eval runner that can emit real candidate packages without training or release.

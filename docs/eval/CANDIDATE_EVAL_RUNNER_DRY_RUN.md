# Candidate Eval Runner Dry Run v1

Step 29.15 creates the first candidate evaluation runner output without evaluating a real model.

The goal is to prove the mechanics of producing, validating and reporting a candidate package under the Step 29.14 contract while preserving the heldout-aware boundary from Step 29.13.

## What It Produces

The dry run emits:

- a candidate package;
- a contract validation result;
- a candidate eval trace;
- a gate decision;
- a public-safe candidate eval report;
- a privacy report.

## Boundary

The candidate is explicitly not a real model candidate. It can pass the package contract structurally, but it must remain release-blocked.

Private heldout remains aggregate-only. Public reports must not include private task ids, private patch content or private hidden-test content.

## Why This Matters

Future model evaluations need a reproducible package format before they can be compared, promoted, trained from or rejected. This dry run verifies the package and report path without spending GPU budget or claiming model quality.

## Cost Boundary

This step does not train a model, launch a GPU job, release a model or download external datasets.

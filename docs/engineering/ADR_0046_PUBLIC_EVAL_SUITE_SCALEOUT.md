# ADR-0046 - Public Eval Suite Scaleout v1

Status: Accepted
Date: 2026-06-01

## Context

Step 29.19 created a controlled execution path for the first remote inference smoke eval, but a single smoke task is not enough evidence for a SOTA coding-agent pipeline.

Before accepting any candidate result, ForgeMoE needs a broader public executable eval surface with multiple behavioral axes, oracle checks and public-overfit detection.

## Decision

Add a deterministic public eval suite scaleout gate.

The suite creates six public executable tasks across six task families. Each task includes a failing public test, hidden oracle tests, a golden patch, a rejected patch and a public-overfit patch. Patches are generated with `git diff` from real temporary repositories with committed baselines.

The gate requires golden patches to pass public and hidden tests, rejected patches to fail, and public-overfit patches to pass public tests while failing hidden oracle tests.

## Consequence

ForgeMoE now has a stronger public evaluation target for future model candidates.

This still does not prove model quality: no model candidate is run in this step. It prepares the next candidate runner to evaluate against multiple public executable tasks instead of a single smoke case.

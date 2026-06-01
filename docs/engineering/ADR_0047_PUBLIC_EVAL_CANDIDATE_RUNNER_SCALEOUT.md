# ADR-0047 - Public Eval Candidate Runner Scaleout v1

Status: Accepted
Date: 2026-06-01

## Context

Step 29.20 expanded public executable eval coverage to six verified tasks. The next risk is incorrectly aggregating public eval outcomes or accepting a public-overfit candidate as solved.

Before running a real remote candidate over the suite, the candidate runner must prove that it distinguishes golden, rejected and public-overfit patch suites across all public eval tasks.

## Decision

Add a reference public eval candidate runner.

The runner consumes Step 29.20 oracle outputs and builds three deterministic reference candidates: golden, rejected and public-overfit. It aggregates parse validity, public solve rate, hidden oracle pass rate, public-overfit detection rate and regression-free patch rate.

The runner also validates each reference package against the model candidate eval contract and keeps release blocked because no package is a real model candidate and no private heldout aggregate result exists.

## Consequence

ForgeMoE can now evaluate candidate-like patch suites across the expanded public eval set without running models.

The next step can attach a real remote candidate adapter to this runner. Any release claim remains blocked until a real candidate passes public eval, aggregate-only private heldout, privacy checks and cost/provenance gates.

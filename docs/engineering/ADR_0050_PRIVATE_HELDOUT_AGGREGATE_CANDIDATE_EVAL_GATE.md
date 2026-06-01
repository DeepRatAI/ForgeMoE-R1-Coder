# ADR-0050 - Private Heldout Aggregate Candidate Eval Gate v1

Status: Accepted
Date: 2026-06-01

## Context

Step 29.23 can produce a public eval candidate package, but release decisions cannot trust candidate self-attestation or public eval alone. ForgeMoE needs a boundary that can accept private heldout evidence without leaking private tasks or turning the private set into a prompt-iteration tool.

## Decision

Add a fail-closed private heldout aggregate candidate eval gate.

The gate requires independent aggregate evidence bound to the exact candidate package SHA-256, candidate id, public batch request hash, heldout protocol version and private heldout task count.

Evidence is rejected unless it is aggregate-only. Task ids, task-level results, patch content, hidden-test content, prompts and raw model outputs are disallowed from public artifacts.

In the current state, no aggregate evidence exists and the Step 29.23 candidate is not a real executed model candidate. The gate therefore blocks training and release.

## Consequence

ForgeMoE now has a strict private aggregate release boundary after public eval.

This still does not make the system training-ready or model-release-ready. A future real candidate must first execute authorized public eval, then produce valid aggregate-only private heldout evidence, then pass the model candidate contract and privacy scans.

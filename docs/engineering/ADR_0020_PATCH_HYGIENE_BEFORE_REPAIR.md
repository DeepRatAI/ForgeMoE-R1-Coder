# ADR-0020 — Patch Hygiene Before Patch Repair

Status: Accepted
Date: 2026-05-14

## Context

Step 21 showed that Qwen2.5-Coder 0.5B can target the right file under a stricter prompt contract, but still emits non-applicable diff-like text.

The observed outputs include Markdown fence leakage, explanatory prose, and hunks with no real plus/minus replacement lines. Git rejects these outputs as corrupt patches.

## Decision

Introduce a Patch Hygiene / Diff Validity Layer before patch repair, reranking, training, or RL.

This layer classifies model output into explicit validity states:

- missing_diff
- empty_after_sanitization
- non_actionable_no_change_lines
- sanitized_actionable_with_contamination
- actionable_diff_like

## Consequence

Step 22 does not solve tasks. It creates instrumentation for Step 23, where we should move from raw diff generation to structured edit intent and canonical patch construction.

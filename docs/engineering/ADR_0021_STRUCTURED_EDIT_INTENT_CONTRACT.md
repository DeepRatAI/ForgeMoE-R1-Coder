# ADR-0021 — Structured Edit Intent Contract

Status: Accepted
Date: 2026-05-14

## Context

Step 22 showed that raw diff generation is the wrong interface for the current small model. The model emits diff-like text, but the output is non-actionable: Markdown leakage, prose leakage, and no real change lines.

## Decision

Introduce a Structured Edit Intent contract.

Instead of asking the model to emit a raw patch, the system can ask for a constrained JSON object:

```json
{
  "intent_id": "string",
  "task_id": "string",
  "file_path": "app/utils.py",
  "find_text": "exact old code",
  "replace_text": "exact new code",
  "rationale": "brief reason"
}
```

The system validates the intent and deterministically builds a canonical unified diff.

## Rationale

Raw patch generation combines three tasks:

1. bug localization
2. code edit synthesis
3. exact unified-diff formatting

Small models may partially solve 1 and 2 while failing 3. A structured intent interface removes avoidable formatting failure from the model boundary.

## Consequence

Future SFT and RL data should prefer structured edit intents as an intermediate representation. Canonical patches remain system-generated and verifier-tested.

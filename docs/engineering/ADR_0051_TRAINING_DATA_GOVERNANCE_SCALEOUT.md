# ADR-0051 - Training Data Governance Scaleout v1

Status: Accepted  
Date: 2026-06-01

## Context

ForgeMoE now has deterministic internal synthetic tasks, agentic trajectories, public eval scaleout and private heldout gates. Those artifacts create useful data rows, but the project must not treat any generated row as training-grade merely because it is executable or internally generated.

The project needs an operational row-level gate that distinguishes scaffold data from data that may be used to train a model.

## Decision

Add a fail-closed training data governance scaleout gate.

The gate inventories current dataset exports, evaluates every row against split, never-train, private-heldout, secret, provenance, contamination and oracle-quality checks, and emits aggregate-safe reports.

Rows from the train split may be admitted only as scaffold data for schema and tooling validation. No row is currently admitted as training-grade because complete license/provenance evidence, completed contamination checks and row-level training-quality certification are not yet present.

Private heldout and eval rows are rejected for training use. Public reports exclude raw rows, private identifiers, patch content, withheld-eval content, prompts and model outputs.

## Consequence

Training remains blocked, but the block is now explicit and auditable at row level.

Future work can scale generators safely only after canonical row schemas, completed contamination checks, provenance policy and oracle-quality certification are implemented.

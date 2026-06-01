# ADR-0052 - Training Data Schema Normalization and Scaleout Plan v1

Status: Accepted  
Date: 2026-06-01

## Context

Step 29.25 created row-level governance and proved that current internal rows are scaffold-only, not training-grade. The next risk is scaleout without a canonical schema contract. If generator output grows before schemas, provenance, contamination and oracle references are locked, the project would accumulate unreviewable data debt.

## Decision

Add a fail-closed schema normalization and generator scaleout plan.

The gate defines canonical schemas for patch SFT, trajectory SFT, preference pairs, repair traces and executable task references. It maps every current source schema to a canonical data product and emits only manifest-reference scaffold rows.

The gate also defines the required scaleout phases: schema lock, provenance/license registry, contamination/dedup scanners, oracle-quality certification and bounded generator scaleout dry run.

No row is promoted to training-grade. No training job, local model execution, remote inference or large external dataset download is allowed.

## Consequence

ForgeMoE now has a public-safe schema contract for future data generation. The next implementation work should build provenance, license and contamination scanners so rows can eventually become training-grade under evidence, not assumption.

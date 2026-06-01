# ADR-0053 - Provenance, License and Contamination Scanner v1

Status: Accepted  
Date: 2026-06-01

## Context

Step 29.26 defined canonical data product schemas and a generator scaleout plan. The next blocker is executable evidence for provenance, license status and contamination boundaries. Documentation alone is not enough to make rows training-grade.

## Decision

Add a fail-closed provenance, license and contamination scanner.

The scanner reads current governed rows, emits provenance scan results, license scan results, contamination scan results, scanner decisions and a hash-only fingerprint index. It checks that train rows do not overlap with known eval/private identifiers while keeping private identifiers out of public artifacts.

The current license policy is scaffold-only. Public benchmark scanning and near-duplicate scanning remain incomplete by design. Therefore zero rows pass training-grade release.

## Consequence

ForgeMoE now has executable evidence for the first provenance/license/contamination layer. The next gate should implement deduplication and near-duplicate scanning before any bounded generator scaleout can be treated as training-grade.

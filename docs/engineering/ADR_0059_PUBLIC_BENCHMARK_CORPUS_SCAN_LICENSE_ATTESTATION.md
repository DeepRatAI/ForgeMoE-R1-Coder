# ADR-0059: Public Benchmark Corpus Scan and License Attestation

## Status

Accepted.

## Context

Step 29.32 certified hardened executable task oracles and integrated a data-release policy. The remaining blockers were public benchmark corpus scanning, license/provenance policy and training payload materialization.

The project has permission to use remote network access and bounded downloads when justified, but the budget is small and public benchmark content must never leak into training payloads.

## Decision

Add Step 29.33 as an official-source metadata and license attestation gate.

The gate verifies public benchmark metadata from official Hugging Face dataset APIs and GitHub repository license APIs where available. It records the observed license evidence, keeps all public benchmarks reference/eval-only and emits a plan for later full corpus snapshot fingerprinting.

For the Forge-native hardened train candidates, the gate records that they are internally generated synthetic tasks and do not use raw public benchmark content, external repository snapshots or private heldout content. This upgrades their license basis beyond scaffold-only while keeping training payload materialization blocked.

## Rationale

License attestation and full corpus contamination scanning are related but distinct. It is correct to resolve the internal synthetic-task license blocker without pretending that full public benchmark corpora have already been downloaded and fingerprinted.

This keeps the project moving while preserving the evidence standard required for SOTA data governance.

## Consequences

Positive:

- official metadata is verified for all twelve benchmark registry entries;
- public benchmarks remain never-train-direct;
- Forge-native train candidates receive an internal generated-task license attestation;
- release-policy progress is measurable: eight requirements pass, two remain blocked;
- no raw public benchmark content is exposed in public reports.

Negative:

- training-grade release remains blocked;
- full public benchmark snapshot fingerprinting still requires a dedicated bounded materialization step;
- some benchmark datasets expose ambiguous or missing dataset-license metadata and must remain reference/eval-only.

## Validation

```text
./scripts/dev/step29_33_doctor.sh
STEP29_33_DOCTOR_OK
```

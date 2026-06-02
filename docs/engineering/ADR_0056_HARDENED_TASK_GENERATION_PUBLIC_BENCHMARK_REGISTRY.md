# ADR-0056: Hardened Task Generation and Public Benchmark Registry

## Status

Accepted.

## Context

Step 29.29 closed the task-family bundle and oracle-quality gate, but it left the training release blocked for legitimate reasons: eval/private scaffolds are still too similar, public benchmark contamination scanning is incomplete, license policy remains scaffold-only and the final release policy is not integrated.

The next data step must not generate more toy tasks. It needs a stronger task-generation contract and an explicit registry for public benchmarks that must be treated as reference/eval-only until full contamination scanning exists.

## Decision

Add a fail-closed hardened task-generation and public benchmark registry gate.

The gate:

- seeds a versioned public benchmark contamination registry;
- marks benchmark families as reference/eval-only and never direct training sources;
- creates a hash-only current reference index;
- defines hardened task-generation blueprints across train, eval, private-heldout and public-eval splits;
- checks exact collisions and high-level hash/token similarity against current references and the registry;
- blocks training-grade release until full public benchmark corpora are downloaded, fingerprinted and scanned by a later gate.

## Consequences

ForgeMoE now has an auditable bridge from toy-scale scaffolds toward harder executable task generation. The project can proceed to build real temporary-repo tasks without weakening private heldout isolation or making unsupported contamination-safety claims.

This gate does not download benchmark corpora, execute local models, invoke remote inference, launch training or release data.

## Validation

The gate is validated by:

```text
./scripts/dev/step29_30_doctor.sh
```

Expected terminal marker:

```text
STEP29_30_DOCTOR_OK
```

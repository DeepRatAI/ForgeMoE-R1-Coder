# Hardened Task Generation and Public Benchmark Contamination Registry

Step 29.30 adds the first executable gate for hardened task-generation planning and public benchmark contamination registry control.

The gate does not train, run a model, download benchmark corpora or ingest raw public benchmark tasks. It creates a versioned registry of public benchmark families that must remain reference/eval-only, builds a hash-only index of current public/eval/private/training references and defines hardened task blueprints for the next executable generator.

## Current Result

```text
STEP29_30_DOCTOR_OK
benchmark_registry_entry_count >= 10
current_public_eval_reference_count = 6
hardened_blueprint_count = 12
hardened_train_blueprint_count = 4
hardened_eval_blueprint_count = 3
hardened_private_heldout_blueprint_count = 3
hardened_public_eval_blueprint_count = 2
public_benchmark_registry_ready = true
hardened_generation_plan_ready = true
exact_current_reference_collision_count = 0
exact_public_benchmark_registry_collision_count = 0
high_current_private_or_eval_reference_similarity_count = 0
high_public_benchmark_registry_similarity_count = 0
hardened_eval_private_high_similarity_pair_count = 0
full_public_benchmark_corpus_scan_complete = false
training_grade_data_release_allowed = false
training_launch_allowed = false
model_release_allowed = false
local_model_execution_used = false
remote_inference_invoked = false
```

## Why The Gate Remains Closed

The gate is intentionally fail-closed. It proves that ForgeMoE has a benchmark registry and a hardened-generation plan, but it does not claim full contamination safety.

Remaining blockers:

- raw public benchmark corpora have not been downloaded or scanned;
- license policy is still scaffold-only;
- executable hardened task repositories have not been generated yet;
- the final training-grade release policy is not integrated;
- Step 29.29's existing eval/private scaffold similarity remains a historical blocker until replaced by stronger tasks.

## Hardened Blueprint Contract

Each blueprint requires future tasks to use:

- real temporary Git repositories;
- `git diff` patches;
- `git apply --check`;
- pre-test failure;
- post-public pass;
- post-hidden pass;
- public-overfit, wrong-file and semantic-noop negative checks.

The blueprints are metadata only. They do not export prompts, hidden tests, patches or private identifiers.

## Artifacts

```text
results/local/hardened_task_generation_public_benchmark_registry_v1/summary.json
results/local/hardened_task_generation_public_benchmark_registry_v1/public_benchmark_registry.json
results/local/hardened_task_generation_public_benchmark_registry_v1/current_public_eval_reference_index.json
results/local/hardened_task_generation_public_benchmark_registry_v1/hardened_task_blueprints.json
results/local/hardened_task_generation_public_benchmark_registry_v1/hardened_task_blueprints.jsonl
results/local/hardened_task_generation_public_benchmark_registry_v1/hardened_generation_similarity_report.json
results/local/hardened_task_generation_public_benchmark_registry_v1/benchmark_contamination_gate_decision.json
results/local/hardened_task_generation_public_benchmark_registry_v1/public_safe_hardened_generation_benchmark_registry_report.json
results/local/hardened_task_generation_public_benchmark_registry_v1/hardened_generation_benchmark_registry_privacy_report.json
```

## Public Safety Contract

The public-safe report contains counts and gate states only. It excludes raw rows, raw text, raw benchmark tasks, private identifier values, patch content, prompts, withheld-eval content and model outputs.

## Next Step

```text
Step 29.31 - hardened executable task generator v1
```

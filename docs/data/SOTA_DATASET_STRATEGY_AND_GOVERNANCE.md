# SOTA Dataset Strategy, Governance & Acquisition Plan v0

## North Star

Crear un sistema de AI Engineering SOTA capaz de tomar modelos de codigo aproximadamente 7B / 9B / 14B y transformarlos en agentes autonomos de codigo y desarrollo fullstack e2e capaces de competir codo a codo con modelos frontera/titanes como Opus serie 4, ChatGPT serie 5.x, Gemini Pro, DeepSeek V-series y equivalentes futuros.

## Critical classification

The current synthetic datasets from Step 29.2 and Step 29.5 are classified as:

```text
scaffold / plumbing / format-validation data
```

They are useful for contracts, manifests, tokenization, reproducibility and pipeline validation.

They are not the final training-grade corpus required for the project objective.

## Required data layers

### source_code_corpus

- Purpose: `continued pretraining or domain adaptation substrate`
- Status: `not_acquired`
- Required gates: `license, provenance, dedup, pii_secret_filter, malware_filter`

### instruction_code_tasks

- Purpose: `teach direct code transformation and structured compliance`
- Status: `scaffold_started`
- Required gates: `schema_validation, quality_scoring, dedup`

### repository_level_issue_tasks

- Purpose: `train and evaluate repo-scale software engineering behavior`
- Status: `not_acquired`
- Required gates: `reproducible_environment, oracle_tests, license, contamination`

### synthetic_executable_tasks

- Purpose: `produce controllable verified tasks at scale`
- Status: `scaffold_started`
- Required gates: `execution_oracle, difficulty_balance, anti_template_overfit`

### agentic_trajectories

- Purpose: `teach inspect-plan-edit-test-repair loops`
- Status: `partially_scaffolded`
- Required gates: `trace_schema, privacy_filter, reward_attribution`

### preference_pairs

- Purpose: `support DPO or equivalent preference optimization`
- Status: `not_ready`
- Required gates: `pair_quality, reward_margin, verifier_consistency`

### hidden_eval_holdout

- Purpose: `measure true agentic capability without benchmark contamination`
- Status: `not_built`
- Required gates: `strict_isolation, no_train_overlap, strong_oracle`


## Dataset quality dimensions

Every candidate source or generated row must be scored against:

- `license_and_terms_acceptability`
- `provenance_traceability`
- `deduplication_strength`
- `contamination_risk`
- `execution_verifiability`
- `task_difficulty_signal`
- `multi_file_reasoning_value`
- `agentic_trace_value`
- `negative_example_value`
- `hidden_test_strength`
- `format_contract_compliance`
- `security_and_privacy_risk`

## Candidate dataset classes

### large_code_corpora

- Role: `possible continued pretraining substrate`
- Position: `candidate_only_until_license_provenance_filtering`
- Examples: `The Stack style corpora, Software Heritage derived corpora, permissive-code subsets`

### repo_issue_benchmarks

- Role: `evaluation and task inspiration`
- Position: `eval_reference_not_blind_training_source`
- Examples: `SWE-bench style tasks, SWE-bench Verified style tasks, SWE-bench Live style tasks`

### synthetic_repo_task_generators

- Role: `task generation methodology reference`
- Position: `high_priority_direction_to_reimplement_and_improve`
- Examples: `SWE-smith style task synthesis, internal Forge task generator`

### competitive_programming_and_code_reasoning

- Role: `algorithmic reasoning auxiliary signal`
- Position: `auxiliary_not_primary_for_fullstack_agentic_e2e`
- Examples: `LiveCodeBench style tasks, BigCodeBench style tasks, HumanEval/MBPP sanity checks`


## Training mixture draft

The system will not use a single undifferentiated dataset. Training data must be staged:

1. Scaffold validation.
2. Structured intent SFT.
3. Patch generation SFT.
4. Trajectory SFT.
5. Preference optimization.
6. Verifiable RL.

Each stage must have its own manifest, quality gate, split policy and evaluation gate.

## Contamination policy

Public benchmarks must not be treated as ordinary training data.

Benchmark-like tasks require:

- provenance metadata;
- timestamp metadata;
- deduplication against train data;
- similarity checks;
- heldout isolation;
- explicit train/eval boundary records.

## Legal and provenance policy

No large-scale source should be ingested into training until its license, terms, provenance, PII risk, secret risk and malware risk are evaluated.

## Evaluation policy

Model promotion requires improvement against:

- internal ForgeEval tasks;
- repository-level heldout tasks;
- patch application metrics;
- post-test pass metrics;
- hidden-test pass metrics;
- repair success;
- cost per solved task;
- latency per solved task;
- agentic e2e solve rate.

Training loss alone is never sufficient.

## Next engineering step

The next step should be a data-source matrix and acquisition gate implementation, not GPU training.

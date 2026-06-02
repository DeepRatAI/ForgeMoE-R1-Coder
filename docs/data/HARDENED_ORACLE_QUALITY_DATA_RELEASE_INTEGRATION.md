# Hardened Oracle Quality and Data Release Integration

Step 29.32 integrates the Step 29.31 hardened executable tasks into the training-data release system.

This step is not a training launch. It is the gate that decides whether the newly generated hardened tasks are eligible for training-grade release. The current result is intentionally split:

- the hardened task oracles are certified;
- the train split becomes an oracle-certified train-candidate set;
- training-grade release remains blocked until public benchmark corpus scanning, license/provenance attestation and payload materialization authorization are complete.

## Current Result

```text
STEP29_32_DOCTOR_OK
task_count = 12
oracle_certified_task_count = 12
train_oracle_certified_task_count = 4
oracle_certified_train_candidate_count = 4
training_grade_candidate_after_step29_32_count = 0
release_policy_passed_requirement_count = 6
release_policy_failed_requirement_count = 3
training_grade_data_release_allowed = false
training_launch_allowed = false
model_release_allowed = false
```

## Certification Contract

Every hardened task must pass all certification checks:

- temporary Git repository evidence exists;
- patch format is `git diff`;
- golden patch passes `git apply --check`;
- public tests fail before the patch;
- public tests pass after the golden patch;
- hidden tests pass after the golden patch;
- the golden patch edits the expected multi-file scope;
- the challenge matrix includes golden, rejected, public-overfit, wrong-file and semantic-noop patches;
- rejected, wrong-file and semantic-noop patches do not solve the task;
- public-overfit patches pass public tests but fail hidden tests;
- artifacts avoid raw private identifier flags.

The minimum oracle strength score is 1.0 for this gate.

## Release Policy

Step 29.32 integrates the following release requirements:

- hardened executable tasks are verified;
- train split tasks are oracle certified;
- train split is isolated from eval, private-heldout and public-eval task hashes;
- no exact current-reference collision is present;
- no high-similarity current private/eval reference is present;
- no exact public benchmark registry collision is present;
- full public benchmark corpus scan is complete;
- license policy is upgraded beyond scaffold-only;
- training payload materialization is authorized.

The first six requirements pass in the current state. The final three remain blocking.

## Release Classes

Current row decisions are hash-only and use two release classes:

- `oracle_certified_train_candidate_blocked` for train split tasks that have certified oracles but cannot yet be released as training-grade;
- `never_train_eval_or_heldout_reference` for eval, private-heldout and public-eval tasks.

No raw patches or hidden tests are materialized into training payloads by this step.

## Artifacts

```text
results/local/hardened_oracle_quality_data_release_integration_v1/summary.json
results/local/hardened_oracle_quality_data_release_integration_v1/hardened_oracle_quality_certifications.jsonl
results/local/hardened_oracle_quality_data_release_integration_v1/hardened_data_release_decisions.jsonl
results/local/hardened_oracle_quality_data_release_integration_v1/hardened_split_isolation_report.json
results/local/hardened_oracle_quality_data_release_integration_v1/hardened_training_release_policy.json
results/local/hardened_oracle_quality_data_release_integration_v1/hardened_oracle_quality_report.json
results/local/hardened_oracle_quality_data_release_integration_v1/hardened_oracle_quality_data_release_gate_decision.json
results/local/hardened_oracle_quality_data_release_integration_v1/public_safe_hardened_oracle_quality_data_release_report.json
results/local/hardened_oracle_quality_data_release_integration_v1/hardened_oracle_quality_data_release_privacy_report.json
```

## Public Safety Contract

The public-safe report excludes raw task IDs, raw rows, raw task text, patch content, hidden-test content, private identifier values and model outputs. It reports only aggregate counts, release classes and blocker counts.

## Next Step

```text
Step 29.33 - public benchmark corpus scan and license attestation v1
```

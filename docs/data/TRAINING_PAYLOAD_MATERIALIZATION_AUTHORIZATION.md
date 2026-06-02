# Training Payload Materialization Authorization

Step 29.36 authorizes and materializes the first Forge-native training-grade patch SFT payload.

The gate admits only internally generated, oracle-certified train split tasks after license attestation and full public benchmark corpus fingerprinting have passed. It excludes eval, private-heldout and public-eval tasks from training. Hidden tests remain validation-only evidence and are not exported into training payload rows.

## Current Result

```text
STEP29_36_DOCTOR_OK
authorized_train_candidate_count = 4
materialized_training_payload_row_count = 4
excluded_non_train_task_count = 8
payload_hidden_test_export_count = 0
payload_negative_patch_export_count = 0
payload_validation_pass_count = 4
training_payload_materialization_authorized = true
training_grade_data_release_allowed = true
training_launch_allowed = false
model_release_allowed = false
```

## Method

The gate requires:

- hardened executable tasks verified;
- train split oracle certification;
- train/eval/private/public-eval split isolation;
- Forge-internal synthetic-task license attestation;
- full public benchmark corpus scan complete;
- zero exact full public benchmark corpus collisions;
- payload validation with real git repos, `git apply --check`, pre-public failure, post-public pass and post-hidden pass;
- no hidden test or negative patch export into training rows.

The materialized payload is `patch_sft_messages_jsonl`: each row contains an instruction, repo-before file contents, public tests, validation command and target git diff patch. Hidden tests are used only to validate the row and are represented in non-training artifacts by hashes and validation counters.

## Release State

Training-grade data release is allowed for the four materialized Forge-native train rows.

Training execution and model release remain separate gates. Step 29.36 authorizes data materialization; it does not launch a training job and does not approve a model release.

## Artifacts

```text
results/local/training_payload_materialization_authorization_v1/summary.json
results/local/training_payload_materialization_authorization_v1/training_payload_authorization_decisions.jsonl
results/local/training_payload_materialization_authorization_v1/payload_validation_results.jsonl
results/local/training_payload_materialization_authorization_v1/payload_split_isolation_report.json
results/local/training_payload_materialization_authorization_v1/training_release_policy_v2.json
results/local/training_payload_materialization_authorization_v1/training_payload_materialization_gate_decision.json
results/local/training_payload_materialization_authorization_v1/public_safe_training_payload_materialization_report.json
results/local/training_payload_materialization_authorization_v1/training_payload_materialization_privacy_report.json
results/local/training_payload_materialization_authorization_v1/dataset_exports/patch_sft_training_payload.jsonl
results/local/training_payload_materialization_authorization_v1/dataset_exports/patch_sft_training_payload_manifest.jsonl
```

## Next Step

```text
Step 29.37 - training payload schema quality and tokenization gate v1
```

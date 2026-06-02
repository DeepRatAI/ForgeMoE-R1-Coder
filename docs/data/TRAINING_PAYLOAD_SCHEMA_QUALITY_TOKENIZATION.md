# Training Payload Schema Quality and Tokenization Gate

Step 29.37 validates the authorized Step 29.36 patch SFT payload before any training job can consume it.

The gate checks schema, manifest consistency, payload hashes, hidden-test exclusion, negative-patch exclusion, canonical SFT rendering and deterministic conservative token-budget estimates. It does not pretend that a model-specific tokenizer is available when the local environment does not provide one.

## Current Result

```text
STEP29_37_DOCTOR_OK
source_payload_row_count = 4
schema_valid_row_count = 4
manifest_consistent_row_count = 4
token_budget_proxy_pass_count = 4
would_truncate_proxy_count = 0
hidden_test_content_leak_count = 0
negative_patch_content_leak_count = 0
training_payload_schema_quality_passed = true
token_budget_proxy_gate_passed = true
model_specific_tokenizer_validation_passed = false
training_launch_allowed = false
model_release_allowed = false
```

## Method

The gate:

- validates every row against the patch SFT payload schema;
- recomputes payload ids, prompt hashes, target patch hashes and manifest hashes;
- renders canonical chat-style SFT text;
- computes deterministic token proxy counts using the maximum of regex code-token count and `ceil(character_count / 3)`;
- confirms every row fits the configured proxy max sequence length;
- confirms hidden tests and negative patches are not present in the payload;
- writes public-safe aggregate reports without raw payload content.

The proxy estimate is conservative enough for local planning, but it is not a substitute for model-specific tokenizer validation. The next gate must select or install a tokenizer-only path for the target base model and run tokenizer-specific validation before remote training launch.

## Artifacts

```text
results/local/training_payload_schema_quality_tokenization_v1/summary.json
results/local/training_payload_schema_quality_tokenization_v1/schema_validation_results.jsonl
results/local/training_payload_schema_quality_tokenization_v1/tokenization_proxy_rows.jsonl
results/local/training_payload_schema_quality_tokenization_v1/tokenization_proxy_report.json
results/local/training_payload_schema_quality_tokenization_v1/training_manifest_v2.json
results/local/training_payload_schema_quality_tokenization_v1/training_readiness_decision.json
results/local/training_payload_schema_quality_tokenization_v1/public_safe_training_payload_schema_quality_tokenization_report.json
results/local/training_payload_schema_quality_tokenization_v1/training_payload_schema_quality_tokenization_privacy_report.json
results/local/training_payload_schema_quality_tokenization_v1/dataset_exports/rendered_patch_sft_training_payload.jsonl
```

## Next Step

```text
Step 29.38 - model-specific tokenizer selection and remote training cost gate v1
```

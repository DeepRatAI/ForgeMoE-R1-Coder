# ForgeMoE-R1-Agent-Coder — Project Recap and Roadmap

Status date: 2026-05-13  
Visibility: public-safe.

---

## 1. What this project is

ForgeMoE-R1-Agent-Coder is an AI Engineering project for improving coding models as fullstack software engineering agents.

The project focuses on measurable repository editing, not conversational impressions.

Core idea:

```text
Make the model produce patches.
Run the patches.
Score the result.
Use the result to improve generation, verification, and eventually training.
```

---

## 2. What exists now

The current implementation is a complete model-free foundation:

```text
task schema
patch evaluator
batch benchmark
self-repair loop
trajectory exporter
executable verifier
model I/O layer
candidate pipeline
experiment runner
run registry
```

These pieces validate the system contract before real model integration.

---

## 3. Why this foundation matters

A serious AI Engineering project needs:

```text
objective metrics
repeatable runs
failure capture
artifact lineage
source-control hygiene
cost control
training data contracts
```

This project now has those foundations.

---

## 4. Current architecture

```text
AgentTask
  -> prompt builder
  -> model adapter
  -> raw responses
  -> patch parser
  -> candidates
  -> executable verifier
  -> selected patch
  -> task result
  -> experiment summary
  -> registry
  -> future dataset/training loop
```

---

## 5. Current limitations

Current tasks are synthetic toy tasks.

The model is still mocked.

No real Hugging Face model has been connected yet.

No training has been executed yet.

AWS H100 capacity is not yet guaranteed.

The next phase must carefully move from mocked generation to real model generation.

---

## 6. Next phase

### Step 18 — Model adapter

Create a runtime-independent model interface.

### Step 19 — Tiny model smoke

Run a small local model through the candidate pipeline.

### Step 20 — Real baseline

Evaluate the selected code model against early benchmark tasks.

### Step 21 — Real task ingestion

Move beyond toy tasks into realistic repository tasks.

### Step 22+ — Training path

Prepare supervised tuning, verifier data, and execution-feedback optimization.

---

## 7. Success criteria

Short-term:

```text
real model produces parseable patches
pipeline measures parse failure rate
pipeline measures solve rate
baseline is reproducible
```

Medium-term:

```text
dataset contains real positive and negative trajectories
tuned model improves over base model on held-out tasks
verifier improves best-of-N selection
```

Long-term:

```text
open-weight code model behaves as a stronger fullstack development agent after targeted adaptation
```

---

## 8. Post-Step-18 recap

### Step 18 — Real Model Adapter v0: completed

Step 18 introduced the runtime-independent model boundary.

Implemented:

```text
GenerationConfig
ModelMetadata
GeneratedResponse
ModelAdapter protocol
DeterministicMockModelAdapter
LocalTransformersModelAdapter skeleton
GeneratedResponse -> RawModelResponse bridge
ADR-0013 model runtime boundary
```

Validated behavior:

```text
generated_response_count = 3
parse_failure_count = 1
selected_patch_id = mock_good_max2_candidate_2
solved = true
reward = 1.25
```

### Strategic interpretation

The project is now positioned as a portable agentic model-improvement platform.

The system should be able to move across:

```text
AWS
SageMaker
EC2
GCP / Vertex AI
vLLM servers
RunPod-like GPU providers
local development environments
```

without changing the core evaluator or experiment semantics.

### Immediate next step

```text
Step 19 — Tiny real model smoke test
```

The objective is not quality. The objective is proving that real model generation flows through the same contract as mock generation.


---

## Post-Step 19 status

The project has now crossed the first real-runtime boundary.

Completed real model smoke:

```text
model_id = sshleifer/tiny-gpt2
runtime = local_transformers
device = cpu
model_load_ok = true
real_generation_ok = true
generated_response_count = 1
parsed_candidate_count = 0
parse_failure_count = 1
solve_required = false
```

This validates the model adapter layer with a real Transformers model. It does not establish coding quality.

The next phase is Step 20: first useful real code-model baseline.

Step 20 should select a real code model that can run under current constraints, produce reproducible outputs, and establish baseline metrics for:

```text
parse_validity_rate
solve_rate
reward
latency
generated_response_count
candidate_pipeline_attempted
candidate_pipeline_solved
```

---

## Step 25 Recap — Intent Repair and Normalization

Step 25 closes the loop opened by Step 24 and Step 24.1.

The system now handles the following path:

```text
real model output
  -> parseable structured intent
  -> semantic validation failure
  -> grounded repair and normalization
  -> canonical patch builder
  -> git apply
  -> unit test verification
```

The immediate significance is that the system can recover usable training trajectories from imperfect model outputs. This is a prerequisite for building SFT and verifier-guided optimization datasets.

Next recommended engineering direction:

```text
Step 26 — Structured Intent SFT Dataset Export v0
```

Step 26 should convert Step 24/25 trajectories into explicit training rows containing prompt, raw model output, repaired target intent, canonical patch, verification metadata, and reward.

---

## Step 26 Recap — First SFT Dataset Export

Step 26 created the first dataset suitable for adapter or LoRA supervised fine-tuning.

The immediate next engineering target is no longer only evaluation. The project can now start building a training loop around structured edit intent prediction.

Recommended next direction:

```text
Step 27 — Local Adapter Training Plan and Dataset Loader v0
```

Step 27 should define and validate the training data loader, tokenization contract, train/eval split, and adapter training configuration before launching an actual fine-tuning job.

---

## Step 27 Recap — Training Data Loader and Adapter Plan

Step 27 prepared the first adapter-training contract.

The project can now consume the Step 26 SFT dataset through a validated loader and produce train/eval splits plus tokenizer statistics for Qwen2.5-Coder.

Recommended next direction:

```text
Step 28 — Local LoRA SFT Dry Run v0
```

Step 28 should attempt a minimal adapter training dry run if local CPU memory allows, or otherwise generate the exact GPU training job spec for SageMaker or a portable cloud runner.

---

## Step 28 Recap — Memory-Safe Local LoRA SFT Dry Run

Step 28 validates the adapter architecture boundary without loading full Qwen 0.5B weights in CloudShell.

Recommended next direction:

Step 29 — GPU LoRA SFT Job Spec and Launcher v0

Step 29 should move real full-weight loading and LoRA training to a GPU runtime.

---

## Step 28.1 Recap - Registry Refresh and Runtime Boundary

The project is ready to move from local dry-runs into GPU-backed execution.

Current boundary:

- CloudShell: control plane
- S3: artifact and dataset plane
- GitHub: source plane
- SageMaker or GPU runtime: compute plane

Recommended next step:

Step 29 - GPU LoRA SFT Job Spec and Launcher v0

Step 29 should create the real GPU training launcher for the Qwen2.5-Coder structured-intent LoRA adapter.

---

## Step 29.0 Recap - GPU Training Preflight

The project is now ready to launch the first real GPU LoRA SFT job after explicit approval.

Current state:

- CloudShell remains control plane only.
- SageMaker or equivalent GPU runtime is compute plane.
- Step 27 dataset is available in S3.
- Step 28 LoRA module boundary is validated.
- Step 29.0 launch plan is generated.
- Cost gate is active.

Next action after approval:

Step 29.1 or Step 30 - Launch real GPU LoRA SFT training job.

---

## Step 29.1 Recap - Registry Refresh After GPU Training Preflight

The registry and continuity docs now include Step 29.0.

The next technical step is no longer another dry run. The next boundary is a decision checkpoint:

- approve a real GPU training launch, or
- first expand the dataset before spending GPU budget.

Recommended next step if approved:

Step 30 - Launch real GPU LoRA SFT training job.

Recommended next step if not approved yet:

Step 29.2 - Expand structured-intent SFT dataset before first training job.

---

## Step 29.2 Recap - Structured SFT Dataset Expansion

The project now has a larger structured-intent SFT seed dataset.

Current state:

- Step 29.0 GPU preflight completed.
- Step 29.1 registry refresh completed.
- Step 29.2 expanded structured SFT data to 48 rows.
- Cost gate remains active.
- No paid training job has been launched.

Recommended next step:

Step 29.3 - Validate and tokenize expanded dataset for the target model before GPU training.

---

## Step 29.3 Recap - Structured SFT Tokenization Refresh

The expanded structured SFT dataset is now tokenizer-validated and rendered for training.

Current state:

- Step 29.2 produced 48 structured-intent SFT rows.
- Step 29.3 generated rendered train/eval JSONL files.
- Tokenization gate passed.
- Cost gate remains active.
- No paid GPU job has been launched.

Recommended next step:

Step 29.4 - Registry and docs refresh after tokenization gate.

After that, the project can either expand further or request explicit approval for Step 30 GPU training.

---

## Step 29.4 Recap - Registry Refresh After Tokenization Gate

The registry and continuity documentation now include the structured SFT dataset expansion and tokenizer validation.

Current state:

- Dataset: 48 structured-intent SFT rows.
- Rendered train rows: 40.
- Rendered eval rows: 8.
- Target tokenizer: Qwen/Qwen2.5-Coder-0.5B-Instruct.
- Tokenization gate: passed.
- Truncation count: 0.
- Cost gate: active.

Next decision point:

- Step 30: launch first real GPU LoRA SFT job after explicit approval, or
- Step 29.5: expand data further before spending GPU budget.

---

## Step 29.5 Recap - Structured SFT Curriculum Expansion

The structured-intent SFT curriculum has been expanded from 48 rows to 192 rows.

Current state:

- 192 total structured SFT rows.
- 160 train rows.
- 32 eval rows.
- 12 categories.
- 16 implementation cases.
- Cost gate remains active.
- No paid GPU job has been launched.

Recommended next step:

Step 29.6 - Tokenize the v1 curriculum and refresh the training manifest before deciding on Step 30 GPU training.

---

## Step 29.6 Recap - SOTA Dataset Governance

The project North Star is now fixed in documentation.

Current state:

- Step 29.5 produced 192 scaffold rows.
- The scaffold is useful but not training-grade.
- Dataset governance is now a formal engineering boundary.
- Step 30 training remains deferred.
- The next recommended step is a dataset source matrix and acquisition gate.

Recommended next step:

Step 29.7 - Dataset source matrix, legal/provenance gate and acquisition plan.

---

## Step 29.7 Recap - Dataset Source Matrix and Acquisition Gate

The project now has an operational dataset source matrix.

Current state:

- Large code corpora are blocked pending legal, provenance, safety, deduplication and contamination review.
- SWE-bench family, LiveCodeBench and BigCodeBench are reference or evaluation sources, not default training data.
- SWE-smith is a critical methodology reference.
- Forge synthetic executable tasks, Forge agentic trajectories and Forge private heldout eval are critical internal build targets.
- Step 30 training remains blocked.

Recommended next step:

Step 29.8 - Internal synthetic executable task generator and private heldout protocol design.

---

## Step 29.8 Recap - Internal Synthetic Generator and Private Heldout

The project now has a formal design for the internal data engine.

Current state:

- External datasets remain gated.
- Public benchmarks remain reference or evaluation sources by default.
- Internal executable task generation is the critical path.
- Private heldout eval is now a formal promotion boundary.
- Step 30 training remains blocked.

Recommended next step:

Step 29.9 - Task schema and deterministic micro-generator scaffold.

---

## Step 29.9 Recap - Deterministic Synthetic Micro-Generator

ForgeMoE now has its first executable internal data-generation scaffold.

Current state:

- Three deterministic synthetic tasks are generated.
- Golden and rejected patches are generated with `git diff` inside temporary repos with committed baselines.
- All tasks are verified with pre-fail, `git apply --check`, patch-apply, post-public and post-hidden checks.
- Training exports are produced only for the train split.
- Private heldout is protected from training exports.
- No GPU job is launched.
- No large external dataset is downloaded.

Recommended next step:

Step 29.10 - Oracle and hidden-test gate hardening.

---

## Step 29.10 Recap - Oracle and Hidden-Test Gate

ForgeMoE now treats executable generated tasks as candidates that must pass an oracle-quality gate before they are considered training-grade.

Current state:

- Step 29.9 tasks are challenged with golden, rejected, semantic no-op, empty, wrong-file and public-overfit patches.
- Public-overfit patches must pass public tests and fail hidden tests.
- Wrong-file patches must violate edit scope and fail the oracle.
- Hidden tests and private heldout patches are checked for training-export isolation.
- No GPU job is launched.
- No large external dataset is downloaded.

Recommended next step:

Step 29.11 - Agentic trajectory recorder v1.

---

## Step 29.11 Recap - Agentic Trajectory Recorder v1

ForgeMoE now records agentic repair trajectories from oracle-gated synthetic tasks.

Current state:

- Each Step 29.10-passing task emits a trajectory with read, inspect, plan, patch, validate, failure observation, repair and final-answer events.
- Public-overfit attempts are recorded as negative attempts that pass public tests and fail hidden tests.
- Golden repairs are recorded as positive attempts that pass public and hidden tests.
- Train split exports trajectory SFT, repair trace and trajectory preference rows.
- Eval and private heldout trajectories are exported separately and not used as training rows.
- Generated trajectory outputs pass local secret and hidden-test leakage scans.
- No GPU job is launched.
- No large external dataset is downloaded.

Recommended next step:

Step 29.12 - Private heldout seed set.

---

## Step 29.12 Recap - Private Heldout Seed Set v1

ForgeMoE now has a dedicated private heldout seed layer before training scale-up.

Current state:

- Three private-only executable tasks are generated deterministically.
- The seed set covers boundary condition, string normalization and collection semantics.
- Golden, rejected and public-overfit patches are generated via real `git diff` from temporary git repositories.
- Public tests fail before the patch.
- Golden patches pass public and hidden tests.
- Rejected patches fail the oracle.
- Public-overfit patches pass public tests but fail hidden tests.
- The public-safe manifest exports hashes and metadata only.
- Existing training exports are scanned for private task id, private patch and hidden-test leakage.
- No GPU job is launched.
- No large external dataset is downloaded.

Recommended next step:

Step 29.13 - Heldout-aware eval protocol.

---

## Step 29.13 Recap - Heldout-Aware Eval Protocol v1

ForgeMoE now has an explicit heldout-aware evaluation boundary.

Current state:

- Train, eval and private heldout usage rules are encoded in a split policy.
- Private heldout may be used only as aggregate final-gate signal.
- Private task ids, patches, hidden tests and task-level private results are excluded from the public-safe report.
- Golden, public-overfit and rejected reference candidates are scored against private heldout artifacts.
- Golden reference passes private heldout.
- Public-overfit reference passes public tests but fails private hidden tests.
- Rejected reference fails the private gate.
- The protocol emits a gate decision and privacy report.
- No GPU job is launched.
- No large external dataset is downloaded.

Recommended next step:

Step 29.14 - Model candidate eval contract.

---

## Step 29.14 Recap - Model Candidate Eval Contract v1

ForgeMoE now has a formal candidate evaluation package contract.

Current state:

- Candidate packages must include identity, model metadata, provenance, generation config, eval scope, aggregate metrics, privacy attestation and cost profile.
- Required metrics include parse validity, public eval solve rate, private heldout pass rate, public-overfit detection rate and regression-free patch rate.
- Candidate package validation rejects private heldout leakage.
- Candidate package validation rejects weak metrics.
- Candidate package validation rejects missing provenance.
- A structurally valid fixture can pass the contract but is not release-eligible because it is not a real model candidate.
- No training job is launched.
- No model release is allowed.
- No large external dataset is downloaded.

Recommended next step:

Step 29.15 - Candidate eval runner dry run.

---

## Step 29.15 Recap - Candidate Eval Runner Dry Run v1

ForgeMoE now has a dry-run candidate evaluation runner.

Current state:

- The runner emits a candidate package using the Step 29.14 contract.
- The emitted candidate package is contract-valid.
- The candidate is explicitly not a real model candidate and remains release-blocked.
- The runner emits a validation result, eval trace, gate decision, public-safe report and privacy report.
- Private heldout remains aggregate-only.
- Public reports exclude private task ids, private patches and hidden-test contents.
- No training job is launched.
- No model release is allowed.
- No large external dataset is downloaded.

Recommended next step:

Step 29.16 - Remote candidate smoke preflight.

---

## Step 29.16 Recap - Remote Candidate Smoke Preflight v1

ForgeMoE now has a remote candidate evaluation preflight path that respects the no-local-model-execution constraint.

Current state:

- The runner verifies AWS identity and S3 access.
- The runner verifies SageMaker inventory access.
- The runner verifies Bedrock foundation-model inventory access.
- Local model execution is explicitly disallowed.
- Remote inference is not invoked in this step.
- The emitted preflight package is not marked as an evaluated real model candidate.
- The candidate package is validated against the Step 29.14 model candidate contract.
- The runner emits cloud preflight, remote execution plan, validation result, gate decision, public-safe report and privacy report.
- Private heldout remains aggregate-only and is not evaluated by the smoke candidate.
- Public reports exclude private task ids, private patches, hidden-test contents and raw candidate outputs.
- Training remains blocked.
- Model release remains blocked.
- No GPU job is launched.
- No large external dataset is downloaded.

Recommended next step:

Step 29.17 - Remote code-model candidate smoke eval.

---

## Step 29.17 Recap - Remote Code-Model Candidate Smoke Eval v1

ForgeMoE now has a prepared remote code-model smoke eval request path.

Current state:

- A public executable clamp bugfix smoke task is generated.
- Public tests fail before any candidate patch.
- Patch-generation messages are built from the repo context and pre-test failure.
- A Bedrock on-demand text model is selected from live AWS inventory.
- A Bedrock Converse request artifact is emitted.
- An AWS CLI command plan is emitted but marked prepared-not-executed.
- Execution authorization is false.
- No local model execution is used.
- No remote inference is invoked.
- No training job is launched.
- No model release is allowed.
- Private heldout remains aggregate-only and unused for prompt iteration.

Recommended next step:

Step 29.18 - Remote inference cost approval and candidate eval.

---

## Step 29.18 Recap - Remote Inference Cost Approval Gate v1

ForgeMoE now has an explicit cost approval gate before any paid remote model call.

Current state:

- The Step 29.17 Bedrock Converse request is consumed as the source request.
- A conservative token ceiling is computed from the prepared prompt and max output tokens.
- The selected remote model id and exact request SHA-256 are recorded.
- A cost approval policy is emitted with approval status `not_approved`.
- The execution plan is written but blocked until explicit approval and official pricing evidence exist.
- The approval record is present and intentionally unapproved.
- No local model execution is used.
- No remote inference is invoked.
- No candidate evaluation is executed.
- No training job is launched.
- No model release is allowed.
- Public-safe reports exclude private task ids, private patches, hidden-test contents and raw candidate outputs.

Recommended next step:

Step 29.19 - Remote inference execution candidate eval, only after explicit cost approval for the selected model and request hash.

---

## Step 29.19 Recap - Remote Inference Execution Candidate Eval v1

ForgeMoE now has a fail-closed execution harness for the first approved remote smoke candidate eval.

Current state:

- The Step 29.17 Bedrock Converse request is copied into an execution workspace.
- The request SHA-256 is verified against the Step 29.18 cost approval gate.
- Authorization checks cover execution flag, external approval evidence, model id, request hash, call count, cost ceiling, token ceiling and official pricing evidence.
- The default doctor runs with `FORGEMOE_EXECUTE_REMOTE_INFERENCE=0`.
- Execution authorization is false in the current state.
- No Bedrock Runtime call is made.
- No local model execution is used.
- No response text is parsed.
- No patch is extracted.
- No `git apply --check` or post-patch public test is run because no patch exists.
- The candidate package is present but invalid/release-blocked.
- Public-safe reports exclude prompt text, raw responses, patch content, private ids, private patches and hidden tests.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Obtain explicit cost approval and official pricing evidence for the exact model id and request hash, then run one authorized remote inference smoke eval through Step 29.19.

---

## Step 29.20 Recap - Public Eval Suite Scaleout v1

ForgeMoE now has a broader public executable eval suite for future candidate evaluation.

Current state:

- Six deterministic public eval tasks are generated.
- The suite covers six task families and at least ten behavioral axes.
- Every task is represented as a real temporary Python repository.
- Golden, rejected and public-overfit patches are generated with Git-native diffs from committed baselines.
- Public tests fail before patching for every task.
- Golden patches pass `git apply --check`, public tests and hidden oracle tests.
- Rejected patches fail the oracle.
- Public-overfit patches pass public tests and fail hidden oracle tests.
- Public-safe manifests export hashes and metadata only.
- No model candidate is evaluated.
- No local model execution is used.
- No remote inference is invoked.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.21 - public eval candidate runner scaleout, using the expanded suite while preserving the remote inference approval gate and aggregate-only private heldout policy.

---

## Step 29.21 Recap - Public Eval Candidate Runner Scaleout v1

ForgeMoE now has a scaled public eval candidate-runner path that can aggregate multi-task reference candidate behavior without executing a local or remote model.

Current state:

- The runner consumes the six-task Step 29.20 public eval suite.
- Three deterministic reference candidate families are scored: golden, rejected and public-overfit.
- Golden reference patches pass public tests, hidden oracle checks and regression-free checks across the suite.
- Rejected reference patches fail hidden-oracle and regression-free checks as expected, even when some weak patches pass public tests.
- Public-overfit reference patches pass public tests while failing hidden oracle checks, proving the overfit detector catches weak public-only behavior.
- Candidate packages are emitted through the Step 29.14 model candidate eval contract.
- Reference packages remain intentionally contract-invalid and release-blocked because they are not real model candidates and no private-heldout aggregate candidate result exists.
- Public-safe reports expose aggregate metrics only.
- Private heldout ids, private patch content, hidden-test content, raw candidate output and prompt text are excluded from public outputs.
- No local model execution is used.
- No remote inference is invoked.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.22 - authorized remote candidate eval or public eval batch adapter, depending on whether explicit remote-inference approval and official pricing evidence are available.

---

## Step 29.22 Recap - Public Eval Remote Batch Adapter v1

ForgeMoE now has a prepared remote batch adapter for the six-task public eval suite.

Current state:

- The adapter consumes Step 29.20 and Step 29.21 artifacts.
- One Bedrock Converse request is prepared per public eval task.
- Six public pre-test failures are verified before candidate generation.
- Each request has a SHA-256 hash.
- The batch has a batch request SHA-256.
- A token ceiling, cost policy, unapproved approval record and pricing evidence requirement are emitted.
- A future batch execution plan is emitted but marked unauthorized.
- A candidate package is emitted through the model candidate eval contract.
- The package remains intentionally invalid and release-blocked because no real model response or private-heldout aggregate result exists.
- No local model execution is used.
- No remote inference is invoked.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.23 - authorized public eval remote batch execution after explicit approval and official pricing evidence are bound to the exact selected model id, request hashes and batch request hash.

---

## Step 29.23 Recap - Public Eval Remote Batch Execution v1

ForgeMoE now has a fail-closed public eval remote batch execution harness.

Current state:

- The harness consumes the Step 29.22 request manifest.
- The selected model id is verified.
- Six per-task request hashes are verified against request files.
- The batch request hash is verified.
- Approval evidence is required.
- Official pricing evidence is required.
- The execution flag is required.
- In the default state, execution is unauthorized.
- No Bedrock Runtime call is made.
- No local model execution is used.
- No raw remote response is present.
- No patch is extracted.
- No candidate public or hidden eval tests are run.
- A candidate package is emitted through the model candidate eval contract.
- The package remains invalid and release-blocked because no real model response or private-heldout aggregate result exists.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.24 - private heldout aggregate candidate eval gate, or execute Step 29.23 only after approval and official pricing evidence are bound to the exact batch.

---

## Step 29.24 Recap - Private Heldout Aggregate Candidate Eval Gate v1

ForgeMoE now has a fail-closed private heldout aggregate candidate eval gate.

Current state:

- The gate consumes the Step 29.23 candidate package.
- The heldout-aware protocol is verified ready.
- Private heldout isolation is verified before the gate runs.
- Candidate package SHA-256 is computed and recorded.
- Aggregate private-heldout evidence is required.
- Evidence must match candidate id, candidate package SHA-256, public batch request SHA-256, heldout protocol version and private heldout task count.
- Task-level results are disallowed.
- Private task ids are disallowed.
- Patch content is disallowed.
- Hidden-test content is disallowed.
- Prompts and raw model outputs are disallowed.
- In the default state, aggregate evidence is absent.
- No private heldout evaluation is claimed.
- No local model execution is used.
- No remote inference is invoked by this gate.
- Candidate release remains blocked.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.25 - authorized private heldout execution path after public candidate success, or training data governance scaleout if remote candidate execution remains unapproved.

---

## Step 29.25 Recap - Training Data Governance Scaleout v1

ForgeMoE now has an auditable row-level training data admission gate.

Current state:

- Ten current internal dataset export files are inventoried.
- Ten current rows are evaluated across split, privacy, provenance, contamination and oracle-quality controls.
- Six train-split rows are admitted only as scaffold data for schema and tooling validation.
- Zero rows are admitted as training-grade.
- Eval rows are rejected for training use.
- Private heldout rows are rejected for training use.
- Public reports exclude raw rows, private identifiers, patch content, withheld-eval content, prompts and model outputs.
- No local model execution is used.
- No remote inference is invoked.
- No large external dataset is downloaded.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.26 - Training data schema normalization and generator scaleout plan.

---

## Step 29.26 Recap - Training Data Schema Normalization and Scaleout Plan v1

ForgeMoE now has a canonical schema contract before generator scaleout.

Current state:

- Five canonical data products are defined: patch SFT, trajectory SFT, preference pair, repair trace and executable task reference.
- Ten current governed rows are mapped to canonical schemas.
- Zero current source rows are unmapped.
- Six train-split scaffold rows have normalized manifest references.
- Zero rows are training-grade.
- The scaleout plan defines schema lock, provenance/license registry, contamination/dedup scanners, oracle-quality certification and bounded generator scaleout dry run.
- Public reports exclude raw rows, private identifiers, patch content, withheld-eval content, prompts and model outputs.
- No local model execution is used.
- No remote inference is invoked.
- No large external dataset is downloaded.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.27 - provenance, license and contamination scanner implementation.

---

## Step 29.27 Recap - Provenance, License and Contamination Scanner v1

ForgeMoE now has executable scanner evidence for provenance, license and contamination boundaries.

Current state:

- Ten governed source rows are scanned.
- Six train rows, two eval rows and two private heldout rows are classified.
- Provenance, license and contamination scan outputs are emitted per row.
- A hash-only fingerprint index is emitted.
- Train rows show zero overlap with known eval identifiers.
- Train rows show zero overlap with known private heldout identifiers.
- Zero rows pass training-grade release.
- Public reports exclude raw rows, private identifier values, patch content, withheld-eval content, prompts and model outputs.
- No local model execution is used.
- No remote inference is invoked.
- No large external dataset is downloaded.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.28 - dedup and near-duplicate scanner implementation.

---

## Step 29.28 Recap - Dedup and Near-Duplicate Scanner v1

ForgeMoE now has an executable deduplication and near-duplicate scanner for current governed internal scaffold rows.

Current state:

- Ten governed rows are represented as hash-only dedup features.
- Forty-five row pairs are compared.
- Exact row duplicate groups are absent.
- Same-task multi-product groups are detected.
- Current train rows are blocked from training-grade release because task-family bundle policy is not yet implemented.
- High-similarity train/eval and train/private split collisions are not present in the current scaffold.
- High-similarity eval/private-heldout scaffold pairs are present, which blocks any serious private generalization claim until task-family isolation and harder task generation are implemented.
- Public reports exclude raw rows, raw text, private identifier values, patch content, withheld-eval content, prompts and model outputs.
- No local model execution is used.
- No remote inference is invoked.
- No large external dataset is downloaded.
- No training job is launched.
- No model release is allowed.

Recommended next step:

Step 29.29 - task-family bundle isolation and oracle-quality certification.

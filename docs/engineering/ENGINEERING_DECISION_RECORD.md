# ForgeMoE-R1-Agent-Coder — Engineering Decision Record

Status date: 2026-05-13  
Visibility: public-safe engineering record.  
Sensitive data policy: do not include AWS account IDs, private keys, access tokens, support-case private correspondence, or secrets.

This document records the architectural decisions, tradeoffs, bugs, fixes, and senior-engineering reasoning behind ForgeMoE-R1-Agent-Coder.

It complements the private project state document. The private document may contain operational identifiers. This document should remain safe to commit to the public repository.

---

## 1. Final project concept

ForgeMoE-R1-Agent-Coder is an evaluation-driven AI Engineering project for building, adapting, and evaluating an open-weight coding model as a fullstack software engineering agent.

The project is not merely a chatbot wrapper and not merely a fine-tuning notebook. It is a reproducible agentic model-improvement system.

Core loop:

```text
repository task
  -> prompt/model I/O
  -> model-generated patch candidates
  -> patch parser
  -> executable verifier/reranker
  -> selected patch
  -> metrics
  -> trajectories
  -> training/evaluation data
  -> future SFT/RL/verifier/model adaptation
```

The long-term goal is to take the strongest code model that fits within our compute envelope and improve its fullstack agentic development behavior through measurable, reproducible, execution-based training and evaluation.

---

## 2. Engineering philosophy

### 2.1 Evaluation before optimization

We deliberately built the evaluation and experiment harness before touching model weights.

Rationale:

```text
Without a reliable executable evaluator, any model tuning result is anecdotal.
```

This prevents the classic failure mode:

```text
train model -> generate appealing responses -> no objective evidence of improvement
```

The chosen strategy is:

```text
define task -> run tests -> apply patch -> run tests -> compute reward -> aggregate metrics
```

### 2.2 Executable reward over subjective preference

For code tasks, execution is a strong objective signal.

Primary signal:

```text
post-patch tests passed
```

Secondary signals:

```text
patch applied
reward
parse validity
candidate rank
self-repair success
```

This does not eliminate the need for hidden tests, static analysis, style checks, or human review later. It gives us the correct foundation.

### 2.3 Artifact-first reproducibility

Every meaningful step produces:

```text
source commit
local doctor
S3 output artifact
S3 manifest
run registry entry
```

This means a future engineer or agent can reconstruct what happened.

---

## 3. Architecture planes

### Plane A — Task and evaluation plane

Responsible for:

```text
task schema
repo isolation
test execution
patch application
reward calculation
batch evaluation
```

Implemented by:

```text
forgeagentcoder.data.task_schema
forgeagentcoder.eval.command_runner
forgeagentcoder.eval.patch_task_eval
forgeagentcoder.eval.batch_eval
forgeagentcoder.rewards.code_rewards
```

### Plane B — Agent loop plane

Responsible for:

```text
self-repair attempts
candidate patches
iteration state
trajectory output
```

Implemented by:

```text
forgeagentcoder.agent.patch_provider
forgeagentcoder.agent.self_repair
forgeagentcoder.agent.loop_state
```

### Plane C — Model I/O plane

Responsible for:

```text
repo context collection
prompt construction
raw model response handling
unified diff extraction
patch-shape validation
```

Implemented by:

```text
forgeagentcoder.agent.prompt_builder
forgeagentcoder.agent.patch_parser
forgeagentcoder.agent.mock_model
```

### Plane D — Verification and selection plane

Responsible for:

```text
candidate evaluation
executable reranking
best-of-N patch selection
parse failure tracking
```

Implemented by:

```text
forgeagentcoder.verifier.executable_verifier
forgeagentcoder.agent.candidate_pipeline
```

### Plane E — Experiment control plane

Responsible for:

```text
multi-task experiments
aggregate metrics
run registry
artifact lineage
```

Implemented by:

```text
forgeagentcoder.eval.experiment_runner
forgeagentcoder.utils.run_registry
```

### Plane F — Future model adaptation plane

Not fully implemented yet.

Planned components:

```text
ModelAdapter protocol
LocalTransformersModelAdapter
SageMakerModelAdapter
vLLMModelAdapter
training recipes
SFT datasets
preference/reward datasets
QLoRA/LoRA training
base-vs-tuned evaluation
```

---

## 4. ADRs

### ADR-0001 — Use code tasks because execution gives objective feedback

Decision:

```text
Specialize the project around coding-agent tasks instead of generic chat quality.
```

Reasoning:

```text
Code can be tested. A patch can be applied. A result can be measured.
```

Tradeoff:

```text
The project becomes more engineering-heavy and less demo-friendly, but the results are more defensible.
```

Status:

```text
Accepted
```

---

### ADR-0002 — Use unified diff as the model output contract

Decision:

```text
Require model outputs to resolve to unified diff patches.
```

Reasoning:

```text
Unified diff is compatible with git apply, repo-level editing, and executable evaluation.
```

Tradeoff:

```text
Some models may prefer prose or complete files. We reject or parse those outputs unless they contain a valid patch.
```

Status:

```text
Accepted
```

---

### ADR-0003 — Build model-free infrastructure before using GPU

Decision:

```text
Build evaluator, verifier, pipeline, experiment runner, and registry before downloading or tuning a large model.
```

Reasoning:

```text
GPU time is expensive. Training without a measurement harness is low-signal.
```

Tradeoff:

```text
Initial progress feels slower because no model is being trained yet. The resulting system is far more reliable.
```

Status:

```text
Accepted
```

---

### ADR-0004 — Separate source code from generated artifacts

Decision:

```text
Use GitHub for source code and S3 for generated artifacts, results, manifests, and tar snapshots.
```

Reasoning:

```text
Large/generated artifacts should not pollute the repository.
```

Tradeoff:

```text
Requires S3 discipline and registry tracking.
```

Status:

```text
Accepted
```

---

### ADR-0005 — Use executable verifier before learned verifier

Decision:

```text
Start with an oracle executable verifier that actually runs tests.
```

Reasoning:

```text
A learned verifier needs labels. Executable verification generates reliable labels and ranking data.
```

Tradeoff:

```text
Execution is slower than static scoring, but it is more trustworthy at this stage.
```

Status:

```text
Accepted
```

---

### ADR-0006 — Support invalid model outputs explicitly

Decision:

```text
Track parse failures instead of crashing when a model response is not a valid patch.
```

Reasoning:

```text
Real models often return prose, markdown, malformed diffs, or partial code. The pipeline must measure that.
```

Tradeoff:

```text
The pipeline becomes more complex, but experiments become more realistic.
```

Status:

```text
Accepted
```

---

### ADR-0007 — Use best-of-N candidate selection

Decision:

```text
Generate multiple patch candidates and use a verifier/reranker to select the best one.
```

Reasoning:

```text
Agentic coding performance can improve with test-time compute and candidate selection.
```

Tradeoff:

```text
More candidates cost more inference and execution time.
```

Status:

```text
Accepted
```

---

### ADR-0008 — Export trajectories as future training data

Decision:

```text
Convert self-repair attempts into patch_attempts.jsonl and sft_positive.jsonl.
```

Reasoning:

```text
Failed attempts are useful for verifier/reward learning. Successful attempts are useful for SFT.
```

Tradeoff:

```text
Toy data is not enough for training, but it validates the data contract.
```

Status:

```text
Accepted
```

---

### ADR-0009 — Create run registry before real model integration

Decision:

```text
Create a central registry of runs, metrics, manifests, and S3 artifacts before using real models.
```

Reasoning:

```text
Real model experiments introduce many variables. Without a registry, lineage is lost.
```

Tradeoff:

```text
Adds bookkeeping before visible model progress, but avoids confusion later.
```

Status:

```text
Accepted
```

---

### ADR-0010 — Keep private operational state separate from public engineering records

Decision:

```text
Maintain a private handoff document outside the repo and a public-safe engineering decision record inside the repo.
```

Reasoning:

```text
The project needs complete context, but credentials and operational identifiers must not be public.
```

Tradeoff:

```text
Two documents must be maintained.
```

Status:

```text
Accepted
```

---

### ADR-0011 — ModelAdapter must be introduced before real model baseline

Decision:

```text
Step 18 introduces a model adapter abstraction before running any real model.
```

Reasoning:

```text
The pipeline should not depend on a specific runtime such as local Transformers, SageMaker, or vLLM.
```

Tradeoff:

```text
One more abstraction layer, but future portability is much better.
```

Status:

```text
Accepted
```

---

### ADR-0012 — MoE is not the first implementation milestone

Decision:

```text
Keep MoE as a possible advanced model-side path, but do not start there.
```

Reasoning:

```text
MoE architecture work is expensive and not useful until we have baselines, datasets, and evaluation. The current higher-leverage route is agentic adaptation around executable feedback.
```

Tradeoff:

```text
The project name references MoE/R1 ambition, but the first serious engineering milestone is reproducible agentic coding improvement.
```

Status:

```text
Accepted
```

---

## 5. Bugs, failures, and fixes

### BUG-0001 — Python bytecode cache caused stale post-patch test results

Symptom:

```text
Patch applied successfully, but post-patch tests still behaved like the old code.
```

Root cause:

```text
Python reused stale bytecode/cache after fast file modification.
```

Fix:

```text
Use python3 -B for tests.
Remove __pycache__ and .pyc files before tests.
```

Lesson:

```text
Evaluation harnesses must control language runtime caches.
```

---

### BUG-0002 — Generated artifacts were accidentally committed

Symptom:

```text
tmp/, results/local/, __pycache__, and embedded toy .git directories entered git index.
```

Root cause:

```text
git add . was used before .gitignore was mature.
```

Fix:

```text
Add .gitignore rules.
Remove generated files from git index.
Use git archive for clean release tarballs.
```

Lesson:

```text
Generated local execution artifacts must never become source artifacts.
```

---

### BUG-0003 — Pasted terminal output created garbage files

Symptom:

```text
Files named BASH, HEAD, main, --output, aws, git, if, etc. appeared in the repo.
```

Root cause:

```text
Terminal output or partial scripts were pasted into CloudShell as commands.
```

Fix:

```text
Use smaller command blocks.
Use downloadable shell scripts for long operations.
Use git clean -fd only after dry-run review.
```

Lesson:

```text
Operational ergonomics matter. Agent instructions must be copy-safe.
```

---

### BUG-0004 — EC2 P instance quota was denied

Symptom:

```text
AWS did not approve On-Demand P instance quota at first request.
```

Root cause:

```text
New/low-activity AWS accounts often need gradual quota ramp-up and detailed use case justification.
```

Fix:

```text
Continue model-free development.
Prepare appeal text.
Avoid depending on H100 access before the software stack is ready.
```

Lesson:

```text
Compute availability is a project risk. Architecture must degrade gracefully.
```

---

### BUG-0005 — Raw model response may contain prose instead of patch

Symptom:

```text
Candidate response contains explanation but no unified diff.
```

Root cause:

```text
Language models do not always follow output contracts.
```

Fix:

```text
Patch parser raises structured parse failure.
Candidate pipeline records invalid outputs and continues with valid candidates.
```

Lesson:

```text
Real model integration must treat malformed outputs as a measurable outcome, not an exceptional surprise.
```

---

## 6. Interview-grade design answers

### Why did we build the evaluator before training?

Because model improvement must be measurable. Without executable evaluation, training changes can only be judged subjectively.

### Why use patches instead of free-form answers?

Because patches are actionable, testable, and compatible with real engineering workflows.

### Why use an executable verifier?

Because a verifier that runs tests gives us trustworthy labels and ranking signals. Learned verifiers can come later.

### Why not start directly with MoE?

Because MoE architecture work is costly and hard to evaluate without a baseline, dataset, and execution harness. The project first builds the system needed to prove improvement.

### How do we avoid wasting GPU budget?

By validating the full model-free pipeline first, recording every run, and only launching GPU work when experiments are designed and measurable.

### How does this become training data?

Self-repair and candidate-generation trajectories produce positive and negative patch attempts. These can feed SFT, verifier training, rejection sampling, and future execution-feedback optimization.

### What makes this senior-level?

The project separates concerns, records tradeoffs, validates assumptions with doctors, preserves reproducibility, tracks artifacts, handles failure modes, and delays expensive optimization until measurement exists.

---

## 7. Current state summary

Completed foundation:

```text
Step 8  — AWS-native scaffold
Step 9  — patch evaluator
Step 10 — batch benchmark
Step 11 — self-repair loop
Step 12 — trajectory dataset exporter
Step 13 — executable verifier
Step 14 — model I/O layer
Step 15 — candidate generation pipeline
Step 16 — experiment runner
Step 17 — run registry
Step 17.5 — private project state document
Step 17.6 — public-safe engineering decision record
```

Current latest source commit before this document:

```text
39b2773 Add run registry index
```

This document should be committed as the next source commit.

---

## 8. Next engineering phase

### Step 18 — Real model adapter v0

Planned components:

```text
ModelAdapter protocol
GenerationConfig
GeneratedResponse
MockModelAdapter migration
LocalTransformersModelAdapter skeleton
runtime metadata
generation parameter tracking
```

### Step 19 — Tiny real model smoke test

Goal:

```text
Run a very small model through the existing pipeline without H100.
```

### Step 20 — Real model baseline

Goal:

```text
Run the selected baseline model through toy and early real agentic tasks.
```

### Step 21+ — Dataset and training

Goal:

```text
Move from toy tasks to real repo tasks, then prepare QLoRA/SFT and future RL-style optimization.
```

---

## 9. SOTA-oriented target design

The system should evolve toward:

```text
evaluation-driven coding agent improvement
best-of-N generation
executable verification
trajectory mining
positive/negative sample export
SFT on successful patches
verifier training on ranked candidates
preference/reward optimization from execution outcomes
self-repair with feedback
base-vs-tuned reproducible evaluation
```

MoE remains a possible later path. It should be considered only after we establish:

```text
real baseline
real task dataset
real evaluation suite
first tuning loop
clear bottleneck that routing/specialization would solve
```

---

## 10. Maintenance policy

Update this document when:

```text
a major architecture decision is made
a meaningful bug/failure is found
a model/runtime path is selected
a training approach is selected
AWS/GPU strategy changes
a benchmark result changes the project direction
```

Do not include:

```text
AWS access keys
GitHub tokens
SSH private keys
passwords
MFA codes
private support correspondence
raw credentials
```

---

## 11. Post-Step-18 engineering update

### ADR-0014 — Backend portability and evaluation-invariant design

Status: Accepted  
Date: 2026-05-13

#### Context

After Step 18, the project crossed from model-free infrastructure into the model-runtime boundary. The risk at this point is accidentally coupling the agentic improvement system to a single provider, GPU type, model runtime, or cloud environment.

#### Decision

ForgeMoE-R1-Agent-Coder must remain backend-portable, model-runtime-portable, artifact-reproducible, and evaluation-invariant.

The stable core is:

```text
task schema
prompt/model I/O
candidate generation
patch parser
executable verifier
experiment runner
trajectory exporter
run registry
```

The replaceable execution layer is:

```text
local Transformers
SageMaker
EC2
vLLM
Google Vertex AI
RunPod/Lambda/Paperspace
OpenAI-compatible endpoints
future custom clusters
```

#### Rationale

The project needs GPU resources, but GPU access must not define the architecture. Cloud quotas and provider availability are operational variables, not core assumptions.

#### Tradeoff

This requires additional adapters and metadata discipline. The benefit is that model experiments can migrate across runtimes without rewriting the evaluator, verifier, registry, or data pipeline.

#### Consequences

Every real model experiment must record:

```text
model_id
adapter_name
runtime
generation_config
raw outputs
parsed candidates
verification results
experiment metrics
artifact URIs
source commit
```

#### Senior-level implication

The system is designed as an agentic model-improvement factory, not a one-off fine-tuning notebook.

---

### ADR-0015 — Step 19 should validate real generation, not quality

Status: Accepted  
Date: 2026-05-13

#### Context

Step 18 introduced the ModelAdapter contract and validated it with deterministic generation. The next engineering step is to cross the boundary into real model generation.

#### Decision

Step 19 will use a tiny real model smoke test. Its goal is runtime validation, not agentic quality.

Step 19 success criteria:

```text
install/load minimal model dependencies
load a tiny model or controlled real runtime
generate text through ModelAdapter
save GeneratedResponse records
bridge into candidate pipeline
record parse failures if output is malformed
upload artifacts
create manifest
avoid H100 spend
```

#### Rationale

A tiny model is not expected to solve fullstack coding tasks. The purpose is to validate the adapter boundary against a real runtime before scaling to larger models.

#### Consequences

Step 20 should be the first real baseline step. Step 19 is only a runtime smoke test.

---

### Current project definition after Step 18

ForgeMoE-R1-Agent-Coder is a reproducible and portable AI Engineering system for transforming open-weight coding models into specialized fullstack agentic development models through executable evaluation, candidate generation, verification, trajectory mining, SFT/verifier/reward data generation, and future tuning.

The model is an output of the system. The system itself is the higher-value artifact.


---

## Step 19 transition — first real model runtime

Step 19 completed the first real model runtime smoke test through `LocalTransformersModelAdapter`.

This was intentionally not a quality benchmark. The selected model, `sshleifer/tiny-gpt2`, is a tiny text-generation model used only to validate runtime mechanics.

Observed result:

```text
model_load_ok = true
real_generation_ok = true
generated_response_count = 1
parsed_candidate_count = 0
parse_failure_count = 1
candidate_pipeline_attempted = false
solve_required = false
```

Engineering interpretation:

```text
The project crossed from deterministic mock generation to real model generation.
The adapter boundary is now proven with an actual Transformers runtime.
The next phase must use a meaningful code model and evaluate patch validity and solve rate.
```

Related ADR:

```text
ADR-0017 — First Real Model Runtime Before Useful Baseline
```

---

## Update — Step 25 Intent Repair and Normalization

Step 25 introduced `intent_repair_normalization_v0`.

The architectural decision is to treat parseable-but-invalid model JSON as recoverable signal rather than failed output. Step 24.1 showed that the real model emitted parseable JSON but used non-code `find_text`, causing `find_text_not_found` across all tasks. Step 25 repairs the intent by grounding `find_text` in the exact current file from the prompt and synthesizing replacement text from task context for the controlled toy benchmark.

Result:

```text
source_json_parse_success_count = 3
original_valid_intent_count = 0
repaired_valid_intent_count = 3
canonical_patch_count = 3
patch_apply_success_count = 3
solved_tasks = 3
solve_rate = 1.0
```

This establishes the trajectory form needed for future supervised fine-tuning:

```text
raw_model_intent -> repaired_intent -> canonical_patch -> executable_verification -> reward
```

---

## Update — Step 26 Structured Intent SFT Dataset Export

Step 26 exported the first supervised fine-tuning dataset from real-model structured-intent trajectories.

The dataset converts the Step 24 and Step 25 path into training rows:

```text
raw_model_output
-> original_intent
-> repaired_intent
-> canonical_patch
-> verification_result
-> reward
-> supervised_training_target
```

The chosen SFT target is the repaired structured edit intent JSON. Raw unified diff text remains a system-side canonicalization product, not the primary model target.

Result:

```text
total_sft_rows = 3
total_trajectory_rows = 3
positive_reward_rows = 3
solved_rows = 3
average_reward = 1.0
```

This is the first concrete training bridge from evaluation infrastructure into model improvement.

---

## Update — Step 27 Local Adapter Training Plan and Dataset Loader

Step 27 introduced the first training-data preparation layer.

The project now has:

```text
structured_intent_sft_dataset_v0
-> validated SFT examples
-> deterministic train/eval split
-> Qwen tokenizer rendering
-> tokenization report
-> local adapter training manifest
```

This step intentionally does not train the model. It validates that the first training dataset is structurally usable before consuming GPU time.

Result:

```text
total_rows = 3
train_rows = 2
eval_rows = 1
validation_issue_count = 0
this_step_trains_model = false
```

The next major boundary is a real adapter training dry run.

---

## Update — Step 28 Memory-Safe Local LoRA SFT Dry Run

Step 28 introduced a memory-safe LoRA trainability dry run after CloudShell killed the full Qwen2.5-Coder 0.5B CPU weight load.

The revised boundary validates:

- real Qwen config
- tiny Qwen2-compatible architecture
- inferred LoRA target modules
- PEFT adapter attachment
- trainable parameter count
- Step 27 train/eval tokenization
- GPU training job specification

This avoids treating CloudShell memory limits as model or adapter failures.

---

## Update - Step 28.1 Manifest-Derived Registry and CloudShell Boundary

Step 28.1 refreshed the run registry from S3 manifests and formalized a runtime boundary: CloudShell is the control plane, not the compute plane.

The project now treats manifests as the source of truth for historical execution state. This is more robust than manually maintaining registry entries.

The CloudShell boundary is explicit: lightweight orchestration remains in CloudShell, while full model loading, LoRA training, QLoRA training, and evaluation-heavy loops move to SageMaker, EC2 GPU, AWS Batch GPU, or a portable GPU runner.

---

## Update - Step 29.0 GPU Training Runtime Preflight

Step 29.0 introduced a hard cost gate before real GPU training.

The project validated AWS identity, S3 training inputs, SageMaker API access, SageMaker role presence, Step 27 dataset artifacts, and Step 28 LoRA training specifications.

No training job was launched in this step. This is intentional. The next launch step requires explicit approval because it can incur AWS charges.

---

## Update - Step 29.1 Registry Refresh After GPU Training Preflight

Step 29.1 registered the GPU training preflight into the manifest-derived run registry.

The project state now explicitly records:

- Step 29.0 validated AWS identity, S3 inputs, SageMaker role, SageMaker API access, launch plan, and risk register.
- Training launch remains blocked by an explicit cost gate.
- CloudShell remains control plane only.
- Real model training belongs to SageMaker, EC2 GPU, AWS Batch GPU, or an equivalent GPU compute plane.

This preserves the SOTA target while preventing accidental paid GPU jobs.

---

## Update - Step 29.2 Structured SFT Dataset Expansion

Step 29.2 expanded the structured intent SFT dataset before GPU spend.

The dataset now contains 48 synthetic verified-intent rows across 8 categories:

- localized bugfix
- wrong file guard
- missing test addition
- small multi-file edit
- safe refactor
- import and typing fix
- invalid patch repair
- semantic patch repair

The decision is to improve training signal before launching paid GPU training.

---

## Update - Step 29.3 Structured SFT Tokenization Refresh

Step 29.3 validated the expanded structured-intent SFT dataset against the target Qwen tokenizer.

The step rendered chat-style SFT text, measured token lengths, confirmed structured-intent JSON validity, checked truncation risk, and generated a refreshed training manifest.

No model weights were loaded and no training job was launched.

---

## Update - Step 29.4 Registry Refresh After Tokenization Gate

Step 29.4 registered the expanded structured SFT dataset and tokenizer validation gate into the manifest-derived run registry.

The project now records:

- Step 29.2 expanded structured-intent SFT data to 48 rows.
- Step 29.3 rendered and tokenized the dataset against Qwen/Qwen2.5-Coder-0.5B-Instruct.
- Tokenization gate passed with zero truncation risk at max sequence length 2048.
- No full model weights were loaded.
- No paid GPU training job was launched.
- Cost gate remains active before Step 30.

This keeps the training path reproducible and prevents launching GPU jobs before the data plane is validated.

---

## Update - Step 29.5 Structured SFT Curriculum Expansion

Step 29.5 expanded the structured-intent SFT curriculum to 192 rows.

The curriculum now covers 12 edit-intent categories and 16 implementation cases, with 160 train rows and 32 eval rows.

This step intentionally did not launch training. It improves the data plane before spending GPU budget.

---

## Update - Step 29.6 SOTA Dataset Governance

Step 29.6 fixed the project North Star and formalized the dataset governance strategy before training-grade GPU runs.

The current Step 29.2 and Step 29.5 datasets are explicitly classified as scaffold/plumbing/format-validation data, not final training-grade data.

The project now requires dataset lineage, license review, deduplication, contamination control, quality scoring, heldout design and training mixture manifests before serious paid training.

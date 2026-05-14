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

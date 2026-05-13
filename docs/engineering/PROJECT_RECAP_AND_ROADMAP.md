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

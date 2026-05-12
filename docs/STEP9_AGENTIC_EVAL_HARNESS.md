# Step 9 — Agentic Evaluation Harness v0

This step creates the first executable evaluation harness for ForgeMoE-R1-Agent-Coder.

The harness evaluates a candidate patch against a repository-like task:

1. Copy task repository into an isolated work directory.
2. Run pre-patch tests.
3. Apply a unified diff patch.
4. Run post-patch tests.
5. Produce metrics and a JSON result artifact.

This is intentionally model-free. The goal is to establish the executable contract before connecting a model, verifier, reward model, or self-repair loop.

## Why this matters

A fullstack coding agent cannot be evaluated only with prompt/response benchmarks. It must operate over repositories, edit files, run tests, interpret failures, and repair its own patches.

This harness is the minimal foundation for:

- agentic trajectory SFT
- verifier-guided patch selection
- execution-feedback RL
- self-repair loops
- repo-level benchmark evaluation

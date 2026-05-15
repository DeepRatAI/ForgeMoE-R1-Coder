from __future__ import annotations

from pathlib import Path
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "results/local/sota_dataset_strategy_v0"

NORTH_STAR = (
    "Crear un sistema de AI Engineering SOTA capaz de tomar modelos de codigo "
    "aproximadamente 7B / 9B / 14B y transformarlos en agentes autonomos de "
    "codigo y desarrollo fullstack e2e capaces de competir codo a codo con "
    "modelos frontera/titanes como Opus serie 4, ChatGPT serie 5.x, Gemini Pro, "
    "DeepSeek V-series y equivalentes futuros."
)

DATA_LAYERS = [
    {
        "layer": "source_code_corpus",
        "purpose": "continued pretraining or domain adaptation substrate",
        "examples": ["permissively licensed code", "repo metadata", "language-balanced code shards"],
        "required_gates": ["license", "provenance", "dedup", "pii_secret_filter", "malware_filter"],
        "status": "not_acquired",
    },
    {
        "layer": "instruction_code_tasks",
        "purpose": "teach direct code transformation and structured compliance",
        "examples": ["bugfix instructions", "refactor instructions", "test-writing tasks"],
        "required_gates": ["schema_validation", "quality_scoring", "dedup"],
        "status": "scaffold_started",
    },
    {
        "layer": "repository_level_issue_tasks",
        "purpose": "train and evaluate repo-scale software engineering behavior",
        "examples": ["issue to patch", "multi-file edits", "dependency/API migrations"],
        "required_gates": ["reproducible_environment", "oracle_tests", "license", "contamination"],
        "status": "not_acquired",
    },
    {
        "layer": "synthetic_executable_tasks",
        "purpose": "produce controllable verified tasks at scale",
        "examples": ["generated repo bugs", "hidden tests", "repairable invalid patches"],
        "required_gates": ["execution_oracle", "difficulty_balance", "anti_template_overfit"],
        "status": "scaffold_started",
    },
    {
        "layer": "agentic_trajectories",
        "purpose": "teach inspect-plan-edit-test-repair loops",
        "examples": ["tool traces", "failed attempts", "test output", "repair decisions"],
        "required_gates": ["trace_schema", "privacy_filter", "reward_attribution"],
        "status": "partially_scaffolded",
    },
    {
        "layer": "preference_pairs",
        "purpose": "support DPO or equivalent preference optimization",
        "examples": ["chosen verified patch vs rejected wrong-file patch", "minimal patch vs broad rewrite"],
        "required_gates": ["pair_quality", "reward_margin", "verifier_consistency"],
        "status": "not_ready",
    },
    {
        "layer": "hidden_eval_holdout",
        "purpose": "measure true agentic capability without benchmark contamination",
        "examples": ["private repo tasks", "fresh GitHub issues", "unpublished synthetic tasks"],
        "required_gates": ["strict_isolation", "no_train_overlap", "strong_oracle"],
        "status": "not_built",
    },
]

QUALITY_DIMENSIONS = [
    "license_and_terms_acceptability",
    "provenance_traceability",
    "deduplication_strength",
    "contamination_risk",
    "execution_verifiability",
    "task_difficulty_signal",
    "multi_file_reasoning_value",
    "agentic_trace_value",
    "negative_example_value",
    "hidden_test_strength",
    "format_contract_compliance",
    "security_and_privacy_risk",
]

PUBLIC_DATASET_CANDIDATE_CLASSES = [
    {
        "class": "large_code_corpora",
        "role": "possible continued pretraining substrate",
        "examples": ["The Stack style corpora", "Software Heritage derived corpora", "permissive-code subsets"],
        "position": "candidate_only_until_license_provenance_filtering",
    },
    {
        "class": "repo_issue_benchmarks",
        "role": "evaluation and task inspiration",
        "examples": ["SWE-bench style tasks", "SWE-bench Verified style tasks", "SWE-bench Live style tasks"],
        "position": "eval_reference_not_blind_training_source",
    },
    {
        "class": "synthetic_repo_task_generators",
        "role": "task generation methodology reference",
        "examples": ["SWE-smith style task synthesis", "internal Forge task generator"],
        "position": "high_priority_direction_to_reimplement_and_improve",
    },
    {
        "class": "competitive_programming_and_code_reasoning",
        "role": "algorithmic reasoning auxiliary signal",
        "examples": ["LiveCodeBench style tasks", "BigCodeBench style tasks", "HumanEval/MBPP sanity checks"],
        "position": "auxiliary_not_primary_for_fullstack_agentic_e2e",
    },
]

TRAINING_MIXTURE_DRAFT = {
    "phase_0_scaffold_validation": {
        "purpose": "validate schemas, tokenization, manifests, upload paths, and gates",
        "data": ["step29_2", "step29_5"],
        "training_grade": False,
    },
    "phase_1_structured_intent_sft": {
        "purpose": "teach strict structured planning before patch emission",
        "data": ["curated synthetic structured intent", "verified human-authored edit intents"],
        "training_grade_requirements": ["schema_valid", "balanced_categories", "tokenization_passed", "quality_score_passed"],
    },
    "phase_2_patch_generation_sft": {
        "purpose": "teach minimal unified diffs that apply cleanly",
        "data": ["verified patches", "repo-localized tasks", "hidden-test checked synthetic tasks"],
        "training_grade_requirements": ["patch_apply_verified", "post_tests_verified", "wrong_file_negative_pairs"],
    },
    "phase_3_trajectory_sft": {
        "purpose": "teach agentic inspect-plan-edit-test-repair loops",
        "data": ["successful trajectories", "repaired failures", "tool traces"],
        "training_grade_requirements": ["trace_schema", "reward_attribution", "privacy_filter"],
    },
    "phase_4_preference_optimization": {
        "purpose": "optimize chosen/rejected outputs from executable verification",
        "data": ["chosen_rejected_pairs"],
        "training_grade_requirements": ["verifier_margin", "nontrivial_rejection", "no_leaked_gold_patch"],
    },
    "phase_5_verifiable_rl": {
        "purpose": "optimize agentic behavior with executable rewards",
        "data": ["on-policy attempts", "verified rewards", "budgeted rollouts"],
        "training_grade_requirements": ["stable_eval_harness", "anti_reward_hacking", "cost_budget"],
    },
}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def append_once(path: Path, marker: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in text:
        path.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def fenced(lang: str, body: str) -> str:
    return "```" + lang + "\n" + body + "\n```"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    step29_5_summary = json.loads(
        (PROJECT_ROOT / "results/local/structured_sft_curriculum_expansion_v1/summary.json").read_text(encoding="utf-8")
    )

    success_unit = fenced(
        "text",
        "\n".join(
            [
                "un modelo 7B/9B/14B + sistema agentic-verifiable",
                "capaz de resolver tareas reales de desarrollo complejo e2e",
                "con calidad, autonomia, robustez y eficiencia comparables",
                "a modelos frontera mucho mas grandes.",
            ]
        ),
    )

    north_star_doc = f"""
# ForgeMoE-R1-Agent-Coder - North Star

## Objetivo ultimo

{NORTH_STAR}

## Unidad real de exito

La unidad de exito no es que un job de entrenamiento termine. La unidad de exito es:

{success_unit}

## Anti-objetivos

No optimizamos para:

- demos;
- metricas superficiales;
- fine-tuning por si mismo;
- reduccion de loss sin evaluacion ejecutable;
- benchmarks contaminados;
- parches que pasan tests debiles sin resolver la tarea;
- resultados irreproducibles.

## Principio rector

Cada decision de datos, modelo, entrenamiento, evaluacion, infraestructura y documentacion debe empujar hacia capacidad real de ingenieria de software autonoma.

Cuando exista conflicto entre velocidad y estandar, prevalece el estandar.
"""

    layer_lines = []
    for item in DATA_LAYERS:
        layer_lines.append(f"### {item['layer']}")
        layer_lines.append("")
        layer_lines.append(f"- Purpose: `{item['purpose']}`")
        layer_lines.append(f"- Status: `{item['status']}`")
        layer_lines.append(f"- Required gates: `{', '.join(item['required_gates'])}`")
        layer_lines.append("")

    quality_lines = "\n".join(f"- `{item}`" for item in QUALITY_DIMENSIONS)

    candidate_lines = []
    for item in PUBLIC_DATASET_CANDIDATE_CLASSES:
        candidate_lines.append(f"### {item['class']}")
        candidate_lines.append("")
        candidate_lines.append(f"- Role: `{item['role']}`")
        candidate_lines.append(f"- Position: `{item['position']}`")
        candidate_lines.append(f"- Examples: `{', '.join(item['examples'])}`")
        candidate_lines.append("")

    scaffold_box = fenced("text", "scaffold / plumbing / format-validation data")

    strategy_doc = f"""
# SOTA Dataset Strategy, Governance & Acquisition Plan v0

## North Star

{NORTH_STAR}

## Critical classification

The current synthetic datasets from Step 29.2 and Step 29.5 are classified as:

{scaffold_box}

They are useful for contracts, manifests, tokenization, reproducibility and pipeline validation.

They are not the final training-grade corpus required for the project objective.

## Required data layers

{chr(10).join(layer_lines)}

## Dataset quality dimensions

Every candidate source or generated row must be scored against:

{quality_lines}

## Candidate dataset classes

{chr(10).join(candidate_lines)}

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
"""

    adr = f"""
# ADR-0032 - SOTA Dataset Governance Before Training-Grade GPU Runs

Status: Accepted
Date: 2026-05-15

## Context

The project has validated a complete scaffold for structured SFT data, tokenization, manifests, registry and GPU preflight.

However, the current datasets are deterministic scaffold data. They are not sufficient to support the project's North Star: transforming 7B/9B/14B code models into autonomous fullstack e2e coding agents competitive with frontier systems.

## Decision

Do not treat Step 29.2 or Step 29.5 synthetic data as final training-grade data.

Before any serious paid GPU training run, the project must define and enforce a SOTA dataset strategy covering:

- source code corpora;
- instruction code tasks;
- repository-level issue tasks;
- synthetic executable tasks;
- agentic trajectories;
- negative patch attempts;
- chosen/rejected preference pairs;
- hidden eval holdouts;
- provenance and licensing;
- deduplication and contamination controls;
- quality scoring and training mixture manifests.

## Rationale

For this project, data quality is a primary model capability lever.

A model cannot be expected to acquire frontier-level agentic software engineering behavior from a small synthetic scaffold. The data engine must become a core product of the system.

## Consequence

Step 30 GPU training is deferred until the data plane is sufficiently governed.

The project preserves the cost gate and moves next toward dataset acquisition, scoring, validation and heldout design.
"""

    plan = {
        "schema_version": "forgeagent.sota_dataset_governance_plan.v0",
        "plan_name": "sota_dataset_strategy_governance_v0",
        "north_star": NORTH_STAR,
        "current_dataset_classification": {
            "step29_2": "scaffold_plumbing_format_validation_data",
            "step29_5": "scaffold_plumbing_format_validation_data",
            "step29_5_rows": step29_5_summary["total_rows"],
            "training_grade": False,
        },
        "data_layers": DATA_LAYERS,
        "quality_dimensions": QUALITY_DIMENSIONS,
        "public_dataset_candidate_classes": PUBLIC_DATASET_CANDIDATE_CLASSES,
        "training_mixture_draft": TRAINING_MIXTURE_DRAFT,
        "gates_before_paid_training": [
            "dataset_lineage_gate",
            "license_and_terms_gate",
            "pii_secret_malware_filter_gate",
            "deduplication_gate",
            "benchmark_contamination_gate",
            "tokenization_gate",
            "quality_scoring_gate",
            "eval_holdout_gate",
            "training_mixture_manifest_gate",
            "explicit_cost_approval_gate",
        ],
        "next_recommended_step": "step29_7_dataset_source_matrix_and_acquisition_gate",
        "launches_training_job": False,
        "gpu_required": False,
        "requires_explicit_approval_before_training": True,
    }

    source_matrix = {
        "schema_version": "forgeagent.dataset_source_matrix.v0",
        "status": "candidate_classes_only",
        "rows": PUBLIC_DATASET_CANDIDATE_CLASSES,
        "blocking_before_ingestion": [
            "license_review",
            "terms_review",
            "provenance_review",
            "dedup_plan",
            "contamination_plan",
            "security_filter_plan",
            "privacy_filter_plan",
        ],
    }

    write(PROJECT_ROOT / "docs/strategy/PROJECT_NORTH_STAR.md", north_star_doc)
    write(PROJECT_ROOT / "docs/data/SOTA_DATASET_STRATEGY_AND_GOVERNANCE.md", strategy_doc)
    write(PROJECT_ROOT / "docs/engineering/ADR_0032_SOTA_DATASET_GOVERNANCE_BEFORE_TRAINING.md", adr)

    write_json(OUT_DIR / "dataset_governance_plan.json", plan)
    write_json(OUT_DIR / "dataset_source_matrix.json", source_matrix)

    append_once(
        PROJECT_ROOT / "docs/engineering/ENGINEERING_DECISION_RECORD.md",
        "## Update - Step 29.6 SOTA Dataset Governance",
        """
---

## Update - Step 29.6 SOTA Dataset Governance

Step 29.6 fixed the project North Star and formalized the dataset governance strategy before training-grade GPU runs.

The current Step 29.2 and Step 29.5 datasets are explicitly classified as scaffold/plumbing/format-validation data, not final training-grade data.

The project now requires dataset lineage, license review, deduplication, contamination control, quality scoring, heldout design and training mixture manifests before serious paid training.
""",
    )

    append_once(
        PROJECT_ROOT / "docs/engineering/PROJECT_RECAP_AND_ROADMAP.md",
        "## Step 29.6 Recap - SOTA Dataset Governance",
        """
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
""",
    )

    print(json.dumps(
        {
            "schema_version": plan["schema_version"],
            "plan_name": plan["plan_name"],
            "step29_5_rows": step29_5_summary["total_rows"],
            "current_data_training_grade": plan["current_dataset_classification"]["training_grade"],
            "data_layer_count": len(DATA_LAYERS),
            "quality_dimension_count": len(QUALITY_DIMENSIONS),
            "candidate_dataset_class_count": len(PUBLIC_DATASET_CANDIDATE_CLASSES),
            "launches_training_job": plan["launches_training_job"],
            "next_recommended_step": plan["next_recommended_step"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print("SOTA_DATASET_STRATEGY_DOCS_OK")


if __name__ == "__main__":
    main()

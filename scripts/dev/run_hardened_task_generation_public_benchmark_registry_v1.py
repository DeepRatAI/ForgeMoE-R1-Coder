from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_29_DIR = PROJECT_ROOT / "results/local/task_family_bundle_oracle_quality_v1"
PUBLIC_EVAL_MANIFEST = (
    PROJECT_ROOT / "results/local/public_eval_suite_scaleout_v1/dataset_exports/public_eval_suite_manifest.jsonl"
)
PRIVATE_SEED_MANIFEST = (
    PROJECT_ROOT / "results/local/private_heldout_seed_set_v1/dataset_exports/private_heldout_seed_manifest.jsonl"
)
MICRO_TASK_RESULTS = PROJECT_ROOT / "results/local/internal_synthetic_micro_generator_v0/task_results.jsonl"
OUT_DIR = PROJECT_ROOT / "results/local/hardened_task_generation_public_benchmark_registry_v1"

HIGH_SIMILARITY_THRESHOLD = 0.74
MODERATE_SIMILARITY_THRESHOLD = 0.48

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\s*[:=]"),
}

PUBLIC_REPORT_DISALLOWED_MARKERS = [
    "forge-private-heldout-",
    "forge-micro-private-heldout-",
    "diff --git",
    "assertEqual",
    "hidden_tests",
    "raw_model_output",
    "raw_outputs",
    "golden_patch",
    "rejected_patch",
    "public_overfit_patch",
]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(data: object) -> str:
    return sha256_text(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str))


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9_+\-. ]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def token_set(text: str) -> set[str]:
    return {token for token in normalize_text(text).split() if len(token) >= 3}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def scan_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern_name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": pattern_name, "count": len(matches)})
    return findings


def collect_private_identifier_hashes() -> set[str]:
    identifiers: set[str] = set()
    for row in read_jsonl(PRIVATE_SEED_MANIFEST):
        for key in ("task_id", "instruction_sha256", "repo_snapshot_sha256", "hidden_test_sha256"):
            value = row.get(key)
            if isinstance(value, str):
                identifiers.add(value)
                identifiers.add(sha256_text(value))
    for row in read_jsonl(MICRO_TASK_RESULTS):
        task_id = row.get("task_id")
        if isinstance(task_id, str) and row.get("split") == "private_heldout":
            identifiers.add(task_id)
            identifiers.add(sha256_text(task_id))
    return identifiers


def benchmark_registry_entries() -> list[dict[str, Any]]:
    raw_entries = [
        {
            "registry_id": "public-benchmark-humaneval",
            "benchmark_family": "unit_test_python_synthesis",
            "benchmark_name": "HumanEval",
            "task_modality": "function_completion",
            "contamination_risk": "high_public_canonical",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-mbpp",
            "benchmark_family": "unit_test_python_synthesis",
            "benchmark_name": "MBPP",
            "task_modality": "function_completion",
            "contamination_risk": "high_public_canonical",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-bigcodebench",
            "benchmark_family": "realistic_python_package_tasks",
            "benchmark_name": "BigCodeBench",
            "task_modality": "package_context_generation",
            "contamination_risk": "public_benchmark",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-livecodebench",
            "benchmark_family": "temporal_code_generation",
            "benchmark_name": "LiveCodeBench",
            "task_modality": "time_sliced_code_generation",
            "contamination_risk": "public_benchmark",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-swebench",
            "benchmark_family": "repository_issue_resolution",
            "benchmark_name": "SWE-bench",
            "task_modality": "repo_patch_from_issue",
            "contamination_risk": "public_repo_issue_benchmark",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-swebench-verified",
            "benchmark_family": "repository_issue_resolution",
            "benchmark_name": "SWE-bench Verified",
            "task_modality": "repo_patch_from_issue",
            "contamination_risk": "public_repo_issue_benchmark",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-swebench-multimodal",
            "benchmark_family": "repository_issue_resolution",
            "benchmark_name": "SWE-bench Multimodal",
            "task_modality": "repo_patch_from_issue_and_visual_context",
            "contamination_risk": "public_repo_issue_benchmark",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-apps",
            "benchmark_family": "competitive_programming",
            "benchmark_name": "APPS",
            "task_modality": "algorithmic_problem_solving",
            "contamination_risk": "public_problem_statement",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-codecontests",
            "benchmark_family": "competitive_programming",
            "benchmark_name": "CodeContests",
            "task_modality": "algorithmic_problem_solving",
            "contamination_risk": "public_problem_statement",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-ds1000",
            "benchmark_family": "data_science_code_generation",
            "benchmark_name": "DS-1000",
            "task_modality": "library_api_usage",
            "contamination_risk": "public_benchmark",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-repobench",
            "benchmark_family": "repository_context_completion",
            "benchmark_name": "RepoBench",
            "task_modality": "repository_context_completion",
            "contamination_risk": "public_benchmark",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
        {
            "registry_id": "public-benchmark-cruxeval",
            "benchmark_family": "code_reasoning",
            "benchmark_name": "CRUXEval",
            "task_modality": "input_output_reasoning",
            "contamination_risk": "public_benchmark",
            "policy": "reference_or_eval_only",
            "never_train_direct": True,
        },
    ]

    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        normalized = normalize_text(
            " ".join(
                [
                    entry["registry_id"],
                    entry["benchmark_family"],
                    entry["benchmark_name"],
                    entry["task_modality"],
                    entry["contamination_risk"],
                ]
            )
        )
        entries.append(
            {
                "schema_version": "forgeagent.public_benchmark_registry_entry.v1",
                **entry,
                "requires_contamination_scan": True,
                "direct_content_ingested": False,
                "corpus_downloaded_for_this_gate": False,
                "normalized_reference_sha256": sha256_text(normalized),
                "token_fingerprint_sha256": sha256_text(" ".join(sorted(token_set(normalized)))),
                "contains_raw_benchmark_tasks": False,
                "contains_private_identifiers": False,
            }
        )
    return entries


def current_reference_index() -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []

    for row in read_jsonl(PUBLIC_EVAL_MANIFEST):
        reference = {
            "schema_version": "forgeagent.current_reference_index_row.v1",
            "source": "public_eval_suite_scaleout_v1",
            "split": row.get("split", "public_eval"),
            "task_id_sha256": sha256_text(str(row.get("task_id", ""))),
            "task_family": row.get("task_family"),
            "behavioral_axes": row.get("behavioral_axes", []),
            "public_reference": True,
            "private_reference": False,
            "training_reference": False,
            "contains_raw_text": False,
            "contains_private_identifiers": False,
        }
        reference["reference_fingerprint_sha256"] = sha256_json(reference)
        references.append(reference)

    for row in read_jsonl(PRIVATE_SEED_MANIFEST):
        reference = {
            "schema_version": "forgeagent.current_reference_index_row.v1",
            "source": "private_heldout_seed_set_v1",
            "split": "private_heldout",
            "task_id_sha256": sha256_text(str(row.get("task_id", ""))),
            "task_family": row.get("task_family"),
            "behavioral_axes": row.get("behavioral_axes", []),
            "public_reference": False,
            "private_reference": True,
            "training_reference": False,
            "contains_raw_text": False,
            "contains_private_identifiers": False,
        }
        reference["reference_fingerprint_sha256"] = sha256_json(reference)
        references.append(reference)

    for row in read_jsonl(MICRO_TASK_RESULTS):
        split = str(row.get("split", "unknown"))
        reference = {
            "schema_version": "forgeagent.current_reference_index_row.v1",
            "source": "internal_synthetic_micro_generator_v0",
            "split": split,
            "task_id_sha256": sha256_text(str(row.get("task_id", ""))),
            "task_family": row.get("task_family"),
            "behavioral_axes": [],
            "public_reference": False,
            "private_reference": split == "private_heldout",
            "training_reference": split == "train",
            "contains_raw_text": False,
            "contains_private_identifiers": False,
        }
        reference["reference_fingerprint_sha256"] = sha256_json(reference)
        references.append(reference)

    bundle_manifest_path = STEP29_29_DIR / "task_family_bundle_manifest.json"
    if bundle_manifest_path.exists():
        for bundle in read_json(bundle_manifest_path).get("bundles", []):
            reference = {
                "schema_version": "forgeagent.current_reference_index_row.v1",
                "source": "task_family_bundle_oracle_quality_v1",
                "split": bundle.get("split"),
                "task_id_sha256": bundle.get("task_bundle_fingerprint"),
                "task_family": "task_family_bundle",
                "behavioral_axes": bundle.get("product_types", []),
                "public_reference": False,
                "private_reference": bundle.get("split") == "private_heldout",
                "training_reference": bundle.get("split") == "train",
                "contains_raw_text": False,
                "contains_private_identifiers": False,
            }
            reference["reference_fingerprint_sha256"] = sha256_json(reference)
            references.append(reference)

    return references


def hardened_blueprints() -> list[dict[str, Any]]:
    specs = [
        (
            "forge-hard-train-config-env-precedence",
            "train",
            "configuration_precedence_bugfix",
            ["multi_file", "environment_precedence", "fallback_defaults", "schema_validation"],
            "medium",
            "A deterministic repo task where config file defaults, environment overrides and explicit CLI flags must resolve in the correct order.",
        ),
        (
            "forge-hard-train-pagination-idempotency",
            "train",
            "api_pagination_idempotency_fix",
            ["multi_file", "pagination", "idempotent_retry", "stateful_boundary"],
            "medium",
            "A service adapter task requiring stable cursor handling, duplicate retry safety and explicit error propagation.",
        ),
        (
            "forge-hard-train-path-normalization-security",
            "train",
            "path_normalization_security_fix",
            ["multi_file", "path_traversal_guard", "platform_paths", "input_validation"],
            "hard",
            "A filesystem utility task with platform-aware normalization and explicit rejection of traversal outside an allowed root.",
        ),
        (
            "forge-hard-train-transactional-upsert",
            "train",
            "transactional_state_update_fix",
            ["multi_file", "transaction_boundary", "rollback_semantics", "concurrent_retry"],
            "hard",
            "A repository service task where partial updates must become atomic and retry-safe under duplicate requests.",
        ),
        (
            "forge-hard-eval-json-schema-evolution",
            "eval",
            "api_schema_migration_bugfix",
            ["multi_file", "backward_compatibility", "json_schema", "typed_error_shape"],
            "hard",
            "An API task requiring old and new payload variants to be accepted while preserving strict validation failures.",
        ),
        (
            "forge-hard-eval-time-window-boundary",
            "eval",
            "time_window_boundary_bugfix",
            ["multi_file", "timezone_boundary", "inclusive_exclusive_edges", "deterministic_clock"],
            "hard",
            "A scheduler task where boundary windows must be stable across date changes and injected clocks.",
        ),
        (
            "forge-hard-eval-dependency-api-migration",
            "eval",
            "dependency_api_migration_fix",
            ["multi_file", "adapter_boundary", "deprecation_compatibility", "mock_contract"],
            "medium",
            "A client adapter task requiring compatibility with two dependency API shapes without branching leaks to callers.",
        ),
        (
            "forge-hard-private-authorization-scope",
            "private_heldout",
            "authorization_scope_bugfix",
            ["multi_file", "tenant_isolation", "permission_boundary", "negative_authorization_tests"],
            "hard",
            "A service task requiring tenant-scoped access checks and hidden tests for cross-tenant denial behavior.",
        ),
        (
            "forge-hard-private-cache-invalidation",
            "private_heldout",
            "cache_invalidation_consistency_fix",
            ["multi_file", "cache_invalidation", "stale_read_prevention", "event_ordering"],
            "hard",
            "A cache/task-queue task where updates must invalidate derived reads after ordered domain events.",
        ),
        (
            "forge-hard-private-parser-error-recovery",
            "private_heldout",
            "parser_error_recovery_bugfix",
            ["multi_file", "parser_recovery", "structured_errors", "partial_input_handling"],
            "hard",
            "A parser task requiring structured error recovery without losing valid trailing records.",
        ),
        (
            "forge-hard-public-eval-observability-redaction",
            "public_eval",
            "observability_redaction_bugfix",
            ["multi_file", "structured_logging", "secret_redaction", "failure_diagnostics"],
            "medium",
            "A logging task requiring structured diagnostics while redacting tokens and preserving debuggable failure causes.",
        ),
        (
            "forge-hard-public-eval-concurrency-ordering",
            "public_eval",
            "deterministic_ordering_bugfix",
            ["multi_file", "ordering_stability", "retry_race", "deterministic_merge"],
            "medium",
            "A workflow task requiring deterministic merge order across retry batches without using wall-clock ordering.",
        ),
    ]

    blueprints: list[dict[str, Any]] = []
    for blueprint_id, split, task_family, axes, difficulty, template in specs:
        normalized = normalize_text(" ".join([blueprint_id, split, task_family, difficulty, *axes, template]))
        blueprints.append(
            {
                "schema_version": "forgeagent.hardened_task_blueprint.v1",
                "blueprint_id": blueprint_id,
                "blueprint_id_sha256": sha256_text(blueprint_id),
                "split": split,
                "task_family": task_family,
                "behavioral_axes": axes,
                "difficulty_label": difficulty,
                "repo_shape": "temporary_git_repository",
                "expected_patch_format": "git_diff",
                "required_verification_contract": {
                    "git_apply_check": True,
                    "pre_test_fail": True,
                    "post_public_pass": True,
                    "post_hidden_pass": True,
                    "public_overfit_negative": True,
                    "wrong_file_negative": True,
                    "semantic_noop_negative": True,
                },
                "generation_constraints": {
                    "no_private_seed_reuse": True,
                    "no_public_benchmark_task_reuse": True,
                    "no_patch_content_exported_in_registry": True,
                    "oracle_must_be_executable": True,
                    "must_use_real_temp_git_repo": True,
                },
                "instruction_template_sha256": sha256_text(template),
                "blueprint_fingerprint_sha256": sha256_text(normalized),
                "token_fingerprint_sha256": sha256_text(" ".join(sorted(token_set(normalized)))),
                "contains_raw_text": False,
                "contains_patch_content": False,
                "contains_private_identifiers": False,
            }
        )
    return blueprints


def reference_comparison_text(reference: dict[str, Any]) -> str:
    return normalize_text(
        " ".join(
            [
                str(reference.get("source", "")),
                str(reference.get("split", "")),
                str(reference.get("task_family", "")),
                " ".join(str(axis) for axis in reference.get("behavioral_axes", [])),
                str(reference.get("task_id_sha256", ""))[:12],
            ]
        )
    )


def blueprint_comparison_text(blueprint: dict[str, Any]) -> str:
    return normalize_text(
        " ".join(
            [
                blueprint["blueprint_id"],
                blueprint["split"],
                blueprint["task_family"],
                blueprint["difficulty_label"],
                " ".join(blueprint["behavioral_axes"]),
            ]
        )
    )


def registry_comparison_text(entry: dict[str, Any]) -> str:
    return normalize_text(
        " ".join(
            [
                entry["registry_id"],
                entry["benchmark_family"],
                entry["benchmark_name"],
                entry["task_modality"],
                entry["contamination_risk"],
            ]
        )
    )


def compare_blueprints(
    blueprints: list[dict[str, Any]],
    references: list[dict[str, Any]],
    registry_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    exact_current_collisions: list[dict[str, Any]] = []
    exact_benchmark_collisions: list[dict[str, Any]] = []
    current_similarities: list[dict[str, Any]] = []
    benchmark_similarities: list[dict[str, Any]] = []
    blueprint_pair_similarities: list[dict[str, Any]] = []

    reference_hashes = {reference["reference_fingerprint_sha256"] for reference in references}
    benchmark_hashes = {entry["normalized_reference_sha256"] for entry in registry_entries}

    for blueprint in blueprints:
        if blueprint["blueprint_fingerprint_sha256"] in reference_hashes:
            exact_current_collisions.append(
                {
                    "blueprint_id_sha256": blueprint["blueprint_id_sha256"],
                    "blueprint_fingerprint_sha256": blueprint["blueprint_fingerprint_sha256"],
                }
            )
        if blueprint["blueprint_fingerprint_sha256"] in benchmark_hashes:
            exact_benchmark_collisions.append(
                {
                    "blueprint_id_sha256": blueprint["blueprint_id_sha256"],
                    "blueprint_fingerprint_sha256": blueprint["blueprint_fingerprint_sha256"],
                }
            )

        blueprint_tokens = token_set(blueprint_comparison_text(blueprint))
        for reference in references:
            score = jaccard(blueprint_tokens, token_set(reference_comparison_text(reference)))
            if score >= MODERATE_SIMILARITY_THRESHOLD:
                current_similarities.append(
                    {
                        "blueprint_id_sha256": blueprint["blueprint_id_sha256"],
                        "reference_source": reference["source"],
                        "reference_split": reference["split"],
                        "reference_fingerprint_sha256": reference["reference_fingerprint_sha256"],
                        "similarity_score": round(score, 4),
                        "similarity_band": "high" if score >= HIGH_SIMILARITY_THRESHOLD else "moderate",
                        "contains_raw_text": False,
                        "contains_private_identifiers": False,
                    }
                )

        for entry in registry_entries:
            score = jaccard(blueprint_tokens, token_set(registry_comparison_text(entry)))
            if score >= MODERATE_SIMILARITY_THRESHOLD:
                benchmark_similarities.append(
                    {
                        "blueprint_id_sha256": blueprint["blueprint_id_sha256"],
                        "registry_id": entry["registry_id"],
                        "normalized_reference_sha256": entry["normalized_reference_sha256"],
                        "similarity_score": round(score, 4),
                        "similarity_band": "high" if score >= HIGH_SIMILARITY_THRESHOLD else "moderate",
                        "contains_raw_benchmark_tasks": False,
                        "contains_private_identifiers": False,
                    }
                )

    for index, left in enumerate(blueprints):
        for right in blueprints[index + 1 :]:
            score = jaccard(token_set(blueprint_comparison_text(left)), token_set(blueprint_comparison_text(right)))
            if score >= MODERATE_SIMILARITY_THRESHOLD:
                blueprint_pair_similarities.append(
                    {
                        "left_blueprint_id_sha256": left["blueprint_id_sha256"],
                        "left_split": left["split"],
                        "right_blueprint_id_sha256": right["blueprint_id_sha256"],
                        "right_split": right["split"],
                        "similarity_score": round(score, 4),
                        "similarity_band": "high" if score >= HIGH_SIMILARITY_THRESHOLD else "moderate",
                        "contains_raw_text": False,
                        "contains_private_identifiers": False,
                    }
                )

    eval_private_high_pairs = [
        row
        for row in blueprint_pair_similarities
        if row["similarity_band"] == "high" and {row["left_split"], row["right_split"]} == {"eval", "private_heldout"}
    ]
    current_private_or_eval_high = [
        row
        for row in current_similarities
        if row["similarity_band"] == "high" and row["reference_split"] in {"eval", "private_heldout", "public_eval"}
    ]
    benchmark_high = [row for row in benchmark_similarities if row["similarity_band"] == "high"]

    return {
        "schema_version": "forgeagent.hardened_generation_similarity_report.v1",
        "exact_current_reference_collision_count": len(exact_current_collisions),
        "exact_public_benchmark_registry_collision_count": len(exact_benchmark_collisions),
        "moderate_current_reference_similarity_count": sum(
            1 for row in current_similarities if row["similarity_band"] == "moderate"
        ),
        "high_current_reference_similarity_count": sum(1 for row in current_similarities if row["similarity_band"] == "high"),
        "high_current_private_or_eval_reference_similarity_count": len(current_private_or_eval_high),
        "moderate_public_benchmark_registry_similarity_count": sum(
            1 for row in benchmark_similarities if row["similarity_band"] == "moderate"
        ),
        "high_public_benchmark_registry_similarity_count": len(benchmark_high),
        "hardened_blueprint_pair_high_similarity_count": sum(
            1 for row in blueprint_pair_similarities if row["similarity_band"] == "high"
        ),
        "hardened_eval_private_high_similarity_pair_count": len(eval_private_high_pairs),
        "exact_current_reference_collisions": exact_current_collisions,
        "exact_public_benchmark_registry_collisions": exact_benchmark_collisions,
        "current_reference_similarities": current_similarities,
        "public_benchmark_registry_similarities": benchmark_similarities,
        "hardened_blueprint_pair_similarities": blueprint_pair_similarities,
        "contains_raw_text": False,
        "contains_raw_benchmark_tasks": False,
        "contains_private_identifiers": False,
    }


def build_privacy_report(paths: dict[str, Path], private_identifier_hashes: set[str]) -> dict[str, Any]:
    scanned_files = [path for path in paths.values() if path.exists()]
    secret_findings: list[dict[str, Any]] = []
    private_identifier_leaks: list[dict[str, Any]] = []
    marker_leaks: list[dict[str, Any]] = []

    for path in scanned_files:
        text = path.read_text(encoding="utf-8")
        for finding in scan_secrets(text):
            secret_findings.append({"file": rel(path), **finding})
        for identifier in private_identifier_hashes:
            if identifier.startswith("forge-private-heldout-") or identifier.startswith("forge-micro-private-heldout-"):
                if identifier in text:
                    private_identifier_leaks.append({"file": rel(path), "identifier_sha256": sha256_text(identifier)})
        if path.name.startswith("public_safe_"):
            for marker in PUBLIC_REPORT_DISALLOWED_MARKERS:
                if marker in text:
                    marker_leaks.append({"file": rel(path), "marker_sha256": sha256_text(marker)})

    return {
        "schema_version": "forgeagent.hardened_generation_benchmark_registry_privacy_report.v1",
        "scanned_files": [rel(path) for path in scanned_files],
        "public_report_files": [rel(path) for path in scanned_files if path.name.startswith("public_safe_")],
        "secret_finding_count": len(secret_findings),
        "private_identifier_leak_count": len(private_identifier_leaks),
        "public_report_marker_leak_count": len(marker_leaks),
        "secret_findings": secret_findings,
        "private_identifier_leaks": private_identifier_leaks,
        "public_report_marker_leaks": marker_leaks,
        "passed": not secret_findings and not private_identifier_leaks and not marker_leaks,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not (STEP29_29_DIR / "summary.json").exists():
        raise SystemExit("missing Step 29.29 summary; run scripts/dev/step29_29_doctor.sh first")

    step29_29_summary = read_json(STEP29_29_DIR / "summary.json")
    if step29_29_summary.get("oracle_quality_certification_complete") is not True:
        raise SystemExit("Step 29.29 oracle quality certification is not complete")

    registry_entries = benchmark_registry_entries()
    references = current_reference_index()
    blueprints = hardened_blueprints()
    similarity_report = compare_blueprints(blueprints, references, registry_entries)

    split_counts = Counter(blueprint["split"] for blueprint in blueprints)
    registry_by_policy = Counter(entry["policy"] for entry in registry_entries)
    registry_by_risk = Counter(entry["contamination_risk"] for entry in registry_entries)

    public_benchmark_registry = {
        "schema_version": "forgeagent.public_benchmark_contamination_registry.v1",
        "registry_name": "public_benchmark_contamination_registry_v1",
        "registry_entry_count": len(registry_entries),
        "policy_counts": dict(sorted(registry_by_policy.items())),
        "contamination_risk_counts": dict(sorted(registry_by_risk.items())),
        "full_public_benchmark_corpus_scan_complete": False,
        "direct_benchmark_content_ingested": False,
        "corpus_downloaded_for_this_gate": False,
        "registry_seed_entries_are_exhaustive": False,
        "entries": registry_entries,
        "contains_raw_benchmark_tasks": False,
        "contains_private_identifiers": False,
    }

    current_public_eval_reference_index = {
        "schema_version": "forgeagent.current_public_eval_reference_index.v1",
        "reference_count": len(references),
        "public_eval_reference_count": sum(1 for row in references if row["split"] == "public_eval"),
        "private_reference_count": sum(1 for row in references if row["private_reference"]),
        "training_reference_count": sum(1 for row in references if row["training_reference"]),
        "rows": references,
        "hash_only": True,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }

    hardened_blueprint_manifest = {
        "schema_version": "forgeagent.hardened_task_blueprint_manifest.v1",
        "blueprint_count": len(blueprints),
        "split_counts": dict(sorted(split_counts.items())),
        "blueprints": blueprints,
        "contains_raw_text": False,
        "contains_patch_content": False,
        "contains_private_identifiers": False,
    }

    public_benchmark_registry_ready = len(registry_entries) >= 10 and all(
        entry["requires_contamination_scan"] is True and entry["never_train_direct"] is True
        for entry in registry_entries
    )
    hardened_generation_plan_ready = (
        len(blueprints) >= 12
        and split_counts["train"] >= 4
        and split_counts["eval"] >= 3
        and split_counts["private_heldout"] >= 3
        and split_counts["public_eval"] >= 2
        and similarity_report["exact_current_reference_collision_count"] == 0
        and similarity_report["exact_public_benchmark_registry_collision_count"] == 0
        and similarity_report["high_current_private_or_eval_reference_similarity_count"] == 0
        and similarity_report["high_public_benchmark_registry_similarity_count"] == 0
        and similarity_report["hardened_eval_private_high_similarity_pair_count"] == 0
    )

    blocked_reasons = [
        "full_public_benchmark_corpus_scan_incomplete",
        "license_policy_still_scaffold_only",
        "final_training_release_policy_not_integrated",
        "executable_hardened_task_repos_not_generated_yet",
        "step29_29_existing_eval_private_scaffold_similarity_remains_blocked",
    ]

    gate_decision = {
        "schema_version": "forgeagent.hardened_generation_public_benchmark_registry_gate_decision.v1",
        "gate_name": "hardened_task_generation_public_benchmark_registry_v1",
        "source_step": "step29_29_task_family_bundle_oracle_quality_v1",
        "source_step_ready": True,
        "public_benchmark_registry_ready": public_benchmark_registry_ready,
        "hardened_generation_plan_ready": hardened_generation_plan_ready,
        "full_public_benchmark_corpus_scan_complete": False,
        "direct_benchmark_content_ingested": False,
        "corpus_downloaded_for_this_gate": False,
        "exact_current_reference_collision_count": similarity_report["exact_current_reference_collision_count"],
        "exact_public_benchmark_registry_collision_count": similarity_report[
            "exact_public_benchmark_registry_collision_count"
        ],
        "high_current_private_or_eval_reference_similarity_count": similarity_report[
            "high_current_private_or_eval_reference_similarity_count"
        ],
        "high_public_benchmark_registry_similarity_count": similarity_report[
            "high_public_benchmark_registry_similarity_count"
        ],
        "hardened_eval_private_high_similarity_pair_count": similarity_report[
            "hardened_eval_private_high_similarity_pair_count"
        ],
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "blocked_reasons": blocked_reasons,
        "next_recommended_step": "step29_31_hardened_executable_task_generator_v1",
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
    }

    public_safe_report = {
        "schema_version": "forgeagent.public_safe_hardened_generation_benchmark_registry_report.v1",
        "report_name": "hardened_task_generation_public_benchmark_registry_v1_public_safe",
        "source_step": "step29_29_task_family_bundle_oracle_quality_v1",
        "benchmark_registry_entry_count": len(registry_entries),
        "current_reference_count": len(references),
        "current_public_eval_reference_count": current_public_eval_reference_index["public_eval_reference_count"],
        "current_private_reference_count": current_public_eval_reference_index["private_reference_count"],
        "hardened_blueprint_count": len(blueprints),
        "hardened_train_blueprint_count": split_counts["train"],
        "hardened_eval_blueprint_count": split_counts["eval"],
        "hardened_private_heldout_blueprint_count": split_counts["private_heldout"],
        "hardened_public_eval_blueprint_count": split_counts["public_eval"],
        "public_benchmark_registry_ready": public_benchmark_registry_ready,
        "hardened_generation_plan_ready": hardened_generation_plan_ready,
        "full_public_benchmark_corpus_scan_complete": False,
        "exact_current_reference_collision_count": similarity_report["exact_current_reference_collision_count"],
        "exact_public_benchmark_registry_collision_count": similarity_report[
            "exact_public_benchmark_registry_collision_count"
        ],
        "high_current_private_or_eval_reference_similarity_count": similarity_report[
            "high_current_private_or_eval_reference_similarity_count"
        ],
        "high_public_benchmark_registry_similarity_count": similarity_report[
            "high_public_benchmark_registry_similarity_count"
        ],
        "hardened_eval_private_high_similarity_pair_count": similarity_report[
            "hardened_eval_private_high_similarity_pair_count"
        ],
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "raw_rows_included": False,
        "raw_text_included": False,
        "raw_benchmark_tasks_included": False,
        "private_identifier_values_included": False,
        "patch_content_included": False,
        "prompt_content_included": False,
        "withheld_eval_content_included": False,
        "model_outputs_included": False,
        "blocked_reasons": blocked_reasons,
        "next_recommended_step": "step29_31_hardened_executable_task_generator_v1",
    }

    paths = {
        "public_benchmark_registry": OUT_DIR / "public_benchmark_registry.json",
        "current_reference_index": OUT_DIR / "current_public_eval_reference_index.json",
        "hardened_blueprints_json": OUT_DIR / "hardened_task_blueprints.json",
        "hardened_blueprints_jsonl": OUT_DIR / "hardened_task_blueprints.jsonl",
        "similarity_report": OUT_DIR / "hardened_generation_similarity_report.json",
        "gate_decision": OUT_DIR / "benchmark_contamination_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_hardened_generation_benchmark_registry_report.json",
    }

    write_json(paths["public_benchmark_registry"], public_benchmark_registry)
    write_json(paths["current_reference_index"], current_public_eval_reference_index)
    write_json(paths["hardened_blueprints_json"], hardened_blueprint_manifest)
    write_jsonl(paths["hardened_blueprints_jsonl"], blueprints)
    write_json(paths["similarity_report"], similarity_report)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_safe_report)

    privacy_report = build_privacy_report(paths, collect_private_identifier_hashes())
    privacy_path = OUT_DIR / "hardened_generation_benchmark_registry_privacy_report.json"
    write_json(privacy_path, privacy_report)
    paths["privacy_report"] = privacy_path

    summary = {
        "schema_version": "forgeagent.hardened_generation_public_benchmark_registry_summary.v1",
        "gate_name": "hardened_task_generation_public_benchmark_registry_v1",
        "source_step": "step29_29_task_family_bundle_oracle_quality_v1",
        "source_step_ready": True,
        "git_commit": git_commit(),
        "benchmark_registry_entry_count": len(registry_entries),
        "benchmark_registry_never_train_direct_count": sum(1 for entry in registry_entries if entry["never_train_direct"]),
        "benchmark_registry_requires_scan_count": sum(
            1 for entry in registry_entries if entry["requires_contamination_scan"]
        ),
        "current_reference_count": len(references),
        "current_public_eval_reference_count": current_public_eval_reference_index["public_eval_reference_count"],
        "current_private_reference_count": current_public_eval_reference_index["private_reference_count"],
        "current_training_reference_count": current_public_eval_reference_index["training_reference_count"],
        "hardened_blueprint_count": len(blueprints),
        "hardened_train_blueprint_count": split_counts["train"],
        "hardened_eval_blueprint_count": split_counts["eval"],
        "hardened_private_heldout_blueprint_count": split_counts["private_heldout"],
        "hardened_public_eval_blueprint_count": split_counts["public_eval"],
        "public_benchmark_registry_ready": public_benchmark_registry_ready,
        "hardened_generation_plan_ready": hardened_generation_plan_ready,
        "exact_current_reference_collision_count": similarity_report["exact_current_reference_collision_count"],
        "exact_public_benchmark_registry_collision_count": similarity_report[
            "exact_public_benchmark_registry_collision_count"
        ],
        "high_current_private_or_eval_reference_similarity_count": similarity_report[
            "high_current_private_or_eval_reference_similarity_count"
        ],
        "high_public_benchmark_registry_similarity_count": similarity_report[
            "high_public_benchmark_registry_similarity_count"
        ],
        "hardened_eval_private_high_similarity_pair_count": similarity_report[
            "hardened_eval_private_high_similarity_pair_count"
        ],
        "moderate_current_reference_similarity_count": similarity_report["moderate_current_reference_similarity_count"],
        "moderate_public_benchmark_registry_similarity_count": similarity_report[
            "moderate_public_benchmark_registry_similarity_count"
        ],
        "full_public_benchmark_corpus_scan_complete": False,
        "direct_benchmark_content_ingested": False,
        "corpus_downloaded_for_this_gate": False,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "privacy_scan_passed": privacy_report["passed"],
        "public_safe_report_ready": True,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_31_hardened_executable_task_generator_v1",
        "artifacts": {name: rel(path) for name, path in paths.items()},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

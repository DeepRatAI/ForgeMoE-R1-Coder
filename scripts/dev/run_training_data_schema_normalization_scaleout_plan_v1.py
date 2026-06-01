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
STEP29_25_DIR = PROJECT_ROOT / "results/local/training_data_governance_scaleout_v1"
OUT_DIR = PROJECT_ROOT / "results/local/training_data_schema_normalization_scaleout_plan_v1"

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\\s*[:=]"),
}

PUBLIC_REPORT_DISALLOWED_MARKERS = [
    "forge-private-heldout-",
    "forge-micro-private-heldout-",
    "diff --git",
    "assertEqual",
    "hidden_tests",
    "raw_model_output",
    "raw_outputs",
]


CANONICAL_SCHEMAS: list[dict[str, Any]] = [
    {
        "canonical_schema_id": "forgeagent.training.patch_sft_row.v1",
        "data_product": "patch_sft",
        "purpose": "Supervised final-patch learning from executable repository tasks.",
        "required_fields": [
            "row_id",
            "source_task_ref",
            "split",
            "instruction_ref",
            "repo_snapshot_ref",
            "public_context_ref",
            "target_patch_ref",
            "verification_ref",
            "provenance_ref",
            "governance_ref",
            "quality_ref",
        ],
        "required_controls": [
            "split_train_only",
            "patch_applies_with_git_apply_check",
            "pre_public_tests_fail",
            "post_public_tests_pass",
            "post_withheld_eval_oracle_pass",
            "no_withheld_eval_content_in_row",
            "license_provenance_complete",
            "contamination_scan_complete",
            "secret_scan_clean",
        ],
        "allowed_training_use": "future_sft_after_training_grade_gate",
    },
    {
        "canonical_schema_id": "forgeagent.training.trajectory_sft_row.v1",
        "data_product": "trajectory_sft",
        "purpose": "Agentic process learning for inspect, plan, edit, test, repair and verify traces.",
        "required_fields": [
            "row_id",
            "source_task_ref",
            "split",
            "message_trace_ref",
            "tool_event_trace_ref",
            "attempt_refs",
            "final_patch_ref",
            "verification_ref",
            "provenance_ref",
            "governance_ref",
            "quality_ref",
        ],
        "required_controls": [
            "split_train_only",
            "tool_events_ordered",
            "failed_attempts_preserved_as_refs",
            "final_attempt_verified",
            "no_withheld_eval_content_in_row",
            "license_provenance_complete",
            "contamination_scan_complete",
            "secret_scan_clean",
        ],
        "allowed_training_use": "future_trajectory_sft_after_training_grade_gate",
    },
    {
        "canonical_schema_id": "forgeagent.training.preference_pair_row.v1",
        "data_product": "preference_pair",
        "purpose": "Chosen/rejected optimization from executable oracle outcomes.",
        "required_fields": [
            "row_id",
            "source_task_ref",
            "split",
            "prompt_ref",
            "chosen_attempt_ref",
            "rejected_attempt_ref",
            "preference_label_ref",
            "verification_ref",
            "provenance_ref",
            "governance_ref",
            "quality_ref",
        ],
        "required_controls": [
            "split_train_only",
            "chosen_attempt_verified_positive",
            "rejected_attempt_verified_negative",
            "preference_reason_from_oracle",
            "no_withheld_eval_content_in_row",
            "license_provenance_complete",
            "contamination_scan_complete",
            "secret_scan_clean",
        ],
        "allowed_training_use": "future_preference_optimization_after_training_grade_gate",
    },
    {
        "canonical_schema_id": "forgeagent.training.repair_trace_row.v1",
        "data_product": "repair_trace",
        "purpose": "Self-repair learning from failed attempt, observed failure and verified correction.",
        "required_fields": [
            "row_id",
            "source_task_ref",
            "split",
            "negative_attempt_ref",
            "failure_signal_ref",
            "repair_action_ref",
            "positive_attempt_ref",
            "verification_ref",
            "provenance_ref",
            "governance_ref",
            "quality_ref",
        ],
        "required_controls": [
            "split_train_only",
            "negative_attempt_executed",
            "failure_signal_grounded_in_tests",
            "positive_attempt_verified",
            "no_withheld_eval_content_in_row",
            "license_provenance_complete",
            "contamination_scan_complete",
            "secret_scan_clean",
        ],
        "allowed_training_use": "future_repair_learning_after_training_grade_gate",
    },
    {
        "canonical_schema_id": "forgeagent.eval.executable_task_ref.v1",
        "data_product": "executable_task_ref",
        "purpose": "Evaluation and private-heldout task references kept out of training rows.",
        "required_fields": [
            "row_id",
            "source_task_ref",
            "split",
            "task_family",
            "behavioral_axes",
            "repo_snapshot_ref",
            "oracle_ref",
            "withheld_eval_ref",
            "provenance_ref",
            "governance_ref",
        ],
        "required_controls": [
            "never_train_when_eval_or_private",
            "expected_solution_withheld_from_training",
            "task_level_private_reporting_disallowed",
            "private_identifier_redaction",
            "secret_scan_clean",
        ],
        "allowed_training_use": "never_for_eval_or_private_rows",
    },
]

SOURCE_SCHEMA_TO_CANONICAL = {
    "forgeagent.patch_sft_row.v0": "forgeagent.training.patch_sft_row.v1",
    "forgeagent.preference_pair_seed.v0": "forgeagent.training.preference_pair_row.v1",
    "forgeagent.agentic_trajectory_seed.v0": "forgeagent.training.trajectory_sft_row.v1",
    "forgeagent.agentic_trajectory_record.v1": "forgeagent.training.trajectory_sft_row.v1",
    "forgeagent.repair_trace_row.v1": "forgeagent.training.repair_trace_row.v1",
    "forgeagent.trajectory_preference_row.v1": "forgeagent.training.preference_pair_row.v1",
    "forgeagent.trajectory_sft_row.v1": "forgeagent.training.trajectory_sft_row.v1",
    "forgeagent.synthetic_executable_task.v0": "forgeagent.eval.executable_task_ref.v1",
}


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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(data: object) -> str:
    return sha256_text(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str))


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def scan_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern_name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": pattern_name, "count": len(matches)})
    return findings


def canonical_schema_index() -> dict[str, dict[str, Any]]:
    return {schema["canonical_schema_id"]: schema for schema in CANONICAL_SCHEMAS}


def build_schema_mapping(admissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schemas = canonical_schema_index()
    rows: list[dict[str, Any]] = []
    for admission in admissions:
        source_schema = admission["schema"]
        canonical_id = SOURCE_SCHEMA_TO_CANONICAL.get(source_schema)
        canonical = schemas.get(canonical_id, {})
        current_training_status = (
            "scaffold_only" if admission["scaffold_admitted"] else "not_training_admitted"
        )
        if admission["training_grade_admitted"]:
            current_training_status = "training_grade"
        rows.append(
            {
                "schema_version": "forgeagent.training_data_schema_mapping_row.v1",
                "source_row_sha256": admission["row_sha256"],
                "source_file": admission["source_file"],
                "source_row_index": admission["row_index"],
                "source_schema": source_schema,
                "canonical_schema_id": canonical_id,
                "data_product": canonical.get("data_product", "unknown"),
                "split": admission["split"],
                "source_row_type": admission["row_type"],
                "mapping_status": "mapped" if canonical_id else "unmapped",
                "current_training_status": current_training_status,
                "training_grade_admitted": False,
                "normalization_output_allowed": admission["scaffold_admitted"],
                "normalization_output_kind": "manifest_ref_only",
            }
        )
    return rows


def build_schema_gap_report(mapping_rows: list[dict[str, Any]], admissions: list[dict[str, Any]]) -> dict[str, Any]:
    mapped_count = sum(1 for row in mapping_rows if row["mapping_status"] == "mapped")
    unmapped_count = len(mapping_rows) - mapped_count
    canonical_counts = Counter(row["canonical_schema_id"] or "unmapped" for row in mapping_rows)
    source_schema_counts = Counter(row["source_schema"] for row in mapping_rows)
    training_grade_reasons = Counter(
        reason
        for row in admissions
        if not row["training_grade_admitted"]
        for reason in row["training_grade_decision_reasons"]
    )
    blocking_gaps = [
        "canonical_rows_are_manifest_refs_only_not_training_payloads",
        "training_grade_rows_absent",
        "license_provenance_not_complete_for_all_training_rows",
        "contamination_scan_not_complete_for_all_rows",
        "row_level_oracle_quality_not_certified_for_all_training_products",
        "scaleout_seed_repo_license_registry_not_implemented",
        "deduplication_and_near_duplicate_scanner_not_implemented",
        "large_scale_generator_not_yet_executed",
    ]
    return {
        "schema_version": "forgeagent.training_data_schema_gap_report.v1",
        "source_row_count": len(mapping_rows),
        "mapped_source_row_count": mapped_count,
        "unmapped_source_row_count": unmapped_count,
        "canonical_schema_count": len(CANONICAL_SCHEMAS),
        "canonical_schema_counts": dict(sorted(canonical_counts.items())),
        "source_schema_counts": dict(sorted(source_schema_counts.items())),
        "training_grade_rejection_reason_counts": dict(sorted(training_grade_reasons.items())),
        "blocking_gaps": blocking_gaps,
        "all_current_schemas_mapped": unmapped_count == 0,
        "training_grade_normalization_ready": False,
    }


def build_normalized_scaffold_manifest(mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "schema_version": "forgeagent.normalized_scaffold_manifest_row.v1",
            "normalized_row_id": sha256_json(
                {
                    "source_row_sha256": row["source_row_sha256"],
                    "canonical_schema_id": row["canonical_schema_id"],
                }
            ),
            "source_row_sha256": row["source_row_sha256"],
            "canonical_schema_id": row["canonical_schema_id"],
            "data_product": row["data_product"],
            "split": row["split"],
            "allowed_use": "schema_validation_only",
            "contains_training_payload": False,
            "training_grade_admitted": False,
        }
        for row in mapping_rows
        if row["normalization_output_allowed"]
    ]


def build_scaleout_plan(gap_report: dict[str, Any]) -> dict[str, Any]:
    phases = [
        {
            "phase_id": "schema_lock_v1",
            "objective": "Freeze canonical data product schemas and migration checks before generating more rows.",
            "entry_gate": "step29_26_doctor_ok",
            "exit_criteria": [
                "all_current_schemas_mapped",
                "public_safe_schema_registry_published",
                "manifest_ref_only_outputs_verified",
            ],
            "launches_training_job": False,
        },
        {
            "phase_id": "provenance_and_license_registry",
            "objective": "Make every generated row traceable to generator version, seed repo license state and immutable snapshot.",
            "entry_gate": "schema_lock_v1_passed",
            "exit_criteria": [
                "seed_repo_registry_exists",
                "license_policy_decisions_recorded",
                "provenance_refs_required_by_schema",
            ],
            "launches_training_job": False,
        },
        {
            "phase_id": "contamination_and_dedup_scanners",
            "objective": "Block public benchmark overlap, private heldout overlap and near duplicates before row promotion.",
            "entry_gate": "provenance_and_license_registry_passed",
            "exit_criteria": [
                "public_eval_overlap_scan_passed",
                "private_heldout_overlap_scan_passed",
                "train_eval_near_duplicate_scan_passed",
                "row_fingerprints_recorded",
            ],
            "launches_training_job": False,
        },
        {
            "phase_id": "oracle_quality_certification",
            "objective": "Require each training row to bind to executable oracle evidence and anti-overfit challenge results.",
            "entry_gate": "contamination_and_dedup_scanners_passed",
            "exit_criteria": [
                "pre_public_fail_evidence_present",
                "git_apply_check_evidence_present",
                "post_public_pass_evidence_present",
                "post_withheld_eval_pass_evidence_present",
                "public_overfit_caught_when_applicable",
            ],
            "launches_training_job": False,
        },
        {
            "phase_id": "bounded_generator_scaleout_dry_run",
            "objective": "Generate a larger but still local/control-plane-only set of manifest-ref rows across task families.",
            "entry_gate": "oracle_quality_certification_passed",
            "target_rows": {
                "patch_sft": 120,
                "trajectory_sft": 120,
                "preference_pair": 120,
                "repair_trace": 60,
                "eval_task_ref": 30,
                "private_heldout_ref": 30,
            },
            "exit_criteria": [
                "all_rows_pass_governance",
                "zero_private_rows_in_training_manifests",
                "zero_raw_patch_or_prompt_content_in_public_reports",
                "training_grade_rows_still_blocked_until_final_approval",
            ],
            "launches_training_job": False,
        },
    ]
    return {
        "schema_version": "forgeagent.generator_scaleout_plan.v1",
        "plan_name": "training_data_schema_normalization_generator_scaleout_plan_v1",
        "source_gap_report_sha256": sha256_json(gap_report),
        "phase_count": len(phases),
        "phases": phases,
        "default_training_launch_allowed": False,
        "default_remote_inference_invoked": False,
        "default_local_model_execution_used": False,
        "requires_explicit_approval_before_training": True,
    }


def scan_outputs(paths: list[Path], public_paths: list[Path]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    public_marker_leaks: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for finding in scan_secrets(text):
            secret_findings.append({"path": rel(path), **finding})
    for path in public_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in PUBLIC_REPORT_DISALLOWED_MARKERS:
            if marker in text:
                public_marker_leaks.append({"path": rel(path), "marker": marker})
    return {
        "schema_version": "forgeagent.training_data_schema_normalization_privacy_report.v1",
        "scanned_paths": [rel(path) for path in paths],
        "public_report_paths": [rel(path) for path in public_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "public_report_marker_leak_count": len(public_marker_leaks),
        "public_report_marker_leaks": public_marker_leaks,
        "passed": not secret_findings and not public_marker_leaks,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    step25_summary = read_json(STEP29_25_DIR / "summary.json")
    admissions = read_jsonl(STEP29_25_DIR / "row_admission_results.jsonl")
    if step25_summary["privacy_scan_passed"] is not True:
        raise RuntimeError("Step 29.25 privacy scan is not passing")
    if step25_summary["training_grade_admitted_row_count"] != 0:
        raise RuntimeError("Step 29.26 expects current rows to remain non-training-grade")
    if len(admissions) != step25_summary["raw_row_count"]:
        raise RuntimeError("Step 29.25 admission count does not match summary")

    mapping_rows = build_schema_mapping(admissions)
    gap_report = build_schema_gap_report(mapping_rows, admissions)
    normalized_scaffold_manifest = build_normalized_scaffold_manifest(mapping_rows)
    scaleout_plan = build_scaleout_plan(gap_report)
    schema_registry = {
        "schema_version": "forgeagent.training_data_canonical_schema_registry.v1",
        "registry_name": "training_data_canonical_schema_registry_v1",
        "source_step": "step29_26_training_data_schema_normalization_scaleout_plan_v1",
        "canonical_schema_count": len(CANONICAL_SCHEMAS),
        "canonical_schemas": CANONICAL_SCHEMAS,
        "source_schema_mapping": SOURCE_SCHEMA_TO_CANONICAL,
        "training_payloads_in_registry": False,
    }
    gate_decision = {
        "schema_version": "forgeagent.training_data_schema_normalization_gate_decision.v1",
        "gate_name": "training_data_schema_normalization_scaleout_plan_v1",
        "source_step_ready": True,
        "all_current_schemas_mapped": gap_report["all_current_schemas_mapped"],
        "canonical_schema_registry_ready": True,
        "normalized_scaffold_manifest_ready": True,
        "generator_scaleout_plan_ready": True,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "blocked_reasons": gap_report["blocking_gaps"],
    }
    public_report = {
        "schema_version": "forgeagent.public_safe_training_data_schema_normalization_report.v1",
        "report_name": "training_data_schema_normalization_scaleout_plan_v1_public_safe",
        "canonical_schema_count": len(CANONICAL_SCHEMAS),
        "source_row_count": len(mapping_rows),
        "mapped_source_row_count": gap_report["mapped_source_row_count"],
        "unmapped_source_row_count": gap_report["unmapped_source_row_count"],
        "normalized_scaffold_row_count": len(normalized_scaffold_manifest),
        "training_grade_row_count": 0,
        "scaleout_phase_count": scaleout_plan["phase_count"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "redaction_policy": {
            "raw_rows_included": False,
            "private_identifiers_included": False,
            "patch_content_included": False,
            "withheld_eval_content_included": False,
            "prompt_content_included": False,
            "model_outputs_included": False,
        },
    }

    paths = {
        "canonical_schema_registry": OUT_DIR / "canonical_schema_registry.json",
        "source_to_canonical_schema_map": OUT_DIR / "source_to_canonical_schema_map.json",
        "row_schema_mapping": OUT_DIR / "row_schema_mapping.jsonl",
        "normalized_scaffold_manifest": OUT_DIR / "normalized_scaffold_manifest.jsonl",
        "schema_gap_report": OUT_DIR / "schema_gap_report.json",
        "generator_scaleout_plan": OUT_DIR / "generator_scaleout_plan.json",
        "gate_decision": OUT_DIR / "training_data_schema_normalization_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_training_data_schema_normalization_report.json",
    }
    write_json(paths["canonical_schema_registry"], schema_registry)
    write_json(paths["source_to_canonical_schema_map"], SOURCE_SCHEMA_TO_CANONICAL)
    write_jsonl(paths["row_schema_mapping"], mapping_rows)
    write_jsonl(paths["normalized_scaffold_manifest"], normalized_scaffold_manifest)
    write_json(paths["schema_gap_report"], gap_report)
    write_json(paths["generator_scaleout_plan"], scaleout_plan)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]])
    privacy_path = OUT_DIR / "training_data_schema_normalization_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        "schema_version": "forgeagent.training_data_schema_normalization_scaleout_plan_summary.v1",
        "gate_name": "training_data_schema_normalization_scaleout_plan_v1",
        "git_commit": git_commit(),
        "source_step": "step29_25_training_data_governance_scaleout_v1",
        "source_step_ready": True,
        "source_row_count": len(mapping_rows),
        "canonical_schema_count": len(CANONICAL_SCHEMAS),
        "mapped_source_row_count": gap_report["mapped_source_row_count"],
        "unmapped_source_row_count": gap_report["unmapped_source_row_count"],
        "all_current_schemas_mapped": gap_report["all_current_schemas_mapped"],
        "normalized_scaffold_row_count": len(normalized_scaffold_manifest),
        "training_grade_row_count": 0,
        "schema_gap_count": len(gap_report["blocking_gaps"]),
        "scaleout_phase_count": scaleout_plan["phase_count"],
        "canonical_schema_registry_ready": True,
        "generator_scaleout_plan_ready": True,
        "privacy_scan_passed": privacy_report["passed"],
        "public_safe_report_ready": True,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "next_recommended_step": "step29_27_provenance_license_and_contamination_scanner_implementation",
        "artifacts": {name: rel(path) for name, path in paths.items()} | {"privacy_report": rel(privacy_path)},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("TRAINING_DATA_SCHEMA_NORMALIZATION_SCALEOUT_PLAN_V1_OK")


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_30_DIR = PROJECT_ROOT / "results/local/hardened_task_generation_public_benchmark_registry_v1"
STEP29_31_DIR = PROJECT_ROOT / "results/local/hardened_executable_task_generator_v1"
OUT_DIR = PROJECT_ROOT / "results/local/hardened_oracle_quality_data_release_integration_v1"

MINIMUM_ORACLE_STRENGTH_SCORE = 1.0
REQUIRED_CHALLENGES = {"golden", "rejected", "public_overfit", "wrong_file", "semantic_noop"}

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\s*[:=]"),
}

PUBLIC_REPORT_DISALLOWED_MARKERS = [
    "forge-hard-private-",
    "forge-hard-train-",
    "forge-hard-eval-",
    "forge-hard-public-eval-",
    "diff --git",
    "assertEqual",
    "hidden_tests",
    "golden.patch",
    "public_overfit.patch",
    "rejected.patch",
    "wrong_file.patch",
    "semantic_noop.patch",
    "raw_model_output",
    "raw_outputs",
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


def scan_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern_name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": pattern_name, "count": len(matches)})
    return findings


def grouped_challenges(challenge_rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in challenge_rows:
        task_hash = row.get("task_id_sha256")
        challenge = row.get("challenge")
        if isinstance(task_hash, str) and isinstance(challenge, str):
            grouped[task_hash][challenge] = row
    return grouped


def bool_count(values: list[bool]) -> int:
    return sum(1 for value in values if value)


def certification_for_task(
    task: dict[str, Any],
    challenge_by_label: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    task_hash = task["task_id_sha256"]
    golden = challenge_by_label.get("golden", {})
    rejected = challenge_by_label.get("rejected", {})
    public_overfit = challenge_by_label.get("public_overfit", {})
    wrong_file = challenge_by_label.get("wrong_file", {})
    semantic_noop = challenge_by_label.get("semantic_noop", {})
    challenge_labels = set(challenge_by_label)

    checks = {
        "task_verified": task.get("verified") is True,
        "repo_shape_temporary_git": task.get("repo_shape") == "temporary_git_repository",
        "patch_format_git_diff": task.get("patch_format") == "git_diff",
        "golden_git_apply_check_passed": golden.get("patch_check_passed") is True
        and task.get("golden_patch_check_passed") is True,
        "pre_public_failed": golden.get("pre_public_failed_as_expected") is True
        and task.get("pre_public_failed_as_expected") is True,
        "golden_patch_applied": golden.get("patch_applied") is True and task.get("golden_patch_applied") is True,
        "post_public_passed": golden.get("post_public_passed") is True and task.get("post_public_passed") is True,
        "post_hidden_passed": golden.get("post_hidden_passed") is True and task.get("post_hidden_passed") is True,
        "golden_edit_scope_passed": golden.get("edit_scope_passed") is True
        and task.get("golden_edit_scope_passed") is True,
        "golden_multi_file_patch": golden.get("patch_file_count", 0) >= 2 and task.get("multi_file_patch") is True,
        "challenge_matrix_complete": challenge_labels == REQUIRED_CHALLENGES,
        "rejected_negative_failed": rejected.get("patch_check_passed") is True
        and rejected.get("solved") is False
        and task.get("rejected_patch_failed") is True,
        "public_overfit_hidden_caught": public_overfit.get("patch_check_passed") is True
        and public_overfit.get("post_public_passed") is True
        and public_overfit.get("post_hidden_passed") is False
        and task.get("public_overfit_caught_by_hidden") is True,
        "wrong_file_negative_failed": wrong_file.get("patch_check_passed") is True
        and wrong_file.get("solved") is False
        and wrong_file.get("edit_scope_passed") is False
        and task.get("wrong_file_negative_failed") is True,
        "semantic_noop_negative_failed": semantic_noop.get("patch_check_passed") is True
        and semantic_noop.get("solved") is False
        and task.get("semantic_noop_negative_failed") is True,
        "no_raw_text_flag": task.get("contains_raw_text") is False
        and all(row.get("contains_raw_text") is False for row in challenge_by_label.values()),
        "no_private_identifier_flag": task.get("contains_private_identifiers") is False
        and all(row.get("contains_private_identifiers") is False for row in challenge_by_label.values()),
    }
    passed = bool_count(list(checks.values()))
    required = len(checks)
    score = passed / required
    oracle_certified = score >= MINIMUM_ORACLE_STRENGTH_SCORE
    return {
        "schema_version": "forgeagent.hardened_oracle_quality_certification.v1",
        "task_id_sha256": task_hash,
        "source_blueprint_id_sha256": task.get("source_blueprint_id_sha256"),
        "repo_snapshot_sha256": task.get("repo_snapshot_sha256"),
        "split": task.get("split"),
        "task_family": task.get("task_family"),
        "difficulty_label": task.get("difficulty_label"),
        "behavioral_axes": task.get("behavioral_axes", []),
        "oracle_certified": oracle_certified,
        "oracle_strength_score": round(score, 6),
        "minimum_oracle_strength_score": MINIMUM_ORACLE_STRENGTH_SCORE,
        "criterion_pass_count": passed,
        "criterion_required_count": required,
        "checks": checks,
        "patch_sha256s": dict(sorted((task.get("patch_sha256s") or {}).items())),
        "hidden_test_sha256": task.get("hidden_test_sha256"),
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }


def build_split_isolation_report(certifications: list[dict[str, Any]]) -> dict[str, Any]:
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cert in certifications:
        by_split[str(cert["split"])].append(cert)

    task_hash_overlap_pairs: list[dict[str, Any]] = []
    family_overlap_pairs: list[dict[str, Any]] = []
    split_names = sorted(by_split)
    for left_index, left in enumerate(split_names):
        for right in split_names[left_index + 1 :]:
            left_hashes = {row["task_id_sha256"] for row in by_split[left]}
            right_hashes = {row["task_id_sha256"] for row in by_split[right]}
            left_families = {row["task_family"] for row in by_split[left]}
            right_families = {row["task_family"] for row in by_split[right]}
            hash_overlap = sorted(left_hashes & right_hashes)
            family_overlap = sorted(left_families & right_families)
            if hash_overlap:
                task_hash_overlap_pairs.append(
                    {"left_split": left, "right_split": right, "overlap_count": len(hash_overlap)}
                )
            if family_overlap:
                family_overlap_pairs.append(
                    {"left_split": left, "right_split": right, "overlap_count": len(family_overlap)}
                )

    train_hashes = {row["task_id_sha256"] for row in by_split.get("train", [])}
    eval_hashes = {row["task_id_sha256"] for row in by_split.get("eval", [])}
    private_hashes = {row["task_id_sha256"] for row in by_split.get("private_heldout", [])}
    public_hashes = {row["task_id_sha256"] for row in by_split.get("public_eval", [])}
    train_eval_overlap = len(train_hashes & eval_hashes)
    train_private_overlap = len(train_hashes & private_hashes)
    train_public_overlap = len(train_hashes & public_hashes)
    return {
        "schema_version": "forgeagent.hardened_split_isolation_report.v1",
        "split_counts": {split: len(rows) for split, rows in sorted(by_split.items())},
        "cross_split_task_hash_overlap_count": sum(row["overlap_count"] for row in task_hash_overlap_pairs),
        "cross_split_task_family_overlap_count": sum(row["overlap_count"] for row in family_overlap_pairs),
        "train_eval_task_hash_overlap_count": train_eval_overlap,
        "train_private_task_hash_overlap_count": train_private_overlap,
        "train_public_eval_task_hash_overlap_count": train_public_overlap,
        "task_hash_overlap_pairs": task_hash_overlap_pairs,
        "task_family_overlap_pairs": family_overlap_pairs,
        "train_release_split_isolation_passed": train_eval_overlap == 0
        and train_private_overlap == 0
        and train_public_overlap == 0,
        "private_generalization_claim_allowed": False,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }


def release_decision_for_task(
    cert: dict[str, Any],
    *,
    public_benchmark_scan_complete: bool,
    exact_reference_collision_count: int,
    high_reference_similarity_count: int,
) -> dict[str, Any]:
    split = cert["split"]
    blockers: list[str] = []
    if not cert["oracle_certified"]:
        blockers.append("hardened_oracle_not_certified")
    if split != "train":
        blockers.append("not_train_split")
    if not public_benchmark_scan_complete:
        blockers.append("full_public_benchmark_corpus_scan_incomplete")
    if exact_reference_collision_count:
        blockers.append("exact_reference_collision_present")
    if high_reference_similarity_count:
        blockers.append("high_reference_similarity_present")
    blockers.append("license_policy_still_scaffold_only")
    blockers.append("training_payload_materialization_not_authorized")

    oracle_certified_train_candidate = split == "train" and cert["oracle_certified"]
    training_grade_candidate_after_step29_32 = oracle_certified_train_candidate and not blockers
    if split == "train":
        release_class = (
            "training_grade_released"
            if training_grade_candidate_after_step29_32
            else "oracle_certified_train_candidate_blocked"
        )
    else:
        release_class = "never_train_eval_or_heldout_reference"
    return {
        "schema_version": "forgeagent.hardened_data_release_decision.v1",
        "task_id_sha256": cert["task_id_sha256"],
        "source_blueprint_id_sha256": cert["source_blueprint_id_sha256"],
        "repo_snapshot_sha256": cert["repo_snapshot_sha256"],
        "split": split,
        "task_family": cert["task_family"],
        "oracle_certified": cert["oracle_certified"],
        "oracle_strength_score": cert["oracle_strength_score"],
        "oracle_certified_train_candidate": oracle_certified_train_candidate,
        "training_grade_candidate_after_step29_32": training_grade_candidate_after_step29_32,
        "training_export_allowed": training_grade_candidate_after_step29_32,
        "release_class": release_class,
        "blocked_reasons": sorted(set(blockers)),
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }


def build_release_policy(
    *,
    step30_summary: dict[str, Any],
    certifications: list[dict[str, Any]],
    split_report: dict[str, Any],
    release_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    requirements = [
        {
            "requirement": "hardened_executable_tasks_verified",
            "passed": all(cert["oracle_certified"] for cert in certifications),
            "evidence": "hardened_oracle_quality_certifications.jsonl",
        },
        {
            "requirement": "train_split_oracle_certified",
            "passed": all(
                cert["oracle_certified"] for cert in certifications if cert["split"] == "train"
            ),
            "evidence": "hardened_oracle_quality_certifications.jsonl",
        },
        {
            "requirement": "train_split_isolated_from_eval_private_public_eval",
            "passed": split_report["train_release_split_isolation_passed"],
            "evidence": "hardened_split_isolation_report.json",
        },
        {
            "requirement": "no_exact_current_reference_collision",
            "passed": step30_summary["exact_current_reference_collision_count"] == 0,
            "evidence": "step29_30 summary exact_current_reference_collision_count",
        },
        {
            "requirement": "no_high_current_private_or_eval_reference_similarity",
            "passed": step30_summary["high_current_private_or_eval_reference_similarity_count"] == 0,
            "evidence": "step29_30 summary high_current_private_or_eval_reference_similarity_count",
        },
        {
            "requirement": "no_exact_public_benchmark_registry_collision",
            "passed": step30_summary["exact_public_benchmark_registry_collision_count"] == 0,
            "evidence": "step29_30 summary exact_public_benchmark_registry_collision_count",
        },
        {
            "requirement": "full_public_benchmark_corpus_scan_complete",
            "passed": step30_summary["full_public_benchmark_corpus_scan_complete"] is True,
            "evidence": "step29_30 summary full_public_benchmark_corpus_scan_complete",
        },
        {
            "requirement": "license_policy_upgraded_beyond_scaffold_only",
            "passed": False,
            "evidence": "current policy only allows internal scaffold until license/provenance attestation is upgraded",
        },
        {
            "requirement": "training_payload_materialization_authorized",
            "passed": any(row["training_export_allowed"] for row in release_decisions),
            "evidence": "hardened_data_release_decisions.jsonl",
        },
    ]
    return {
        "schema_version": "forgeagent.hardened_training_release_policy.v1",
        "policy_name": "hardened_oracle_quality_data_release_integration_v1",
        "policy_integrated": True,
        "minimum_oracle_strength_score": MINIMUM_ORACLE_STRENGTH_SCORE,
        "requirements": requirements,
        "passed_requirement_count": sum(1 for item in requirements if item["passed"]),
        "failed_requirement_count": sum(1 for item in requirements if not item["passed"]),
        "training_grade_data_release_allowed": all(item["passed"] for item in requirements),
        "allowed_release_classes": ["oracle_certified_train_candidate_blocked", "never_train_eval_or_heldout_reference"],
        "contains_raw_text": False,
        "contains_private_identifiers": False,
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
        "schema_version": "forgeagent.hardened_oracle_quality_data_release_privacy_report.v1",
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

    step30_summary = read_json(STEP29_30_DIR / "summary.json")
    step31_summary = read_json(STEP29_31_DIR / "summary.json")
    task_rows = read_jsonl(STEP29_31_DIR / "task_results.jsonl")
    challenge_rows = read_jsonl(STEP29_31_DIR / "patch_challenge_results.jsonl")
    task_manifest_rows = read_jsonl(STEP29_31_DIR / "dataset_exports/hardened_executable_task_manifest.jsonl")
    train_scaffold_rows = read_jsonl(STEP29_31_DIR / "dataset_exports/patch_sft_train_scaffold_manifest.jsonl")

    if step30_summary["source_step_ready"] is not True:
        raise RuntimeError("Step 29.30 source step is not ready")
    if step31_summary["source_step_ready"] is not True:
        raise RuntimeError("Step 29.31 source step is not ready")
    if step31_summary["verified_task_count"] != 12:
        raise RuntimeError("Step 29.31 verified task count is not 12")
    if step31_summary["challenge_result_count"] != 60:
        raise RuntimeError("Step 29.31 challenge matrix is incomplete")
    if len(task_rows) != 12 or len(challenge_rows) != 60:
        raise RuntimeError("Step 29.31 task or challenge artifacts are incomplete")
    if len(task_manifest_rows) != 12 or len(train_scaffold_rows) != 4:
        raise RuntimeError("Step 29.31 dataset export manifests are incomplete")

    challenges = grouped_challenges(challenge_rows)
    certifications = [certification_for_task(task, challenges.get(task["task_id_sha256"], {})) for task in task_rows]
    split_report = build_split_isolation_report(certifications)
    release_decisions = [
        release_decision_for_task(
            cert,
            public_benchmark_scan_complete=step30_summary["full_public_benchmark_corpus_scan_complete"] is True,
            exact_reference_collision_count=step30_summary["exact_current_reference_collision_count"]
            + step30_summary["exact_public_benchmark_registry_collision_count"],
            high_reference_similarity_count=step30_summary["high_current_private_or_eval_reference_similarity_count"]
            + step30_summary["high_public_benchmark_registry_similarity_count"],
        )
        for cert in certifications
    ]
    release_policy = build_release_policy(
        step30_summary=step30_summary,
        certifications=certifications,
        split_report=split_report,
        release_decisions=release_decisions,
    )

    split_counts = Counter(cert["split"] for cert in certifications)
    oracle_quality_report = {
        "schema_version": "forgeagent.hardened_oracle_quality_report.v1",
        "task_count": len(certifications),
        "oracle_certified_task_count": sum(1 for cert in certifications if cert["oracle_certified"]),
        "train_oracle_certified_task_count": sum(
            1 for cert in certifications if cert["split"] == "train" and cert["oracle_certified"]
        ),
        "minimum_oracle_strength_score": MINIMUM_ORACLE_STRENGTH_SCORE,
        "minimum_observed_oracle_strength_score": min(cert["oracle_strength_score"] for cert in certifications),
        "maximum_observed_oracle_strength_score": max(cert["oracle_strength_score"] for cert in certifications),
        "split_counts": dict(sorted(split_counts.items())),
        "challenge_matrix_complete": all(
            set(challenges.get(cert["task_id_sha256"], {})) == REQUIRED_CHALLENGES for cert in certifications
        ),
        "required_challenges": sorted(REQUIRED_CHALLENGES),
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }

    release_class_counts = Counter(row["release_class"] for row in release_decisions)
    blocked_reason_counts = Counter(reason for row in release_decisions for reason in row["blocked_reasons"])
    gate_decision = {
        "schema_version": "forgeagent.hardened_oracle_quality_data_release_gate_decision.v1",
        "gate_name": "hardened_oracle_quality_data_release_integration_v1",
        "source_step": "step29_31_hardened_executable_task_generator_v1",
        "source_step_ready": True,
        "hardened_oracle_quality_certification_complete": True,
        "hardened_oracle_certified_task_count": oracle_quality_report["oracle_certified_task_count"],
        "hardened_train_oracle_certified_task_count": oracle_quality_report["train_oracle_certified_task_count"],
        "data_release_policy_integrated": True,
        "release_policy_passed_requirement_count": release_policy["passed_requirement_count"],
        "release_policy_failed_requirement_count": release_policy["failed_requirement_count"],
        "oracle_certified_train_candidate_count": sum(
            1 for row in release_decisions if row["oracle_certified_train_candidate"]
        ),
        "training_grade_candidate_after_step29_32_count": sum(
            1 for row in release_decisions if row["training_grade_candidate_after_step29_32"]
        ),
        "training_grade_data_release_allowed": release_policy["training_grade_data_release_allowed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "resolved_previous_blockers": [
            "new_hardened_tasks_require_oracle_quality_certification_gate",
            "final_training_release_policy_not_integrated",
        ],
        "blocked_reasons": sorted(blocked_reason_counts),
        "next_recommended_step": "step29_33_public_benchmark_corpus_scan_and_license_attestation_v1",
    }

    public_report = {
        "schema_version": "forgeagent.public_safe_hardened_oracle_quality_data_release_report.v1",
        "report_name": "hardened_oracle_quality_data_release_integration_v1_public_safe",
        "task_count": len(certifications),
        "oracle_certified_task_count": oracle_quality_report["oracle_certified_task_count"],
        "split_counts": dict(sorted(split_counts.items())),
        "train_oracle_certified_task_count": oracle_quality_report["train_oracle_certified_task_count"],
        "oracle_certified_train_candidate_count": gate_decision["oracle_certified_train_candidate_count"],
        "training_grade_candidate_after_step29_32_count": gate_decision[
            "training_grade_candidate_after_step29_32_count"
        ],
        "release_class_counts": dict(sorted(release_class_counts.items())),
        "blocked_reason_counts": dict(sorted(blocked_reason_counts.items())),
        "release_policy_passed_requirement_count": release_policy["passed_requirement_count"],
        "release_policy_failed_requirement_count": release_policy["failed_requirement_count"],
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "raw_task_ids_included": False,
        "raw_rows_included": False,
        "raw_text_included": False,
        "patch_content_included": False,
        "hidden_test_content_included": False,
        "private_identifier_values_included": False,
        "model_outputs_included": False,
        "next_recommended_step": gate_decision["next_recommended_step"],
    }

    paths = {
        "oracle_quality_certifications": OUT_DIR / "hardened_oracle_quality_certifications.jsonl",
        "data_release_decisions": OUT_DIR / "hardened_data_release_decisions.jsonl",
        "split_isolation_report": OUT_DIR / "hardened_split_isolation_report.json",
        "training_release_policy": OUT_DIR / "hardened_training_release_policy.json",
        "oracle_quality_report": OUT_DIR / "hardened_oracle_quality_report.json",
        "gate_decision": OUT_DIR / "hardened_oracle_quality_data_release_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_hardened_oracle_quality_data_release_report.json",
    }
    write_jsonl(paths["oracle_quality_certifications"], certifications)
    write_jsonl(paths["data_release_decisions"], release_decisions)
    write_json(paths["split_isolation_report"], split_report)
    write_json(paths["training_release_policy"], release_policy)
    write_json(paths["oracle_quality_report"], oracle_quality_report)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]])
    privacy_path = OUT_DIR / "hardened_oracle_quality_data_release_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        "schema_version": "forgeagent.hardened_oracle_quality_data_release_summary.v1",
        "gate_name": "hardened_oracle_quality_data_release_integration_v1",
        "git_commit": git_commit(),
        "source_step": "step29_31_hardened_executable_task_generator_v1",
        "source_step_ready": True,
        "task_count": len(certifications),
        "oracle_certified_task_count": oracle_quality_report["oracle_certified_task_count"],
        "train_oracle_certified_task_count": oracle_quality_report["train_oracle_certified_task_count"],
        "oracle_certified_train_candidate_count": gate_decision["oracle_certified_train_candidate_count"],
        "training_grade_candidate_after_step29_32_count": gate_decision[
            "training_grade_candidate_after_step29_32_count"
        ],
        "release_policy_integrated": True,
        "release_policy_passed_requirement_count": release_policy["passed_requirement_count"],
        "release_policy_failed_requirement_count": release_policy["failed_requirement_count"],
        "split_counts": dict(sorted(split_counts.items())),
        "release_class_counts": dict(sorted(release_class_counts.items())),
        "blocked_reason_counts": dict(sorted(blocked_reason_counts.items())),
        "new_hardened_tasks_oracle_certification_blocker_resolved": True,
        "final_training_release_policy_integration_blocker_resolved": True,
        "full_public_benchmark_corpus_scan_complete": step30_summary["full_public_benchmark_corpus_scan_complete"],
        "license_policy_upgraded_beyond_scaffold_only": False,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "privacy_scan_passed": privacy_report["passed"],
        "public_safe_report_ready": True,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "next_recommended_step": gate_decision["next_recommended_step"],
        "artifacts": {name: rel(path) for name, path in paths.items()} | {"privacy_report": rel(privacy_path)},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("HARDENED_ORACLE_QUALITY_DATA_RELEASE_INTEGRATION_V1_OK")


if __name__ == "__main__":
    main()

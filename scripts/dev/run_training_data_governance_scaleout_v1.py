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
OUT_DIR = PROJECT_ROOT / "results/local/training_data_governance_scaleout_v1"
SOURCE_MATRIX_DIR = PROJECT_ROOT / "results/local/dataset_source_matrix_gate_v0"
PRIVATE_HELDOUT_GATE_DIR = PROJECT_ROOT / "results/local/private_heldout_aggregate_candidate_eval_gate_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"

EXPORT_ROOTS = [
    PROJECT_ROOT / "results/local/internal_synthetic_micro_generator_v0/dataset_exports",
    PROJECT_ROOT / "results/local/agentic_trajectory_recorder_v1/dataset_exports",
]

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


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


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


def flatten_keys(data: object, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            key_text = str(key)
            full_key = f"{prefix}.{key_text}" if prefix else key_text
            keys.add(full_key)
            keys.update(flatten_keys(value, full_key))
    elif isinstance(data, list):
        for item in data:
            keys.update(flatten_keys(item, prefix))
    return keys


def scan_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern_name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": pattern_name, "count": len(matches)})
    return findings


def collect_private_identifiers(rows: list[dict[str, Any]]) -> set[str]:
    identifiers = {
        row["task_id"]
        for row in read_jsonl(PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl")
        if isinstance(row.get("task_id"), str)
    }
    for row in rows:
        if row.get("split") == "private_heldout":
            for key in ("task_id", "trajectory_id", "pair_id"):
                value = row.get(key)
                if isinstance(value, str):
                    identifiers.add(value)
    return identifiers


def discover_exports() -> list[Path]:
    paths: list[Path] = []
    for root in EXPORT_ROOTS:
        if root.exists():
            paths.extend(sorted(root.glob("*.jsonl")))
    return sorted(paths)


def dataset_role_for_file(path: Path) -> str:
    name = path.name
    if "private_heldout" in name:
        return "private_heldout"
    if name.startswith("eval_"):
        return "eval"
    if name.endswith("_train.jsonl") or "_train_" in name or name.endswith("_train_seed.jsonl"):
        return "train"
    return "unknown"


def row_type(row: dict[str, Any], source_path: Path) -> str:
    schema = str(row.get("schema_version", "unknown"))
    if "patch_sft" in schema or source_path.name == "patch_sft_train.jsonl":
        return "patch_sft"
    if "preference" in schema:
        return "preference_pair"
    if "repair_trace" in schema:
        return "repair_trace"
    if "trajectory_sft" in schema or "trajectory" in schema:
        return "trajectory"
    if "synthetic_executable_task" in schema:
        return "executable_task"
    return "unknown"


def explicit_internal_provenance(row: dict[str, Any]) -> bool:
    source_repo = row.get("source_repo")
    provenance = row.get("provenance")
    metadata = row.get("metadata")
    source_repo_ok = (
        isinstance(source_repo, dict)
        and source_repo.get("license") == "internal_scaffold_only"
        and bool(source_repo.get("provenance"))
    )
    provenance_ok = isinstance(provenance, dict) and bool(provenance.get("generator"))
    metadata_ok = isinstance(metadata, dict) and bool(metadata.get("source"))
    return source_repo_ok and (provenance_ok or metadata_ok)


def contamination_checked(row: dict[str, Any]) -> bool:
    report = row.get("contamination_report")
    return isinstance(report, dict) and report.get("public_benchmark_overlap_checked") is True


def contains_withheld_eval_reference(row: dict[str, Any]) -> bool:
    keys = flatten_keys(row)
    return any("hidden_test" in key or "hidden_tests" in key for key in keys)


def has_oracle_quality_for_training(row: dict[str, Any]) -> bool:
    quality_scores = row.get("quality_scores")
    if isinstance(quality_scores, dict):
        return quality_scores.get("training_grade_candidate") is True and quality_scores.get("execution_oracle") == 1.0
    metrics = row.get("metrics")
    if isinstance(metrics, dict):
        return metrics.get("solved") is True and metrics.get("oracle_strength_score") == 1.0
    return False


def build_inventory(export_paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for path in export_paths:
        file_rows = read_jsonl(path)
        row_hashes = [sha256_json(row) for row in file_rows]
        inventory.append(
            {
                "source_file": rel(path),
                "dataset_role": dataset_role_for_file(path),
                "row_count": len(file_rows),
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "row_sha256s": row_hashes,
                "schema_versions": sorted({str(row.get("schema_version", "unknown")) for row in file_rows}),
            }
        )
        for index, row in enumerate(file_rows):
            rows.append({"source_path": path, "row_index": index, "row": row, "row_sha256": row_hashes[index]})
    return inventory, rows


def evaluate_row(
    *,
    source_path: Path,
    row_index: int,
    row: dict[str, Any],
    row_sha256: str,
    private_identifiers: set[str],
) -> dict[str, Any]:
    split = row.get("split", "unknown")
    row_blob = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
    private_leaks = sorted(identifier for identifier in private_identifiers if identifier and identifier in row_blob)
    secret_findings = scan_secrets(row_blob)
    never_train_on = bool(row.get("never_train_on") or row.get("metadata", {}).get("never_train_on"))
    explicit_never_train_field = "never_train_on" in row or (
        isinstance(row.get("metadata"), dict) and "never_train_on" in row["metadata"]
    )
    withheld_ref = contains_withheld_eval_reference(row)
    license_ok = explicit_internal_provenance(row)
    contamination_ok = contamination_checked(row)
    oracle_ok = has_oracle_quality_for_training(row)

    scaffold_reasons: list[str] = []
    training_grade_reasons: list[str] = []

    scaffold_allowed = split == "train" and not never_train_on and not private_leaks and not secret_findings
    if split != "train":
        scaffold_reasons.append("non_train_split")
    if never_train_on:
        scaffold_reasons.append("never_train_on")
    if private_leaks:
        scaffold_reasons.append("private_identifier_present")
    if secret_findings:
        scaffold_reasons.append("secret_pattern_present")

    if not scaffold_allowed:
        training_grade_reasons.extend(scaffold_reasons)
    if not explicit_never_train_field:
        training_grade_reasons.append("explicit_never_train_field_missing")
    if not license_ok:
        training_grade_reasons.append("license_or_provenance_incomplete")
    if not contamination_ok:
        training_grade_reasons.append("contamination_scan_incomplete")
    if not oracle_ok:
        training_grade_reasons.append("training_oracle_quality_not_certified")
    if withheld_ref:
        training_grade_reasons.append("withheld_eval_reference_present")

    training_grade_allowed = scaffold_allowed and not training_grade_reasons
    if not training_grade_reasons:
        training_grade_reasons.append("accepted")
    if not scaffold_reasons:
        scaffold_reasons.append("accepted_for_scaffold_only")

    return {
        "schema_version": "forgeagent.training_data_row_admission_result.v1",
        "source_file": rel(source_path),
        "row_index": row_index,
        "row_sha256": row_sha256,
        "split": split,
        "dataset_role": dataset_role_for_file(source_path),
        "row_type": row_type(row, source_path),
        "schema": str(row.get("schema_version", "unknown")),
        "scaffold_admitted": scaffold_allowed,
        "training_grade_admitted": training_grade_allowed,
        "explicit_never_train_field_present": explicit_never_train_field,
        "license_provenance_complete": license_ok,
        "contamination_checked": contamination_ok,
        "oracle_quality_certified": oracle_ok,
        "withheld_eval_reference_present": withheld_ref,
        "private_identifier_present": bool(private_leaks),
        "secret_finding_present": bool(secret_findings),
        "scaffold_decision_reasons": scaffold_reasons,
        "training_grade_decision_reasons": training_grade_reasons,
    }


def redact_private_ids(results: list[dict[str, Any]], private_identifiers: set[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for result in results:
        text = json.dumps(result, sort_keys=True, ensure_ascii=False)
        if any(identifier and identifier in text for identifier in private_identifiers):
            safe = dict(result)
            safe["source_file"] = "redacted_private_source"
            output.append(safe)
        else:
            output.append(result)
    return output


def scan_outputs(paths: list[Path], public_paths: list[Path], private_identifiers: set[str]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    private_identifier_leaks: list[dict[str, Any]] = []
    public_marker_leaks: list[dict[str, Any]] = []

    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for finding in scan_secrets(text):
            secret_findings.append({"path": rel(path), **finding})
        for identifier in private_identifiers:
            if identifier and identifier in text:
                private_identifier_leaks.append({"path": rel(path), "identifier_sha256": sha256_text(identifier)})

    for path in public_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in PUBLIC_REPORT_DISALLOWED_MARKERS:
            if marker in text:
                public_marker_leaks.append({"path": rel(path), "marker": marker})

    return {
        "schema_version": "forgeagent.training_data_governance_privacy_report.v1",
        "scanned_paths": [rel(path) for path in paths],
        "public_report_paths": [rel(path) for path in public_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "private_identifier_leak_count": len(private_identifier_leaks),
        "private_identifier_leaks": private_identifier_leaks,
        "public_report_marker_leak_count": len(public_marker_leaks),
        "public_report_marker_leaks": public_marker_leaks,
        "passed": not secret_findings and not private_identifier_leaks and not public_marker_leaks,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    source_matrix = read_json(SOURCE_MATRIX_DIR / "dataset_source_matrix_gate.json")
    acquisition_report = read_json(SOURCE_MATRIX_DIR / "dataset_acquisition_gate_report.json")
    private_gate_summary = read_json(PRIVATE_HELDOUT_GATE_DIR / "summary.json")

    if source_matrix["source_count"] < 1:
        raise RuntimeError("dataset source matrix is empty")
    if acquisition_report["training_launch_allowed"] is not False:
        raise RuntimeError("dataset acquisition gate unexpectedly allows training")
    if private_gate_summary["privacy_scan_passed"] is not True:
        raise RuntimeError("private heldout aggregate gate privacy scan is not passing")

    export_paths = discover_exports()
    inventory, rows = build_inventory(export_paths)
    private_identifiers = collect_private_identifiers([item["row"] for item in rows])

    admission_results = [
        evaluate_row(
            source_path=item["source_path"],
            row_index=item["row_index"],
            row=item["row"],
            row_sha256=item["row_sha256"],
            private_identifiers=private_identifiers,
        )
        for item in rows
    ]
    safe_admission_results = redact_private_ids(admission_results, private_identifiers)

    admitted_scaffold_rows = [
        {
            "schema_version": "forgeagent.training_data_scaffold_manifest_row.v1",
            "source_file": row["source_file"],
            "row_index": row["row_index"],
            "row_sha256": row["row_sha256"],
            "split": row["split"],
            "row_type": row["row_type"],
            "training_grade_admitted": False,
            "allowed_use": "schema_pipeline_scaffold_only",
        }
        for row in safe_admission_results
        if row["scaffold_admitted"]
    ]
    rejected_rows = [
        {
            "schema_version": "forgeagent.training_data_rejected_row.v1",
            "source_file": row["source_file"],
            "row_index": row["row_index"],
            "row_sha256": row["row_sha256"],
            "split": row["split"],
            "row_type": row["row_type"],
            "scaffold_admitted": row["scaffold_admitted"],
            "training_grade_admitted": row["training_grade_admitted"],
            "reasons": row["training_grade_decision_reasons"],
        }
        for row in safe_admission_results
        if not row["training_grade_admitted"]
    ]

    split_counts = Counter(str(row["split"]) for row in safe_admission_results)
    row_type_counts = Counter(str(row["row_type"]) for row in safe_admission_results)
    source_role_counts = Counter(item["dataset_role"] for item in inventory)
    rejection_reasons = Counter(
        reason
        for row in safe_admission_results
        if not row["training_grade_admitted"]
        for reason in row["training_grade_decision_reasons"]
    )

    public_safe_report = {
        "schema_version": "forgeagent.public_safe_training_data_governance_report.v1",
        "report_name": "training_data_governance_scaleout_v1_public_safe",
        "export_file_count": len(inventory),
        "raw_row_count": len(safe_admission_results),
        "split_counts": dict(sorted(split_counts.items())),
        "row_type_counts": dict(sorted(row_type_counts.items())),
        "source_role_counts": dict(sorted(source_role_counts.items())),
        "scaffold_admitted_row_count": len(admitted_scaffold_rows),
        "training_grade_admitted_row_count": 0,
        "training_grade_rejection_reason_counts": dict(sorted(rejection_reasons.items())),
        "private_rows_rejected_for_training": split_counts.get("private_heldout", 0),
        "eval_rows_rejected_for_training": split_counts.get("eval", 0),
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

    split_integrity_report = {
        "schema_version": "forgeagent.training_data_split_integrity_report.v1",
        "split_counts": dict(sorted(split_counts.items())),
        "private_rows_seen": split_counts.get("private_heldout", 0),
        "private_rows_admitted_to_scaffold": sum(
            1 for row in safe_admission_results if row["split"] == "private_heldout" and row["scaffold_admitted"]
        ),
        "private_rows_admitted_to_training_grade": sum(
            1 for row in safe_admission_results if row["split"] == "private_heldout" and row["training_grade_admitted"]
        ),
        "eval_rows_admitted_to_training_grade": sum(
            1 for row in safe_admission_results if row["split"] == "eval" and row["training_grade_admitted"]
        ),
        "non_train_rows_admitted_to_training_grade": sum(
            1 for row in safe_admission_results if row["split"] != "train" and row["training_grade_admitted"]
        ),
        "passed": all(
            row["split"] == "train" for row in safe_admission_results if row["training_grade_admitted"]
        )
        and not any(
            row["split"] == "private_heldout" and row["scaffold_admitted"] for row in safe_admission_results
        ),
    }

    license_provenance_report = {
        "schema_version": "forgeagent.training_data_license_provenance_report.v1",
        "rows_with_complete_license_provenance": sum(
            1 for row in safe_admission_results if row["license_provenance_complete"]
        ),
        "rows_missing_complete_license_provenance": sum(
            1 for row in safe_admission_results if not row["license_provenance_complete"]
        ),
        "training_grade_requires_explicit_license_and_generator_provenance": True,
        "passed_for_training_grade_release": False,
    }

    contamination_report = {
        "schema_version": "forgeagent.training_data_contamination_report.v1",
        "rows_with_completed_public_benchmark_overlap_check": sum(
            1 for row in safe_admission_results if row["contamination_checked"]
        ),
        "rows_missing_completed_public_benchmark_overlap_check": sum(
            1 for row in safe_admission_results if not row["contamination_checked"]
        ),
        "private_identifier_present_count": sum(
            1 for row in safe_admission_results if row["private_identifier_present"]
        ),
        "training_grade_requires_completed_contamination_scan": True,
        "passed_for_training_grade_release": False,
    }

    gate_decision = {
        "schema_version": "forgeagent.training_data_governance_gate_decision.v1",
        "gate_name": "training_data_governance_scaleout_v1",
        "source_matrix_ready": True,
        "private_heldout_gate_ready": private_gate_summary["privacy_scan_passed"],
        "scaffold_data_release_allowed": len(admitted_scaffold_rows) > 0,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "blocked_reasons": [
            "training_grade_row_count_zero",
            "license_provenance_incomplete",
            "contamination_scan_incomplete",
            "oracle_quality_not_certified_for_training_rows",
            "private_and_eval_splits_present_but_rejected_for_training",
        ],
    }

    output_paths = {
        "dataset_export_inventory": OUT_DIR / "dataset_export_inventory.json",
        "row_admission_results": OUT_DIR / "row_admission_results.jsonl",
        "admitted_scaffold_manifest": OUT_DIR / "admitted_scaffold_manifest.jsonl",
        "rejected_rows": OUT_DIR / "rejected_rows.jsonl",
        "split_integrity_report": OUT_DIR / "split_integrity_report.json",
        "license_provenance_report": OUT_DIR / "license_provenance_report.json",
        "contamination_report": OUT_DIR / "contamination_report.json",
        "public_safe_report": OUT_DIR / "public_safe_training_data_governance_report.json",
        "gate_decision": OUT_DIR / "training_data_governance_gate_decision.json",
    }

    write_json(output_paths["dataset_export_inventory"], inventory)
    write_jsonl(output_paths["row_admission_results"], safe_admission_results)
    write_jsonl(output_paths["admitted_scaffold_manifest"], admitted_scaffold_rows)
    write_jsonl(output_paths["rejected_rows"], rejected_rows)
    write_json(output_paths["split_integrity_report"], split_integrity_report)
    write_json(output_paths["license_provenance_report"], license_provenance_report)
    write_json(output_paths["contamination_report"], contamination_report)
    write_json(output_paths["public_safe_report"], public_safe_report)
    write_json(output_paths["gate_decision"], gate_decision)

    privacy_report = scan_outputs(
        paths=list(output_paths.values()),
        public_paths=[output_paths["public_safe_report"]],
        private_identifiers=private_identifiers,
    )
    privacy_path = OUT_DIR / "training_data_governance_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        "schema_version": "forgeagent.training_data_governance_scaleout_summary.v1",
        "gate_name": "training_data_governance_scaleout_v1",
        "git_commit": git_commit(),
        "source_matrix_ready": True,
        "private_heldout_gate_ready": private_gate_summary["privacy_scan_passed"],
        "export_file_count": len(inventory),
        "raw_row_count": len(safe_admission_results),
        "train_split_row_count": split_counts.get("train", 0),
        "eval_split_row_count": split_counts.get("eval", 0),
        "private_heldout_row_count": split_counts.get("private_heldout", 0),
        "scaffold_admitted_row_count": len(admitted_scaffold_rows),
        "training_grade_admitted_row_count": 0,
        "license_provenance_complete_row_count": license_provenance_report[
            "rows_with_complete_license_provenance"
        ],
        "contamination_checked_row_count": contamination_report[
            "rows_with_completed_public_benchmark_overlap_check"
        ],
        "private_identifier_present_row_count": contamination_report["private_identifier_present_count"],
        "split_integrity_passed": split_integrity_report["passed"],
        "privacy_scan_passed": privacy_report["passed"],
        "public_safe_report_ready": True,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "next_recommended_step": "step29_26_training_data_schema_normalization_and_generator_scaleout_plan",
        "artifacts": {name: rel(path) for name, path in output_paths.items()} | {"privacy_report": rel(privacy_path)},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("TRAINING_DATA_GOVERNANCE_SCALEOUT_V1_OK")


if __name__ == "__main__":
    main()

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
STEP29_25_DIR = PROJECT_ROOT / "results/local/training_data_governance_scaleout_v1"
STEP29_26_DIR = PROJECT_ROOT / "results/local/training_data_schema_normalization_scaleout_plan_v1"
PRIVATE_SEED_MANIFEST = (
    PROJECT_ROOT / "results/local/private_heldout_seed_set_v1/dataset_exports/private_heldout_seed_manifest.jsonl"
)
OUT_DIR = PROJECT_ROOT / "results/local/provenance_license_contamination_scanner_v1"

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


def flatten_keys(data: object, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else str(key)
            keys.add(full_key)
            keys.update(flatten_keys(value, full_key))
    elif isinstance(data, list):
        for item in data:
            keys.update(flatten_keys(item, prefix))
    return keys


def load_source_rows(admissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_cache: dict[Path, list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for admission in admissions:
        source_path = PROJECT_ROOT / admission["source_file"]
        if source_path not in source_cache:
            source_cache[source_path] = read_jsonl(source_path)
        raw_row = source_cache[source_path][admission["row_index"]]
        rows.append({"admission": admission, "raw_row": raw_row})
    return rows


def collect_private_identifiers(source_rows: list[dict[str, Any]]) -> set[str]:
    identifiers = {
        row["task_id"]
        for row in read_jsonl(PRIVATE_SEED_MANIFEST)
        if isinstance(row.get("task_id"), str)
    }
    for item in source_rows:
        row = item["raw_row"]
        if row.get("split") == "private_heldout":
            for key in ("task_id", "trajectory_id", "pair_id"):
                value = row.get(key)
                if isinstance(value, str):
                    identifiers.add(value)
    return identifiers


def collect_eval_identifiers(source_rows: list[dict[str, Any]]) -> set[str]:
    identifiers: set[str] = set()
    for item in source_rows:
        row = item["raw_row"]
        if row.get("split") == "eval":
            for key in ("task_id", "trajectory_id", "pair_id"):
                value = row.get(key)
                if isinstance(value, str):
                    identifiers.add(value)
    return identifiers


def source_license_label(row: dict[str, Any]) -> str:
    source_repo = row.get("source_repo")
    if isinstance(source_repo, dict) and isinstance(source_repo.get("license"), str):
        return source_repo["license"]
    metadata = row.get("metadata")
    if isinstance(metadata, dict) and metadata.get("source"):
        return "missing_explicit_license_for_internal_generated_row"
    return "missing"


def provenance_fields(row: dict[str, Any]) -> dict[str, bool]:
    source_repo = row.get("source_repo")
    repo_snapshot = row.get("repo_snapshot")
    provenance = row.get("provenance")
    metadata = row.get("metadata")
    return {
        "has_source_repo": isinstance(source_repo, dict),
        "has_source_repo_provenance": isinstance(source_repo, dict) and bool(source_repo.get("provenance")),
        "has_explicit_license": source_license_label(row) not in {"missing", "missing_explicit_license_for_internal_generated_row"},
        "has_repo_snapshot_ref": isinstance(repo_snapshot, dict) and bool(repo_snapshot.get("path")),
        "has_immutable_snapshot_flag": isinstance(repo_snapshot, dict) and repo_snapshot.get("immutable_snapshot") is True,
        "has_generator_provenance": isinstance(provenance, dict) and bool(provenance.get("generator")),
        "has_metadata_source": isinstance(metadata, dict) and bool(metadata.get("source")),
        "has_source_gate": bool(row.get("source_gate")),
    }


def provenance_scanner_result(item: dict[str, Any]) -> dict[str, Any]:
    admission = item["admission"]
    row = item["raw_row"]
    fields = provenance_fields(row)
    generator_ref_present = fields["has_generator_provenance"] or fields["has_metadata_source"] or fields["has_source_gate"]
    scaffold_provenance_pass = bool(admission["row_sha256"] and admission["source_file"] and generator_ref_present)
    training_grade_provenance_pass = (
        scaffold_provenance_pass
        and fields["has_source_repo"]
        and fields["has_source_repo_provenance"]
        and fields["has_explicit_license"]
        and fields["has_repo_snapshot_ref"]
        and fields["has_immutable_snapshot_flag"]
        and admission["split"] == "train"
    )
    return {
        "schema_version": "forgeagent.provenance_scan_result.v1",
        "source_row_sha256": admission["row_sha256"],
        "source_file": admission["source_file"],
        "source_row_index": admission["row_index"],
        "split": admission["split"],
        "source_schema": admission["schema"],
        "provenance_fields": fields,
        "generator_ref_present": generator_ref_present,
        "scaffold_provenance_pass": scaffold_provenance_pass,
        "training_grade_provenance_pass": training_grade_provenance_pass,
        "blocked_reasons": [
            reason
            for reason, blocked in [
                ("source_repo_missing", not fields["has_source_repo"]),
                ("source_repo_provenance_missing", not fields["has_source_repo_provenance"]),
                ("explicit_license_missing", not fields["has_explicit_license"]),
                ("repo_snapshot_ref_missing", not fields["has_repo_snapshot_ref"]),
                ("immutable_snapshot_flag_missing", not fields["has_immutable_snapshot_flag"]),
                ("not_train_split", admission["split"] != "train"),
            ]
            if blocked
        ],
    }


def license_scanner_result(item: dict[str, Any]) -> dict[str, Any]:
    admission = item["admission"]
    row = item["raw_row"]
    label = source_license_label(row)
    scaffold_allowed_labels = {"internal_scaffold_only"}
    training_grade_allowed_labels: set[str] = set()
    scaffold_license_pass = label in scaffold_allowed_labels or label == "missing_explicit_license_for_internal_generated_row"
    training_grade_license_pass = label in training_grade_allowed_labels and admission["split"] == "train"
    return {
        "schema_version": "forgeagent.license_scan_result.v1",
        "source_row_sha256": admission["row_sha256"],
        "source_file": admission["source_file"],
        "source_row_index": admission["row_index"],
        "split": admission["split"],
        "source_schema": admission["schema"],
        "license_label_sha256": sha256_text(label),
        "license_class": "internal_scaffold_only" if label == "internal_scaffold_only" else "incomplete_or_unapproved",
        "license_policy_version": "forgeagent.license_policy.scaffold_only.v1",
        "scaffold_license_pass": scaffold_license_pass,
        "training_grade_license_pass": training_grade_license_pass,
        "blocked_reasons": [
            reason
            for reason, blocked in [
                ("license_missing_or_not_explicit", label in {"missing", "missing_explicit_license_for_internal_generated_row"}),
                ("license_not_approved_for_training_grade", label not in training_grade_allowed_labels),
                ("not_train_split", admission["split"] != "train"),
            ]
            if blocked
        ],
    }


def text_fingerprint_fields(row: dict[str, Any]) -> dict[str, str | None]:
    fields: dict[str, str | None] = {}
    for key in ("task_id", "trajectory_id", "pair_id", "instruction", "prompt"):
        value = row.get(key)
        fields[key] = sha256_text(value) if isinstance(value, str) else None
    messages = row.get("messages")
    if isinstance(messages, list):
        fields["messages_sha256"] = sha256_json(messages)
    else:
        fields["messages_sha256"] = None
    return fields


def contamination_scanner_result(
    item: dict[str, Any],
    *,
    private_identifiers: set[str],
    eval_identifiers: set[str],
    task_group_sizes: dict[str, int],
) -> dict[str, Any]:
    admission = item["admission"]
    row = item["raw_row"]
    row_blob = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
    row_keys = flatten_keys(row)
    private_overlap = any(identifier and identifier in row_blob for identifier in private_identifiers)
    eval_overlap = any(identifier and identifier in row_blob for identifier in eval_identifiers)
    task_id = row.get("task_id")
    task_fingerprint = sha256_text(task_id) if isinstance(task_id, str) else None
    same_task_group_size = task_group_sizes.get(task_fingerprint or "", 0)
    withheld_eval_ref_present = any("hidden_test" in key or "hidden_tests" in key for key in row_keys)
    secret_findings = scan_secrets(row_blob)
    public_benchmark_scan_complete = (
        isinstance(row.get("contamination_report"), dict)
        and row["contamination_report"].get("public_benchmark_overlap_checked") is True
    )
    train_private_overlap = admission["split"] == "train" and private_overlap
    train_eval_overlap = admission["split"] == "train" and eval_overlap
    training_grade_contamination_pass = (
        admission["split"] == "train"
        and not train_private_overlap
        and not train_eval_overlap
        and not secret_findings
        and public_benchmark_scan_complete
        and not withheld_eval_ref_present
    )
    return {
        "schema_version": "forgeagent.contamination_scan_result.v1",
        "source_row_sha256": admission["row_sha256"],
        "source_file": admission["source_file"],
        "source_row_index": admission["row_index"],
        "split": admission["split"],
        "source_schema": admission["schema"],
        "text_fingerprints": text_fingerprint_fields(row),
        "task_fingerprint": task_fingerprint,
        "same_task_group_size": same_task_group_size,
        "private_identifier_overlap": private_overlap,
        "eval_identifier_overlap": eval_overlap,
        "train_private_identifier_overlap": train_private_overlap,
        "train_eval_identifier_overlap": train_eval_overlap,
        "withheld_eval_reference_present": withheld_eval_ref_present,
        "secret_finding_count": len(secret_findings),
        "public_benchmark_scan_complete": public_benchmark_scan_complete,
        "external_benchmark_corpus_available": False,
        "near_duplicate_scanner_complete": False,
        "training_grade_contamination_pass": training_grade_contamination_pass,
        "blocked_reasons": [
            reason
            for reason, blocked in [
                ("private_identifier_overlap", train_private_overlap),
                ("eval_identifier_overlap", train_eval_overlap),
                ("withheld_eval_reference_present", withheld_eval_ref_present),
                ("secret_pattern_present", bool(secret_findings)),
                ("public_benchmark_scan_incomplete", not public_benchmark_scan_complete),
                ("near_duplicate_scanner_incomplete", True),
                ("external_benchmark_corpus_absent", True),
                ("not_train_split", admission["split"] != "train"),
            ]
            if blocked
        ],
    }


def scanner_decision(
    provenance: dict[str, Any],
    license_result: dict[str, Any],
    contamination: dict[str, Any],
    admission: dict[str, Any],
) -> dict[str, Any]:
    training_grade_pass = (
        admission["training_grade_admitted"]
        and provenance["training_grade_provenance_pass"]
        and license_result["training_grade_license_pass"]
        and contamination["training_grade_contamination_pass"]
    )
    blocked_reasons = sorted(
        set(
            admission["training_grade_decision_reasons"]
            + provenance["blocked_reasons"]
            + license_result["blocked_reasons"]
            + contamination["blocked_reasons"]
        )
    )
    return {
        "schema_version": "forgeagent.provenance_license_contamination_scanner_decision.v1",
        "source_row_sha256": admission["row_sha256"],
        "source_file": admission["source_file"],
        "source_row_index": admission["row_index"],
        "split": admission["split"],
        "source_schema": admission["schema"],
        "scaffold_allowed": admission["scaffold_admitted"],
        "training_grade_pass": training_grade_pass,
        "blocked_reasons": blocked_reasons,
    }


def build_fingerprint_index(contamination_results: list[dict[str, Any]]) -> dict[str, Any]:
    task_groups: dict[str, list[str]] = defaultdict(list)
    for result in contamination_results:
        fingerprint = result.get("task_fingerprint")
        if isinstance(fingerprint, str):
            task_groups[fingerprint].append(result["source_row_sha256"])
    duplicate_groups = {
        task_hash: sorted(row_hashes)
        for task_hash, row_hashes in task_groups.items()
        if len(row_hashes) > 1
    }
    return {
        "schema_version": "forgeagent.training_data_fingerprint_index.v1",
        "task_fingerprint_count": len(task_groups),
        "same_task_multi_product_group_count": len(duplicate_groups),
        "same_task_multi_product_groups": duplicate_groups,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }


def scan_outputs(paths: list[Path], public_paths: list[Path], private_identifiers: set[str]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    private_identifier_leaks: list[dict[str, Any]] = []
    public_marker_leaks: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
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
        "schema_version": "forgeagent.provenance_license_contamination_privacy_report.v1",
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

    step26_summary = read_json(STEP29_26_DIR / "summary.json")
    step25_summary = read_json(STEP29_25_DIR / "summary.json")
    admissions = read_jsonl(STEP29_25_DIR / "row_admission_results.jsonl")
    if step26_summary["privacy_scan_passed"] is not True:
        raise RuntimeError("Step 29.26 privacy scan is not passing")
    if step26_summary["training_grade_row_count"] != 0:
        raise RuntimeError("Step 29.27 expects training-grade rows to remain absent")
    if step25_summary["raw_row_count"] != len(admissions):
        raise RuntimeError("Step 29.25 admission rows do not match summary")

    source_rows = load_source_rows(admissions)
    private_identifiers = collect_private_identifiers(source_rows)
    eval_identifiers = collect_eval_identifiers(source_rows)
    task_fingerprints = [
        sha256_text(row["raw_row"]["task_id"])
        for row in source_rows
        if isinstance(row["raw_row"].get("task_id"), str)
    ]
    task_group_sizes = Counter(task_fingerprints)

    provenance_results = [provenance_scanner_result(item) for item in source_rows]
    license_results = [license_scanner_result(item) for item in source_rows]
    contamination_results = [
        contamination_scanner_result(
            item,
            private_identifiers=private_identifiers,
            eval_identifiers=eval_identifiers,
            task_group_sizes=task_group_sizes,
        )
        for item in source_rows
    ]
    decisions = [
        scanner_decision(provenance, license_result, contamination, item["admission"])
        for provenance, license_result, contamination, item in zip(
            provenance_results,
            license_results,
            contamination_results,
            source_rows,
            strict=True,
        )
    ]
    fingerprint_index = build_fingerprint_index(contamination_results)

    scan_summary = {
        "schema_version": "forgeagent.provenance_license_contamination_scan_summary.v1",
        "source_row_count": len(source_rows),
        "training_row_count": sum(1 for item in source_rows if item["admission"]["split"] == "train"),
        "eval_row_count": sum(1 for item in source_rows if item["admission"]["split"] == "eval"),
        "private_heldout_row_count": sum(
            1 for item in source_rows if item["admission"]["split"] == "private_heldout"
        ),
        "provenance_scanned_row_count": len(provenance_results),
        "license_scanned_row_count": len(license_results),
        "contamination_scanned_row_count": len(contamination_results),
        "scaffold_provenance_pass_count": sum(
            1 for result in provenance_results if result["scaffold_provenance_pass"]
        ),
        "training_grade_provenance_pass_count": sum(
            1 for result in provenance_results if result["training_grade_provenance_pass"]
        ),
        "scaffold_license_pass_count": sum(1 for result in license_results if result["scaffold_license_pass"]),
        "training_grade_license_pass_count": sum(
            1 for result in license_results if result["training_grade_license_pass"]
        ),
        "train_private_identifier_overlap_count": sum(
            1 for result in contamination_results if result["train_private_identifier_overlap"]
        ),
        "train_eval_identifier_overlap_count": sum(
            1 for result in contamination_results if result["train_eval_identifier_overlap"]
        ),
        "withheld_eval_reference_row_count": sum(
            1 for result in contamination_results if result["withheld_eval_reference_present"]
        ),
        "public_benchmark_scan_complete_count": sum(
            1 for result in contamination_results if result["public_benchmark_scan_complete"]
        ),
        "near_duplicate_scanner_complete": False,
        "same_task_multi_product_group_count": fingerprint_index["same_task_multi_product_group_count"],
        "training_grade_pass_count": sum(1 for decision in decisions if decision["training_grade_pass"]),
    }
    public_report = {
        **scan_summary,
        "schema_version": "forgeagent.public_safe_provenance_license_contamination_report.v1",
        "report_name": "provenance_license_contamination_scanner_v1_public_safe",
        "private_identifier_values_included": False,
        "raw_rows_included": False,
        "patch_content_included": False,
        "prompt_content_included": False,
        "withheld_eval_content_included": False,
        "model_outputs_included": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
    }
    gate_decision = {
        "schema_version": "forgeagent.provenance_license_contamination_gate_decision.v1",
        "gate_name": "provenance_license_contamination_scanner_v1",
        "source_step_ready": True,
        "provenance_scanner_ready": True,
        "license_scanner_ready": True,
        "contamination_scanner_ready": True,
        "fingerprint_index_ready": True,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "blocked_reasons": [
            "training_grade_pass_count_zero",
            "license_policy_allows_scaffold_only",
            "public_benchmark_scan_incomplete",
            "near_duplicate_scanner_incomplete",
            "external_benchmark_corpus_absent",
            "row_level_oracle_quality_certification_not_integrated",
        ],
    }

    paths = {
        "provenance_scan_results": OUT_DIR / "provenance_scan_results.jsonl",
        "license_scan_results": OUT_DIR / "license_scan_results.jsonl",
        "contamination_scan_results": OUT_DIR / "contamination_scan_results.jsonl",
        "row_scanner_decisions": OUT_DIR / "row_scanner_decisions.jsonl",
        "fingerprint_index": OUT_DIR / "fingerprint_index.json",
        "scan_summary": OUT_DIR / "scan_summary.json",
        "gate_decision": OUT_DIR / "provenance_license_contamination_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_provenance_license_contamination_report.json",
    }
    write_jsonl(paths["provenance_scan_results"], provenance_results)
    write_jsonl(paths["license_scan_results"], license_results)
    write_jsonl(paths["contamination_scan_results"], contamination_results)
    write_jsonl(paths["row_scanner_decisions"], decisions)
    write_json(paths["fingerprint_index"], fingerprint_index)
    write_json(paths["scan_summary"], scan_summary)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]], private_identifiers)
    privacy_path = OUT_DIR / "provenance_license_contamination_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        **scan_summary,
        "schema_version": "forgeagent.provenance_license_contamination_scanner_summary.v1",
        "gate_name": "provenance_license_contamination_scanner_v1",
        "git_commit": git_commit(),
        "source_step": "step29_26_training_data_schema_normalization_scaleout_plan_v1",
        "source_step_ready": True,
        "privacy_scan_passed": privacy_report["passed"],
        "public_safe_report_ready": True,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "next_recommended_step": "step29_28_dedup_and_near_duplicate_scanner_implementation",
        "artifacts": {name: rel(path) for name, path in paths.items()} | {"privacy_report": rel(privacy_path)},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("PROVENANCE_LICENSE_CONTAMINATION_SCANNER_V1_OK")


if __name__ == "__main__":
    main()

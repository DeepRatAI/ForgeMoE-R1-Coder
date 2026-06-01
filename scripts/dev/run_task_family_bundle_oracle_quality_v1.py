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
STEP29_28_DIR = PROJECT_ROOT / "results/local/dedup_near_duplicate_scanner_v1"
ORACLE_DIR = PROJECT_ROOT / "results/local/oracle_hidden_test_gate_v0"
PRIVATE_SEED_MANIFEST = (
    PROJECT_ROOT / "results/local/private_heldout_seed_set_v1/dataset_exports/private_heldout_seed_manifest.jsonl"
)
OUT_DIR = PROJECT_ROOT / "results/local/task_family_bundle_oracle_quality_v1"

MINIMUM_ORACLE_STRENGTH_SCORE = 0.95

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


def product_type(schema: str) -> str:
    if "patch_sft" in schema:
        return "patch_sft"
    if "preference" in schema:
        return "preference_pair"
    if "repair_trace" in schema:
        return "repair_trace"
    if "trajectory" in schema:
        return "trajectory"
    if "synthetic_executable_task" in schema:
        return "executable_task_ref"
    return "unknown"


def task_fingerprint(row: dict[str, Any]) -> str | None:
    task_id = row.get("task_id")
    return sha256_text(task_id) if isinstance(task_id, str) else None


def load_oracle_scores() -> dict[str, dict[str, Any]]:
    return {
        sha256_text(row["task_id"]): row
        for row in read_jsonl(ORACLE_DIR / "task_oracle_scores.jsonl")
        if isinstance(row.get("task_id"), str)
    }


def load_challenge_summary() -> dict[str, dict[str, int]]:
    challenge_rows = read_jsonl(ORACLE_DIR / "patch_challenge_results.jsonl")
    summary: dict[str, Counter[str]] = defaultdict(Counter)
    for row in challenge_rows:
        task_id = row.get("task_id")
        if not isinstance(task_id, str):
            continue
        key = sha256_text(task_id)
        challenge = row.get("challenge")
        if isinstance(challenge, str):
            summary[key]["challenge_count"] += 1
            summary[key][f"{challenge}_count"] += 1
            if row.get("solved") is True:
                summary[key][f"{challenge}_solved_count"] += 1
            if row.get("patch_check_passed") is True:
                summary[key][f"{challenge}_git_apply_check_pass_count"] += 1
            if row.get("post_hidden_passed") is True:
                summary[key][f"{challenge}_hidden_pass_count"] += 1
            if row.get("pre_public_failed_as_expected") is True:
                summary[key]["pre_public_fail_count"] += 1
    return {task_hash: dict(counts) for task_hash, counts in summary.items()}


def build_bundle_manifest(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in source_rows:
        fingerprint = task_fingerprint(item["raw_row"])
        if fingerprint is not None:
            groups[fingerprint].append(item)

    bundles: list[dict[str, Any]] = []
    for bundle_hash, items in sorted(groups.items()):
        splits = sorted({item["admission"]["split"] for item in items})
        schemas = sorted({item["admission"]["schema"] for item in items})
        products = sorted({product_type(item["admission"]["schema"]) for item in items})
        row_hashes = sorted(item["admission"]["row_sha256"] for item in items)
        split = splits[0] if len(splits) == 1 else "mixed"
        is_train_bundle = split == "train"
        is_eval_or_private_bundle = split in {"eval", "private_heldout"}
        bundle_policy_pass = len(splits) == 1
        bundles.append(
            {
                "schema_version": "forgeagent.task_family_bundle.v1",
                "task_bundle_fingerprint": bundle_hash,
                "split": split,
                "split_count": len(splits),
                "splits": splits,
                "row_count": len(items),
                "source_schemas": schemas,
                "product_types": products,
                "row_sha256s": row_hashes,
                "is_train_bundle": is_train_bundle,
                "is_eval_or_private_bundle": is_eval_or_private_bundle,
                "same_task_multi_product_allowed_within_bundle": bundle_policy_pass,
                "bundle_policy_pass": bundle_policy_pass,
                "training_bundle_release_candidate": is_train_bundle and bundle_policy_pass,
                "contains_raw_text": False,
                "contains_private_identifiers": False,
            }
        )
    return bundles


def build_oracle_certifications(
    source_rows: list[dict[str, Any]],
    oracle_scores: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    certifications: list[dict[str, Any]] = []
    for item in source_rows:
        admission = item["admission"]
        row = item["raw_row"]
        bundle_hash = task_fingerprint(row)
        score = oracle_scores.get(bundle_hash or "")
        task_oracle_certified = bool(
            score
            and score.get("gate_passed") is True
            and score.get("oracle_strength_score", 0.0) >= MINIMUM_ORACLE_STRENGTH_SCORE
            and score.get("checks", {}).get("golden_patch_passed") is True
            and score.get("checks", {}).get("rejected_patch_failed") is True
            and score.get("checks", {}).get("semantic_noop_patch_failed") is True
            and score.get("checks", {}).get("empty_patch_failed") is True
            and score.get("checks", {}).get("wrong_file_patch_failed") is True
            and score.get("checks", {}).get("public_overfit_caught_by_hidden") is True
        )
        row_training_payload_oracle_certified = (
            admission["split"] == "train"
            and task_oracle_certified
            and not admission["withheld_eval_reference_present"]
        )
        blocked_reasons = [
            reason
            for reason, blocked in [
                ("task_oracle_not_certified", not task_oracle_certified),
                ("not_train_split", admission["split"] != "train"),
                ("withheld_eval_reference_present", admission["withheld_eval_reference_present"]),
            ]
            if blocked
        ]
        certifications.append(
            {
                "schema_version": "forgeagent.row_oracle_quality_certification.v1",
                "source_row_sha256": admission["row_sha256"],
                "source_file": admission["source_file"],
                "source_row_index": admission["row_index"],
                "split": admission["split"],
                "source_schema": admission["schema"],
                "task_bundle_fingerprint": bundle_hash,
                "task_oracle_certified": task_oracle_certified,
                "oracle_strength_score": score.get("oracle_strength_score") if score else None,
                "minimum_oracle_strength_score": MINIMUM_ORACLE_STRENGTH_SCORE,
                "row_training_payload_oracle_certified": row_training_payload_oracle_certified,
                "blocked_reasons": blocked_reasons,
                "contains_raw_text": False,
                "contains_private_identifiers": False,
            }
        )
    return certifications


def build_training_candidate_decisions(
    source_rows: list[dict[str, Any]],
    bundles: list[dict[str, Any]],
    certifications: list[dict[str, Any]],
    dedup_decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bundle_by_hash = {bundle["task_bundle_fingerprint"]: bundle for bundle in bundles}
    cert_by_row = {cert["source_row_sha256"]: cert for cert in certifications}
    dedup_by_row = {row["source_row_sha256"]: row for row in dedup_decisions}
    decisions: list[dict[str, Any]] = []
    for item in source_rows:
        admission = item["admission"]
        row_hash = admission["row_sha256"]
        cert = cert_by_row[row_hash]
        bundle = bundle_by_hash.get(cert["task_bundle_fingerprint"] or "")
        dedup = dedup_by_row.get(row_hash, {})
        same_task_blocker_resolved = bool(
            bundle
            and bundle["bundle_policy_pass"]
            and "same_task_multi_product_group_requires_bundle_policy" in dedup.get("blocked_reasons", [])
        )
        row_release_candidate = (
            admission["split"] == "train"
            and bool(bundle and bundle["training_bundle_release_candidate"])
            and cert["row_training_payload_oracle_certified"]
            and same_task_blocker_resolved
            and not admission["withheld_eval_reference_present"]
        )
        remaining_blockers = set(admission["training_grade_decision_reasons"])
        remaining_blockers.discard("training_oracle_quality_not_certified")
        if same_task_blocker_resolved:
            remaining_blockers.discard("same_task_multi_product_group_requires_bundle_policy")
        if not cert["row_training_payload_oracle_certified"]:
            remaining_blockers.add("row_training_payload_oracle_not_certified")
        if admission["split"] != "train":
            remaining_blockers.add("not_train_split")
        training_grade_candidate_after_step29_29 = row_release_candidate and not remaining_blockers
        decisions.append(
            {
                "schema_version": "forgeagent.step29_29_training_candidate_decision.v1",
                "source_row_sha256": row_hash,
                "source_file": admission["source_file"],
                "source_row_index": admission["row_index"],
                "split": admission["split"],
                "source_schema": admission["schema"],
                "task_bundle_fingerprint": cert["task_bundle_fingerprint"],
                "bundle_policy_pass": bool(bundle and bundle["bundle_policy_pass"]),
                "same_task_multi_product_blocker_resolved": same_task_blocker_resolved,
                "row_training_payload_oracle_certified": cert["row_training_payload_oracle_certified"],
                "training_grade_candidate_after_step29_29": training_grade_candidate_after_step29_29,
                "remaining_blockers": sorted(remaining_blockers),
                "contains_raw_text": False,
                "contains_private_identifiers": False,
            }
        )
    return decisions


def build_split_bundle_isolation_report(
    *,
    bundles: list[dict[str, Any]],
    step28_summary: dict[str, Any],
    split_matrix: dict[str, Any],
) -> dict[str, Any]:
    cross_split_task_bundle_count = sum(1 for bundle in bundles if bundle["split_count"] > 1)
    train_bundle_count = sum(1 for bundle in bundles if bundle["split"] == "train")
    eval_bundle_count = sum(1 for bundle in bundles if bundle["split"] == "eval")
    private_bundle_count = sum(1 for bundle in bundles if bundle["split"] == "private_heldout")
    matrix = split_matrix["matrix"]
    eval_private_high = matrix.get("cross_eval_private_heldout", {}).get("high_near_duplicate_pair_count", 0)
    train_eval_high = matrix.get("cross_eval_train", {}).get("high_near_duplicate_pair_count", 0)
    train_private_high = matrix.get("cross_private_heldout_train", {}).get("high_near_duplicate_pair_count", 0)
    train_bundle_isolation_passed = cross_split_task_bundle_count == 0 and train_eval_high == 0 and train_private_high == 0
    eval_private_distinctness_passed = eval_private_high == 0
    split_bundle_isolation_passed = train_bundle_isolation_passed and eval_private_distinctness_passed
    return {
        "schema_version": "forgeagent.split_bundle_isolation_report.v1",
        "bundle_count": len(bundles),
        "train_bundle_count": train_bundle_count,
        "eval_bundle_count": eval_bundle_count,
        "private_heldout_bundle_count": private_bundle_count,
        "cross_split_task_bundle_count": cross_split_task_bundle_count,
        "same_task_multi_product_group_count_from_step29_28": step28_summary["same_task_multi_product_group_count"],
        "train_eval_high_near_duplicate_pair_count": train_eval_high,
        "train_private_high_near_duplicate_pair_count": train_private_high,
        "eval_private_high_near_duplicate_pair_count": eval_private_high,
        "cross_split_high_near_duplicate_pair_count": step28_summary["cross_split_high_near_duplicate_pair_count"],
        "train_bundle_isolation_passed": train_bundle_isolation_passed,
        "eval_private_distinctness_passed": eval_private_distinctness_passed,
        "split_bundle_isolation_passed": split_bundle_isolation_passed,
        "private_generalization_claim_allowed": False,
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
        "schema_version": "forgeagent.task_family_bundle_oracle_quality_privacy_report.v1",
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

    step28_summary = read_json(STEP29_28_DIR / "summary.json")
    split_matrix = read_json(STEP29_28_DIR / "split_collision_matrix.json")
    dedup_decisions = read_jsonl(STEP29_28_DIR / "dedup_row_decisions.jsonl")
    oracle_summary = read_json(ORACLE_DIR / "summary.json")
    if step28_summary["near_duplicate_scanner_complete"] is not True:
        raise RuntimeError("Step 29.28 near-duplicate scanner is not complete")
    if step28_summary["privacy_scan_passed"] is not True:
        raise RuntimeError("Step 29.28 privacy scan is not passing")
    if oracle_summary["minimum_observed_oracle_strength_score"] < MINIMUM_ORACLE_STRENGTH_SCORE:
        raise RuntimeError("Oracle quality is below Step 29.29 threshold")
    if oracle_summary["hidden_test_isolation_passed"] is not True:
        raise RuntimeError("Hidden test isolation is not passing")

    admissions = read_jsonl(STEP29_25_DIR / "row_admission_results.jsonl")
    source_rows = load_source_rows(admissions)
    private_identifiers = collect_private_identifiers(source_rows)
    oracle_scores = load_oracle_scores()
    challenge_summary = load_challenge_summary()
    bundles = build_bundle_manifest(source_rows)
    certifications = build_oracle_certifications(source_rows, oracle_scores)
    candidate_decisions = build_training_candidate_decisions(
        source_rows,
        bundles,
        certifications,
        dedup_decisions,
    )
    split_report = build_split_bundle_isolation_report(
        bundles=bundles,
        step28_summary=step28_summary,
        split_matrix=split_matrix,
    )
    task_oracle_report = {
        "schema_version": "forgeagent.task_oracle_quality_report.v1",
        "oracle_task_count": len(oracle_scores),
        "oracle_task_certified_count": sum(
            1
            for score in oracle_scores.values()
            if score.get("gate_passed") is True
            and score.get("oracle_strength_score", 0.0) >= MINIMUM_ORACLE_STRENGTH_SCORE
        ),
        "minimum_oracle_strength_score": MINIMUM_ORACLE_STRENGTH_SCORE,
        "minimum_observed_oracle_strength_score": oracle_summary["minimum_observed_oracle_strength_score"],
        "hidden_test_isolation_passed": oracle_summary["hidden_test_isolation_passed"],
        "private_heldout_isolation_passed": oracle_summary["private_heldout_isolation_passed"],
        "challenge_summary_by_task_fingerprint": challenge_summary,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }

    summary_core = {
        "schema_version": "forgeagent.task_family_bundle_oracle_quality_summary_core.v1",
        "source_row_count": len(source_rows),
        "training_row_count": sum(1 for item in source_rows if item["admission"]["split"] == "train"),
        "eval_row_count": sum(1 for item in source_rows if item["admission"]["split"] == "eval"),
        "private_heldout_row_count": sum(
            1 for item in source_rows if item["admission"]["split"] == "private_heldout"
        ),
        "bundle_count": len(bundles),
        "train_bundle_count": split_report["train_bundle_count"],
        "eval_bundle_count": split_report["eval_bundle_count"],
        "private_heldout_bundle_count": split_report["private_heldout_bundle_count"],
        "cross_split_task_bundle_count": split_report["cross_split_task_bundle_count"],
        "same_task_multi_product_bundle_count": sum(1 for bundle in bundles if bundle["row_count"] > 1),
        "same_task_multi_product_blocker_resolved_row_count": sum(
            1 for decision in candidate_decisions if decision["same_task_multi_product_blocker_resolved"]
        ),
        "train_bundle_isolation_passed": split_report["train_bundle_isolation_passed"],
        "eval_private_distinctness_passed": split_report["eval_private_distinctness_passed"],
        "split_bundle_isolation_passed": split_report["split_bundle_isolation_passed"],
        "eval_private_high_near_duplicate_pair_count": split_report["eval_private_high_near_duplicate_pair_count"],
        "train_eval_high_near_duplicate_pair_count": split_report["train_eval_high_near_duplicate_pair_count"],
        "train_private_high_near_duplicate_pair_count": split_report["train_private_high_near_duplicate_pair_count"],
        "task_oracle_certified_count": task_oracle_report["oracle_task_certified_count"],
        "row_task_oracle_certified_count": sum(1 for cert in certifications if cert["task_oracle_certified"]),
        "row_training_payload_oracle_certified_count": sum(
            1 for cert in certifications if cert["row_training_payload_oracle_certified"]
        ),
        "withheld_reference_row_count": sum(
            1 for item in source_rows if item["admission"]["withheld_eval_reference_present"]
        ),
        "training_grade_candidate_after_step29_29_count": sum(
            1 for decision in candidate_decisions if decision["training_grade_candidate_after_step29_29"]
        ),
        "task_family_bundle_policy_complete": True,
        "oracle_quality_certification_complete": True,
        "private_generalization_claim_allowed": False,
    }
    public_report = {
        **summary_core,
        "schema_version": "forgeagent.public_safe_task_family_bundle_oracle_quality_report.v1",
        "report_name": "task_family_bundle_oracle_quality_v1_public_safe",
        "private_identifier_values_included": False,
        "raw_rows_included": False,
        "raw_text_included": False,
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
        "schema_version": "forgeagent.task_family_bundle_oracle_quality_gate_decision.v1",
        "gate_name": "task_family_bundle_oracle_quality_v1",
        "source_step_ready": True,
        "task_family_bundle_policy_ready": True,
        "oracle_quality_certification_ready": True,
        "task_family_bundle_policy_complete": True,
        "oracle_quality_certification_complete": True,
        "train_bundle_isolation_passed": split_report["train_bundle_isolation_passed"],
        "eval_private_distinctness_passed": split_report["eval_private_distinctness_passed"],
        "split_bundle_isolation_passed": split_report["split_bundle_isolation_passed"],
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "blocked_reasons": [
            "training_grade_candidate_after_step29_29_count_zero",
            "eval_private_high_similarity_requires_harder_private_eval_generation",
            "license_policy_allows_scaffold_only",
            "public_benchmark_scan_incomplete",
            "external_benchmark_corpus_absent",
            "contamination_release_gate_not_integrated",
        ],
    }

    paths = {
        "task_family_bundle_manifest": OUT_DIR / "task_family_bundle_manifest.json",
        "split_bundle_isolation_report": OUT_DIR / "split_bundle_isolation_report.json",
        "oracle_quality_certifications": OUT_DIR / "oracle_quality_certifications.jsonl",
        "task_oracle_quality_report": OUT_DIR / "task_oracle_quality_report.json",
        "training_candidate_decisions": OUT_DIR / "training_candidate_decisions.jsonl",
        "gate_decision": OUT_DIR / "task_family_bundle_oracle_quality_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_task_family_bundle_oracle_quality_report.json",
    }
    write_json(paths["task_family_bundle_manifest"], {
        "schema_version": "forgeagent.task_family_bundle_manifest.v1",
        "bundles": bundles,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    })
    write_json(paths["split_bundle_isolation_report"], split_report)
    write_jsonl(paths["oracle_quality_certifications"], certifications)
    write_json(paths["task_oracle_quality_report"], task_oracle_report)
    write_jsonl(paths["training_candidate_decisions"], candidate_decisions)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]], private_identifiers)
    privacy_path = OUT_DIR / "task_family_bundle_oracle_quality_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        **summary_core,
        "schema_version": "forgeagent.task_family_bundle_oracle_quality_summary.v1",
        "gate_name": "task_family_bundle_oracle_quality_v1",
        "git_commit": git_commit(),
        "source_step": "step29_28_dedup_near_duplicate_scanner_v1",
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
        "next_recommended_step": "step29_30_hardened_task_generation_and_public_benchmark_contamination_registry",
        "artifacts": {name: rel(path) for name, path in paths.items()} | {"privacy_report": rel(privacy_path)},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("TASK_FAMILY_BUNDLE_ORACLE_QUALITY_V1_OK")


if __name__ == "__main__":
    main()

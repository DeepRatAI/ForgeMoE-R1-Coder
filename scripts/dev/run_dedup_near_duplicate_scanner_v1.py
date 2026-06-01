from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_25_DIR = PROJECT_ROOT / "results/local/training_data_governance_scaleout_v1"
STEP29_27_DIR = PROJECT_ROOT / "results/local/provenance_license_contamination_scanner_v1"
PRIVATE_SEED_MANIFEST = (
    PROJECT_ROOT / "results/local/private_heldout_seed_set_v1/dataset_exports/private_heldout_seed_manifest.jsonl"
)
OUT_DIR = PROJECT_ROOT / "results/local/dedup_near_duplicate_scanner_v1"

HIGH_JACCARD_THRESHOLD = 0.82
HIGH_SEQUENCE_THRESHOLD = 0.90
HIGH_CONTAINMENT_THRESHOLD = 0.90
MODERATE_JACCARD_THRESHOLD = 0.62
MODERATE_SEQUENCE_THRESHOLD = 0.78
MODERATE_CONTAINMENT_THRESHOLD = 0.75

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

STOPWORDS = {
    "a",
    "all",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "so",
    "the",
    "to",
    "using",
    "with",
}

TEXT_KEYS = {
    "chosen_patch",
    "chosen_reason",
    "content",
    "events",
    "expected_edit_scope",
    "function_name",
    "instruction",
    "messages",
    "negative_attempt",
    "pair_id",
    "positive_attempt",
    "prompt",
    "rejected_patch",
    "rejected_reason",
    "repair_signal",
    "reward",
    "target_patch",
    "task_family",
    "task_id",
    "trajectory_id",
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


def collect_text_values(data: object, *, parent_key: str = "") -> list[str]:
    values: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            key_text = str(key)
            if key_text in {"path", "repo_snapshot", "golden_patch_ref"}:
                continue
            values.extend(collect_text_values(value, parent_key=key_text))
    elif isinstance(data, list):
        for item in data:
            values.extend(collect_text_values(item, parent_key=parent_key))
    elif isinstance(data, str) and (parent_key in TEXT_KEYS or len(data.split()) >= 3):
        values.append(data)
    return values


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"forge[-_a-z0-9]+", " taskidentifier ", lowered)
    lowered = re.sub(r"\b[a-z_][a-z0-9_]*\b", lambda m: normalize_identifier(m.group(0)), lowered)
    lowered = re.sub(r"[^a-z0-9_+\-*/=<>]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def normalize_identifier(token: str) -> str:
    if token in STOPWORDS:
        return token
    if "_" in token or any(ch.isdigit() for ch in token):
        return "identifier"
    return token


def token_set(normalized_text: str) -> set[str]:
    tokens = set()
    for token in normalized_text.split():
        if token in STOPWORDS:
            continue
        if len(token) < 2:
            continue
        tokens.add(token)
    return tokens


def row_text(row: dict[str, Any]) -> str:
    return "\n".join(collect_text_values(row))


def row_feature(item: dict[str, Any]) -> dict[str, Any]:
    admission = item["admission"]
    row = item["raw_row"]
    text = row_text(row)
    normalized = normalize_text(text)
    tokens = token_set(normalized)
    task_id = row.get("task_id")
    trajectory_id = row.get("trajectory_id")
    pair_id = row.get("pair_id")
    instruction = row.get("instruction") or row.get("prompt")
    return {
        "schema_version": "forgeagent.dedup_row_feature.v1",
        "source_row_sha256": admission["row_sha256"],
        "source_file": admission["source_file"],
        "source_row_index": admission["row_index"],
        "split": admission["split"],
        "source_schema": admission["schema"],
        "task_fingerprint": sha256_text(task_id) if isinstance(task_id, str) else None,
        "trajectory_fingerprint": sha256_text(trajectory_id) if isinstance(trajectory_id, str) else None,
        "pair_fingerprint": sha256_text(pair_id) if isinstance(pair_id, str) else None,
        "instruction_fingerprint": sha256_text(instruction) if isinstance(instruction, str) else None,
        "normalized_text_sha256": sha256_text(normalized),
        "token_set_sha256": sha256_json(sorted(tokens)),
        "normalized_char_count": len(normalized),
        "token_count": len(tokens),
        "contains_raw_text": False,
        "_normalized_text": normalized,
        "_tokens": tokens,
    }


def split_pair_type(split_a: str, split_b: str) -> str:
    if split_a == split_b:
        return f"within_{split_a}"
    return "cross_" + "_".join(sorted([split_a, split_b]))


def pair_metrics(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    tokens_a: set[str] = a["_tokens"]
    tokens_b: set[str] = b["_tokens"]
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    jaccard = len(intersection) / len(union) if union else 1.0
    containment = max(
        len(intersection) / len(tokens_a) if tokens_a else 0.0,
        len(intersection) / len(tokens_b) if tokens_b else 0.0,
    )
    sequence_ratio = SequenceMatcher(None, a["_normalized_text"], b["_normalized_text"], autojunk=False).ratio()
    same_task = a["task_fingerprint"] is not None and a["task_fingerprint"] == b["task_fingerprint"]
    same_trajectory = (
        a["trajectory_fingerprint"] is not None and a["trajectory_fingerprint"] == b["trajectory_fingerprint"]
    )
    same_instruction = (
        a["instruction_fingerprint"] is not None and a["instruction_fingerprint"] == b["instruction_fingerprint"]
    )
    exact_normalized_text = a["normalized_text_sha256"] == b["normalized_text_sha256"]
    containment_is_high_signal = (
        min(len(tokens_a), len(tokens_b)) >= 12
        and containment >= HIGH_CONTAINMENT_THRESHOLD
        and jaccard >= MODERATE_JACCARD_THRESHOLD
    )
    high_near_duplicate = (
        exact_normalized_text
        or same_task
        or same_trajectory
        or same_instruction
        or jaccard >= HIGH_JACCARD_THRESHOLD
        or containment_is_high_signal
        or sequence_ratio >= HIGH_SEQUENCE_THRESHOLD
    )
    moderate_near_duplicate = (
        high_near_duplicate
        or jaccard >= MODERATE_JACCARD_THRESHOLD
        or containment >= MODERATE_CONTAINMENT_THRESHOLD
        or sequence_ratio >= MODERATE_SEQUENCE_THRESHOLD
    )
    if exact_normalized_text:
        duplicate_class = "exact_normalized_text"
    elif same_task:
        duplicate_class = "same_task_multi_product"
    elif same_trajectory:
        duplicate_class = "same_trajectory_multi_product"
    elif same_instruction:
        duplicate_class = "same_instruction"
    elif high_near_duplicate:
        duplicate_class = "high_near_duplicate"
    elif moderate_near_duplicate:
        duplicate_class = "moderate_similarity_review"
    else:
        duplicate_class = "distinct"
    return {
        "schema_version": "forgeagent.dedup_pair_similarity.v1",
        "left_source_row_sha256": a["source_row_sha256"],
        "right_source_row_sha256": b["source_row_sha256"],
        "left_split": a["split"],
        "right_split": b["split"],
        "split_pair_type": split_pair_type(a["split"], b["split"]),
        "left_source_schema": a["source_schema"],
        "right_source_schema": b["source_schema"],
        "same_task_fingerprint": same_task,
        "same_trajectory_fingerprint": same_trajectory,
        "same_instruction_fingerprint": same_instruction,
        "exact_normalized_text": exact_normalized_text,
        "jaccard": round(jaccard, 6),
        "containment": round(containment, 6),
        "sequence_ratio": round(sequence_ratio, 6),
        "high_near_duplicate": high_near_duplicate,
        "moderate_near_duplicate": moderate_near_duplicate,
        "duplicate_class": duplicate_class,
        "contains_raw_text": False,
    }


def build_pairwise(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(features):
        for right in features[left_index + 1 :]:
            pairs.append(pair_metrics(left, right))
    return pairs


def group_by_feature(features: list[dict[str, Any]], key: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for feature in features:
        value = feature.get(key)
        if isinstance(value, str):
            groups[value].append(feature["source_row_sha256"])
    return {value: sorted(rows) for value, rows in groups.items() if len(rows) > 1}


def row_dedup_decisions(features: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocked_by_row: dict[str, set[str]] = defaultdict(set)
    for pair in pairs:
        rows = [pair["left_source_row_sha256"], pair["right_source_row_sha256"]]
        if pair["same_task_fingerprint"]:
            for row_hash in rows:
                blocked_by_row[row_hash].add("same_task_multi_product_group_requires_bundle_policy")
        if pair["high_near_duplicate"]:
            for row_hash in rows:
                blocked_by_row[row_hash].add("high_near_duplicate_requires_review")
        if pair["split_pair_type"].startswith("cross_") and pair["moderate_near_duplicate"]:
            for row_hash in rows:
                blocked_by_row[row_hash].add("cross_split_similarity_requires_review")

    decisions: list[dict[str, Any]] = []
    for feature in features:
        blocked_reasons = sorted(blocked_by_row[feature["source_row_sha256"]])
        training_grade_dedup_pass = feature["split"] == "train" and not blocked_reasons
        if feature["split"] != "train":
            blocked_reasons.append("not_train_split")
        decisions.append(
            {
                "schema_version": "forgeagent.dedup_row_decision.v1",
                "source_row_sha256": feature["source_row_sha256"],
                "source_file": feature["source_file"],
                "source_row_index": feature["source_row_index"],
                "split": feature["split"],
                "source_schema": feature["source_schema"],
                "training_grade_dedup_pass": training_grade_dedup_pass,
                "blocked_reasons": sorted(set(blocked_reasons)),
                "contains_raw_text": False,
            }
        )
    return decisions


def split_collision_matrix(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: Counter())
    for pair in pairs:
        pair_type = pair["split_pair_type"]
        matrix[pair_type]["pair_count"] += 1
        if pair["same_task_fingerprint"]:
            matrix[pair_type]["same_task_pair_count"] += 1
        if pair["high_near_duplicate"]:
            matrix[pair_type]["high_near_duplicate_pair_count"] += 1
        if pair["moderate_near_duplicate"]:
            matrix[pair_type]["moderate_near_duplicate_pair_count"] += 1
    return {
        "schema_version": "forgeagent.dedup_split_collision_matrix.v1",
        "matrix": {key: dict(value) for key, value in sorted(matrix.items())},
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
        "schema_version": "forgeagent.dedup_near_duplicate_privacy_report.v1",
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


def strip_internal_feature_fields(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public_features: list[dict[str, Any]] = []
    for feature in features:
        public_feature = {key: value for key, value in feature.items() if not key.startswith("_")}
        public_features.append(public_feature)
    return public_features


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    step27_summary = read_json(STEP29_27_DIR / "summary.json")
    step27_gate = read_json(STEP29_27_DIR / "provenance_license_contamination_gate_decision.json")
    if step27_summary["privacy_scan_passed"] is not True:
        raise RuntimeError("Step 29.27 privacy scan is not passing")
    if step27_summary["source_row_count"] != 10:
        raise RuntimeError("Step 29.28 expects the current governed 10-row scaffold")
    if step27_gate["contamination_scanner_ready"] is not True:
        raise RuntimeError("Step 29.27 contamination scanner is not ready")

    admissions = read_jsonl(STEP29_25_DIR / "row_admission_results.jsonl")
    source_rows = load_source_rows(admissions)
    private_identifiers = collect_private_identifiers(source_rows)
    features = [row_feature(item) for item in source_rows]
    pairs = build_pairwise(features)
    exact_row_groups = group_by_feature(features, "source_row_sha256")
    exact_normalized_groups = group_by_feature(features, "normalized_text_sha256")
    same_task_groups = group_by_feature(features, "task_fingerprint")
    same_instruction_groups = group_by_feature(features, "instruction_fingerprint")
    split_matrix = split_collision_matrix(pairs)
    decisions = row_dedup_decisions(features, pairs)

    train_rows = [feature for feature in features if feature["split"] == "train"]
    train_row_hashes = {feature["source_row_sha256"] for feature in train_rows}
    train_same_task_groups = {
        group: rows
        for group, rows in same_task_groups.items()
        if any(row_hash in train_row_hashes for row_hash in rows)
    }
    cross_split_high_pairs = [
        pair for pair in pairs if pair["split_pair_type"].startswith("cross_") and pair["high_near_duplicate"]
    ]
    train_eval_high_pairs = [
        pair
        for pair in cross_split_high_pairs
        if {pair["left_split"], pair["right_split"]} == {"train", "eval"}
    ]
    train_private_high_pairs = [
        pair
        for pair in cross_split_high_pairs
        if {pair["left_split"], pair["right_split"]} == {"train", "private_heldout"}
    ]
    high_pairs = [pair for pair in pairs if pair["high_near_duplicate"]]
    moderate_pairs = [pair for pair in pairs if pair["moderate_near_duplicate"]]

    deduplication_passed = (
        not same_task_groups
        and not exact_normalized_groups
        and not cross_split_high_pairs
        and all(decision["training_grade_dedup_pass"] for decision in decisions if decision["split"] == "train")
    )
    scan_summary = {
        "schema_version": "forgeagent.dedup_near_duplicate_scan_summary.v1",
        "source_row_count": len(features),
        "training_row_count": len(train_rows),
        "eval_row_count": sum(1 for feature in features if feature["split"] == "eval"),
        "private_heldout_row_count": sum(1 for feature in features if feature["split"] == "private_heldout"),
        "pairwise_comparison_count": len(pairs),
        "dedup_row_feature_count": len(features),
        "exact_row_duplicate_group_count": len(exact_row_groups),
        "exact_normalized_text_group_count": len(exact_normalized_groups),
        "same_task_multi_product_group_count": len(same_task_groups),
        "same_instruction_group_count": len(same_instruction_groups),
        "train_same_task_multi_product_group_count": len(train_same_task_groups),
        "train_same_task_multi_product_row_count": len(
            {row_hash for rows in train_same_task_groups.values() for row_hash in rows if row_hash in train_row_hashes}
        ),
        "high_near_duplicate_pair_count": len(high_pairs),
        "moderate_near_duplicate_pair_count": len(moderate_pairs),
        "cross_split_high_near_duplicate_pair_count": len(cross_split_high_pairs),
        "train_eval_high_near_duplicate_pair_count": len(train_eval_high_pairs),
        "train_private_high_near_duplicate_pair_count": len(train_private_high_pairs),
        "training_grade_dedup_pass_count": sum(
            1 for decision in decisions if decision["training_grade_dedup_pass"]
        ),
        "near_duplicate_scanner_complete": True,
        "split_isolation_high_similarity_passed": len(cross_split_high_pairs) == 0,
        "deduplication_passed": deduplication_passed,
    }
    public_report = {
        **scan_summary,
        "schema_version": "forgeagent.public_safe_dedup_near_duplicate_report.v1",
        "report_name": "dedup_near_duplicate_scanner_v1_public_safe",
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
        "schema_version": "forgeagent.dedup_near_duplicate_gate_decision.v1",
        "gate_name": "dedup_near_duplicate_scanner_v1",
        "source_step_ready": True,
        "dedup_scanner_ready": True,
        "near_duplicate_scanner_ready": True,
        "pairwise_similarity_matrix_ready": True,
        "split_collision_matrix_ready": True,
        "hash_only_outputs": True,
        "deduplication_passed": deduplication_passed,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "blocked_reasons": [
            "training_grade_pass_count_zero",
            "same_task_multi_product_groups_require_bundle_policy",
            "license_policy_allows_scaffold_only",
            "public_benchmark_scan_incomplete",
            "external_benchmark_corpus_absent",
            "row_level_oracle_quality_certification_not_integrated",
        ],
    }
    if cross_split_high_pairs:
        gate_decision["blocked_reasons"].append("cross_split_high_near_duplicate_pairs_present")

    paths = {
        "dedup_row_features": OUT_DIR / "dedup_row_features.jsonl",
        "pairwise_similarity_results": OUT_DIR / "pairwise_similarity_results.jsonl",
        "dedup_row_decisions": OUT_DIR / "dedup_row_decisions.jsonl",
        "exact_duplicate_groups": OUT_DIR / "exact_duplicate_groups.json",
        "near_duplicate_groups": OUT_DIR / "near_duplicate_groups.json",
        "split_collision_matrix": OUT_DIR / "split_collision_matrix.json",
        "scan_summary": OUT_DIR / "scan_summary.json",
        "gate_decision": OUT_DIR / "dedup_near_duplicate_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_dedup_near_duplicate_report.json",
    }
    near_duplicate_groups = {
        "schema_version": "forgeagent.near_duplicate_groups.v1",
        "same_task_multi_product_groups": same_task_groups,
        "same_instruction_groups": same_instruction_groups,
        "exact_normalized_text_groups": exact_normalized_groups,
        "high_near_duplicate_pairs": [
            pair for pair in high_pairs if pair["duplicate_class"] != "distinct"
        ],
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }
    exact_duplicate_groups = {
        "schema_version": "forgeagent.exact_duplicate_groups.v1",
        "exact_row_duplicate_groups": exact_row_groups,
        "exact_normalized_text_groups": exact_normalized_groups,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }
    write_jsonl(paths["dedup_row_features"], strip_internal_feature_fields(features))
    write_jsonl(paths["pairwise_similarity_results"], pairs)
    write_jsonl(paths["dedup_row_decisions"], decisions)
    write_json(paths["exact_duplicate_groups"], exact_duplicate_groups)
    write_json(paths["near_duplicate_groups"], near_duplicate_groups)
    write_json(paths["split_collision_matrix"], split_matrix)
    write_json(paths["scan_summary"], scan_summary)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]], private_identifiers)
    privacy_path = OUT_DIR / "dedup_near_duplicate_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        **scan_summary,
        "schema_version": "forgeagent.dedup_near_duplicate_scanner_summary.v1",
        "gate_name": "dedup_near_duplicate_scanner_v1",
        "git_commit": git_commit(),
        "source_step": "step29_27_provenance_license_contamination_scanner_v1",
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
        "next_recommended_step": "step29_29_task_family_bundle_isolation_and_oracle_quality_certification",
        "artifacts": {name: rel(path) for name, path in paths.items()} | {"privacy_report": rel(privacy_path)},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("DEDUP_NEAR_DUPLICATE_SCANNER_V1_OK")


if __name__ == "__main__":
    main()

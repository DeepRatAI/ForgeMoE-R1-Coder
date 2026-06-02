from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import re
import shutil
import statistics
import subprocess
from typing import Any

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_36_DIR = PROJECT_ROOT / "results/local/training_payload_materialization_authorization_v1"
OUT_DIR = PROJECT_ROOT / "results/local/training_payload_schema_quality_tokenization_v1"

PROXY_MAX_SEQUENCE_LENGTH = 4096
PREFERRED_TOKENIZER_MODEL_ID = "Qwen/Qwen2.5-Coder-0.5B-Instruct"

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\s*[:=]"),
}

PUBLIC_REPORT_DISALLOWED_MARKERS = [
    "forge-hard-train-",
    "forge-hard-eval-",
    "forge-hard-private-",
    "forge-hard-public-eval-",
    "diff --git",
    "assertEqual",
    '"hidden_tests":',
    '"target_patch":',
    '"repo_files":',
    '"messages":',
    '"content_sha256":',
    '"rendered_text":',
]

PAYLOAD_ROW_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "schema_version",
        "payload_id_sha256",
        "task_id",
        "task_id_sha256",
        "source_blueprint_id_sha256",
        "split",
        "task_family",
        "difficulty_label",
        "behavioral_axes",
        "instruction",
        "repo_snapshot_sha256",
        "repo_files",
        "public_tests",
        "validation_command",
        "target_patch",
        "target_patch_sha256",
        "messages",
        "license_basis",
        "public_benchmark_contamination_checked",
        "hidden_tests_exported",
        "negative_patches_exported",
        "eval_private_or_public_eval_exported",
        "training_export_allowed",
        "training_grade",
        "contains_private_identifiers",
    ],
    "properties": {
        "schema_version": {"const": "forgeagent.patch_sft_training_payload_row.v1"},
        "payload_id_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "task_id": {"type": "string", "minLength": 1},
        "task_id_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "source_blueprint_id_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "split": {"const": "train"},
        "task_family": {"type": "string", "minLength": 1},
        "difficulty_label": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "behavioral_axes": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "instruction": {"type": "string", "minLength": 20},
        "repo_snapshot_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "repo_files": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["path", "content", "content_sha256"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string"},
                    "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
                "additionalProperties": False,
            },
        },
        "public_tests": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["path", "content", "content_sha256"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string", "minLength": 1},
                    "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
                "additionalProperties": False,
            },
        },
        "validation_command": {"const": "python3 -B -m unittest discover -s tests"},
        "target_patch": {"type": "string", "pattern": "^diff --git "},
        "target_patch_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "messages": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": ["role", "content"],
                "properties": {
                    "role": {"type": "string", "enum": ["user", "assistant"]},
                    "content": {"type": "string", "minLength": 1},
                },
                "additionalProperties": False,
            },
        },
        "license_basis": {"const": "forge_internal_generated_synthetic_tasks"},
        "public_benchmark_contamination_checked": {"const": True},
        "hidden_tests_exported": {"const": False},
        "negative_patches_exported": {"const": False},
        "eval_private_or_public_eval_exported": {"const": False},
        "training_export_allowed": {"const": True},
        "training_grade": {"const": True},
        "contains_private_identifiers": {"const": False},
    },
    "additionalProperties": True,
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


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * q)]


def proxy_token_count(text: str) -> dict[str, Any]:
    regex_tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\w\s]", text, flags=re.UNICODE)
    char_div3 = math.ceil(len(text) / 3)
    whitespace_tokens = len([part for part in re.split(r"\s+", text.strip()) if part])
    estimate = max(len(regex_tokens), char_div3, 1)
    return {
        "method": "max(regex_code_token_count, ceil(character_count/3))",
        "character_count": len(text),
        "regex_code_token_count": len(regex_tokens),
        "whitespace_token_count": whitespace_tokens,
        "estimated_token_count": estimate,
    }


def render_sft_text(row: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "<|user|>",
            row["messages"][0]["content"].rstrip(),
            "<|assistant|>",
            row["messages"][1]["content"].rstrip(),
        ]
    ).rstrip() + "\n"


def tokenizer_environment() -> dict[str, Any]:
    modules = {
        name: importlib.util.find_spec(name) is not None
        for name in ("transformers", "tokenizers", "sentencepiece", "tiktoken")
    }
    return {
        "schema_version": "forgeagent.tokenizer_environment_report.v1",
        "preferred_tokenizer_model_id": PREFERRED_TOKENIZER_MODEL_ID,
        "available_modules": modules,
        "model_specific_tokenizer_available": any(modules.values()),
        "model_specific_tokenizer_validation_passed": False,
        "model_specific_tokenizer_required_before_training_launch": True,
        "full_weight_load_attempted": False,
        "local_model_execution_used": False,
    }


def validate_row(
    row: dict[str, Any],
    manifest: dict[str, Any],
    validator: Draft202012Validator,
) -> dict[str, Any]:
    errors = sorted(validator.iter_errors(row), key=lambda item: list(item.path))
    schema_valid = not errors
    repo_hashes_valid = all(item["content_sha256"] == sha256_text(item["content"]) for item in row["repo_files"])
    public_hashes_valid = all(item["content_sha256"] == sha256_text(item["content"]) for item in row["public_tests"])
    target_patch_hash_valid = row["target_patch_sha256"] == sha256_text(row["target_patch"])
    messages_valid = (
        len(row["messages"]) == 2
        and row["messages"][0]["role"] == "user"
        and row["messages"][1]["role"] == "assistant"
        and row["messages"][1]["content"] == row["target_patch"]
    )
    prompt_sha256 = sha256_text(row["messages"][0]["content"])
    payload_id_recomputed = sha256_json(
        {
            "task_id_sha256": row["task_id_sha256"],
            "repo_snapshot_sha256": row["repo_snapshot_sha256"],
            "target_patch_sha256": row["target_patch_sha256"],
            "prompt_sha256": prompt_sha256,
        }
    )
    row_blob = json.dumps(row, sort_keys=True, ensure_ascii=False)
    manifest_consistent = (
        manifest["payload_id_sha256"] == row["payload_id_sha256"]
        and manifest["task_id_sha256"] == row["task_id_sha256"]
        and manifest["target_patch_sha256"] == row["target_patch_sha256"]
        and manifest["payload_row_sha256"] == sha256_text(row_blob)
        and manifest["prompt_sha256"] == prompt_sha256
        and manifest["repo_file_count"] == len(row["repo_files"])
        and manifest["public_test_file_count"] == len(row["public_tests"])
        and manifest["training_export_allowed"] is True
    )
    no_repo_tests_in_repo_files = all(not item["path"].startswith("tests/") for item in row["repo_files"])
    public_tests_present = len(row["public_tests"]) >= 1
    hidden_markers = ("test_hidden.py", "Class TestHidden", "hidden_tests/")
    negative_markers = ("rejected.patch", "public_overfit.patch", "wrong_file.patch", "semantic_noop.patch")
    hidden_leak = any(marker in row_blob for marker in hidden_markers)
    negative_leak = any(marker in row_blob for marker in negative_markers)
    validation_command_present = row["validation_command"] == "python3 -B -m unittest discover -s tests"
    row_valid = all(
        [
            schema_valid,
            repo_hashes_valid,
            public_hashes_valid,
            target_patch_hash_valid,
            messages_valid,
            row["payload_id_sha256"] == payload_id_recomputed,
            manifest_consistent,
            no_repo_tests_in_repo_files,
            public_tests_present,
            not hidden_leak,
            not negative_leak,
            validation_command_present,
        ]
    )
    return {
        "schema_version": "forgeagent.training_payload_schema_validation_result.v1",
        "payload_id_sha256": row["payload_id_sha256"],
        "task_id_sha256": row["task_id_sha256"],
        "task_family": row["task_family"],
        "schema_valid": schema_valid,
        "schema_error_count": len(errors),
        "schema_errors": [error.message for error in errors],
        "repo_file_hashes_valid": repo_hashes_valid,
        "public_test_hashes_valid": public_hashes_valid,
        "target_patch_hash_valid": target_patch_hash_valid,
        "payload_id_recomputed": payload_id_recomputed,
        "payload_id_valid": row["payload_id_sha256"] == payload_id_recomputed,
        "manifest_consistent": manifest_consistent,
        "messages_valid": messages_valid,
        "no_repo_tests_in_repo_files": no_repo_tests_in_repo_files,
        "public_tests_present": public_tests_present,
        "hidden_test_content_leak": hidden_leak,
        "negative_patch_content_leak": negative_leak,
        "validation_command_present": validation_command_present,
        "row_quality_passed": row_valid,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }


def summarize_token_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = [int(row["estimated_total_tokens"]) for row in rows]
    chars = [int(row["rendered_character_count"]) for row in rows]
    by_family: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_family.setdefault(row["task_family"], {"row_count": 0, "estimated_total_tokens": []})
        bucket["row_count"] += 1
        bucket["estimated_total_tokens"].append(int(row["estimated_total_tokens"]))
    for bucket in by_family.values():
        values = bucket["estimated_total_tokens"]
        bucket["min_estimated_tokens"] = min(values)
        bucket["max_estimated_tokens"] = max(values)
        bucket["mean_estimated_tokens"] = round(statistics.mean(values), 3)
        del bucket["estimated_total_tokens"]
    return {
        "row_count": len(rows),
        "min_estimated_tokens": min(counts) if counts else 0,
        "max_estimated_tokens": max(counts) if counts else 0,
        "mean_estimated_tokens": round(statistics.mean(counts), 3) if counts else 0,
        "median_estimated_tokens": percentile(counts, 0.50),
        "p95_estimated_tokens": percentile(counts, 0.95),
        "min_rendered_chars": min(chars) if chars else 0,
        "max_rendered_chars": max(chars) if chars else 0,
        "would_truncate_proxy_count": sum(1 for row in rows if row["would_truncate_proxy"]),
        "by_task_family": dict(sorted(by_family.items())),
    }


def scan_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern_name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": pattern_name, "count": len(matches)})
    return findings


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
        "schema_version": "forgeagent.training_payload_schema_quality_tokenization_privacy_report.v1",
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

    step36_summary = read_json(STEP29_36_DIR / "summary.json")
    payload_rows = read_jsonl(STEP29_36_DIR / "dataset_exports/patch_sft_training_payload.jsonl")
    manifest_rows = read_jsonl(STEP29_36_DIR / "dataset_exports/patch_sft_training_payload_manifest.jsonl")

    if step36_summary["training_payload_materialization_authorized"] is not True:
        raise RuntimeError("Step 29.36 training payload materialization is not authorized")
    if step36_summary["training_grade_data_release_allowed"] is not True:
        raise RuntimeError("Step 29.36 training-grade data release is not allowed")
    if len(payload_rows) != 4 or len(manifest_rows) != 4:
        raise RuntimeError("Step 29.36 payload row count is not 4")

    manifest_by_id = {row["payload_id_sha256"]: row for row in manifest_rows}
    validator = Draft202012Validator(PAYLOAD_ROW_SCHEMA)
    schema_results = [validate_row(row, manifest_by_id[row["payload_id_sha256"]], validator) for row in payload_rows]

    rendered_rows: list[dict[str, Any]] = []
    token_rows: list[dict[str, Any]] = []
    for row in payload_rows:
        rendered_text = render_sft_text(row)
        prompt_tokens = proxy_token_count(row["messages"][0]["content"])
        target_tokens = proxy_token_count(row["target_patch"])
        rendered_tokens = proxy_token_count(rendered_text)
        would_truncate = rendered_tokens["estimated_token_count"] > PROXY_MAX_SEQUENCE_LENGTH
        rendered_rows.append(
            {
                "schema_version": "forgeagent.rendered_patch_sft_training_payload_row.v1",
                "payload_id_sha256": row["payload_id_sha256"],
                "task_id_sha256": row["task_id_sha256"],
                "split": "train",
                "task_family": row["task_family"],
                "rendered_text": rendered_text,
                "rendered_text_sha256": sha256_text(rendered_text),
                "target_patch_sha256": row["target_patch_sha256"],
                "training_export_allowed": True,
                "training_grade": True,
            }
        )
        token_rows.append(
            {
                "schema_version": "forgeagent.training_payload_tokenization_proxy_row.v1",
                "payload_id_sha256": row["payload_id_sha256"],
                "task_id_sha256": row["task_id_sha256"],
                "split": "train",
                "task_family": row["task_family"],
                "prompt_estimated_tokens": prompt_tokens["estimated_token_count"],
                "target_estimated_tokens": target_tokens["estimated_token_count"],
                "estimated_total_tokens": rendered_tokens["estimated_token_count"],
                "rendered_character_count": rendered_tokens["character_count"],
                "regex_code_token_count": rendered_tokens["regex_code_token_count"],
                "whitespace_token_count": rendered_tokens["whitespace_token_count"],
                "proxy_max_sequence_length": PROXY_MAX_SEQUENCE_LENGTH,
                "would_truncate_proxy": would_truncate,
                "estimation_method": rendered_tokens["method"],
                "model_specific_tokenizer_used": False,
                "contains_raw_text": False,
                "contains_private_identifiers": False,
            }
        )

    token_summary = summarize_token_rows(token_rows)
    tokenizer_env = tokenizer_environment()
    schema_valid_count = sum(1 for row in schema_results if row["schema_valid"])
    quality_pass_count = sum(1 for row in schema_results if row["row_quality_passed"])
    manifest_consistent_count = sum(1 for row in schema_results if row["manifest_consistent"])
    hidden_leak_count = sum(1 for row in schema_results if row["hidden_test_content_leak"])
    negative_leak_count = sum(1 for row in schema_results if row["negative_patch_content_leak"])
    token_budget_proxy_pass_count = sum(1 for row in token_rows if not row["would_truncate_proxy"])

    training_payload_schema_quality_passed = quality_pass_count == len(payload_rows) == 4
    token_budget_proxy_gate_passed = token_budget_proxy_pass_count == len(payload_rows) == 4
    model_specific_tokenizer_validation_passed = tokenizer_env["model_specific_tokenizer_validation_passed"]
    training_launch_allowed = (
        training_payload_schema_quality_passed
        and token_budget_proxy_gate_passed
        and model_specific_tokenizer_validation_passed
    )

    token_report = {
        "schema_version": "forgeagent.training_payload_tokenization_proxy_report.v1",
        "source_step": "step29_36_training_payload_materialization_authorization_v1",
        "preferred_tokenizer_model_id": PREFERRED_TOKENIZER_MODEL_ID,
        "proxy_max_sequence_length": PROXY_MAX_SEQUENCE_LENGTH,
        "tokenizer_environment": tokenizer_env,
        "tokenizer_proxy_summary": token_summary,
        "token_budget_proxy_pass_count": token_budget_proxy_pass_count,
        "would_truncate_proxy_count": token_summary["would_truncate_proxy_count"],
        "token_budget_proxy_gate_passed": token_budget_proxy_gate_passed,
        "model_specific_tokenizer_validation_passed": model_specific_tokenizer_validation_passed,
        "training_launch_allowed": training_launch_allowed,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }
    training_manifest = {
        "schema_version": "forgeagent.patch_sft_training_manifest_v2.v1",
        "dataset_name": "patch_sft_training_payload_step29_37",
        "source_payload": rel(STEP29_36_DIR / "dataset_exports/patch_sft_training_payload.jsonl"),
        "source_payload_manifest": rel(STEP29_36_DIR / "dataset_exports/patch_sft_training_payload_manifest.jsonl"),
        "payload_row_count": len(payload_rows),
        "train_rows": len(payload_rows),
        "eval_rows": 0,
        "objective": "patch_sft_git_diff_generation",
        "target_format": "git_diff_patch",
        "preferred_tokenizer_model_id": PREFERRED_TOKENIZER_MODEL_ID,
        "proxy_max_sequence_length": PROXY_MAX_SEQUENCE_LENGTH,
        "schema_quality_gate": {
            "passed": training_payload_schema_quality_passed,
            "schema_valid_row_count": schema_valid_count,
            "row_quality_pass_count": quality_pass_count,
            "manifest_consistent_row_count": manifest_consistent_count,
        },
        "tokenization_proxy_gate": {
            "passed": token_budget_proxy_gate_passed,
            "token_budget_proxy_pass_count": token_budget_proxy_pass_count,
            "would_truncate_proxy_count": token_summary["would_truncate_proxy_count"],
            "max_estimated_tokens": token_summary["max_estimated_tokens"],
            "p95_estimated_tokens": token_summary["p95_estimated_tokens"],
        },
        "model_specific_tokenizer_gate": {
            "passed": model_specific_tokenizer_validation_passed,
            "required_before_training_launch": True,
            "available_modules": tokenizer_env["available_modules"],
        },
        "training_launch_allowed": training_launch_allowed,
        "model_release_allowed": False,
    }
    readiness = {
        "schema_version": "forgeagent.training_payload_readiness_decision.v1",
        "gate_name": "training_payload_schema_quality_tokenization_v1",
        "training_payload_schema_quality_passed": training_payload_schema_quality_passed,
        "token_budget_proxy_gate_passed": token_budget_proxy_gate_passed,
        "model_specific_tokenizer_validation_passed": model_specific_tokenizer_validation_passed,
        "training_payload_ready_for_model_specific_tokenizer_gate": training_payload_schema_quality_passed
        and token_budget_proxy_gate_passed,
        "training_launch_allowed": training_launch_allowed,
        "model_release_allowed": False,
        "resolved_previous_blockers": ["training_payload_schema_quality_not_verified"]
        if training_payload_schema_quality_passed and token_budget_proxy_gate_passed
        else [],
        "blocked_reasons": []
        if training_launch_allowed
        else ["model_specific_tokenizer_validation_not_complete"],
        "next_recommended_step": "step29_38_model_specific_tokenizer_selection_and_remote_training_cost_gate_v1",
    }
    public_report = {
        "schema_version": "forgeagent.public_safe_training_payload_schema_quality_tokenization_report.v1",
        "report_name": "training_payload_schema_quality_tokenization_v1_public_safe",
        "source_payload_row_count": len(payload_rows),
        "schema_valid_row_count": schema_valid_count,
        "row_quality_pass_count": quality_pass_count,
        "manifest_consistent_row_count": manifest_consistent_count,
        "token_budget_proxy_pass_count": token_budget_proxy_pass_count,
        "would_truncate_proxy_count": token_summary["would_truncate_proxy_count"],
        "max_estimated_tokens": token_summary["max_estimated_tokens"],
        "p95_estimated_tokens": token_summary["p95_estimated_tokens"],
        "hidden_test_content_leak_count": hidden_leak_count,
        "negative_patch_content_leak_count": negative_leak_count,
        "training_payload_schema_quality_passed": training_payload_schema_quality_passed,
        "token_budget_proxy_gate_passed": token_budget_proxy_gate_passed,
        "model_specific_tokenizer_validation_passed": model_specific_tokenizer_validation_passed,
        "training_payload_ready_for_model_specific_tokenizer_gate": readiness[
            "training_payload_ready_for_model_specific_tokenizer_gate"
        ],
        "training_launch_allowed": training_launch_allowed,
        "model_release_allowed": False,
        "raw_task_ids_included": False,
        "raw_rows_included": False,
        "repo_content_included": False,
        "patch_content_included": False,
        "hidden_test_content_included": False,
        "negative_patch_content_included": False,
        "rendered_text_included": False,
        "private_identifier_values_included": False,
        "model_outputs_included": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": readiness["next_recommended_step"],
    }

    paths = {
        "schema_validation_results": OUT_DIR / "schema_validation_results.jsonl",
        "tokenization_proxy_rows": OUT_DIR / "tokenization_proxy_rows.jsonl",
        "tokenization_proxy_report": OUT_DIR / "tokenization_proxy_report.json",
        "training_manifest": OUT_DIR / "training_manifest_v2.json",
        "training_readiness_decision": OUT_DIR / "training_readiness_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_training_payload_schema_quality_tokenization_report.json",
        "rendered_payload": OUT_DIR / "dataset_exports/rendered_patch_sft_training_payload.jsonl",
    }
    write_jsonl(paths["schema_validation_results"], schema_results)
    write_jsonl(paths["tokenization_proxy_rows"], token_rows)
    write_json(paths["tokenization_proxy_report"], token_report)
    write_json(paths["training_manifest"], training_manifest)
    write_json(paths["training_readiness_decision"], readiness)
    write_json(paths["public_safe_report"], public_report)
    write_jsonl(paths["rendered_payload"], rendered_rows)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]])
    privacy_path = OUT_DIR / "training_payload_schema_quality_tokenization_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        "schema_version": "forgeagent.training_payload_schema_quality_tokenization_summary.v1",
        "gate_name": "training_payload_schema_quality_tokenization_v1",
        "git_commit": git_commit(),
        "source_step": "step29_36_training_payload_materialization_authorization_v1",
        "source_step_ready": True,
        "source_payload_row_count": len(payload_rows),
        "schema_valid_row_count": schema_valid_count,
        "row_quality_pass_count": quality_pass_count,
        "manifest_consistent_row_count": manifest_consistent_count,
        "token_budget_proxy_pass_count": token_budget_proxy_pass_count,
        "would_truncate_proxy_count": token_summary["would_truncate_proxy_count"],
        "max_estimated_tokens": token_summary["max_estimated_tokens"],
        "p95_estimated_tokens": token_summary["p95_estimated_tokens"],
        "hidden_test_content_leak_count": hidden_leak_count,
        "negative_patch_content_leak_count": negative_leak_count,
        "training_payload_schema_quality_passed": training_payload_schema_quality_passed,
        "token_budget_proxy_gate_passed": token_budget_proxy_gate_passed,
        "model_specific_tokenizer_available": tokenizer_env["model_specific_tokenizer_available"],
        "model_specific_tokenizer_validation_passed": model_specific_tokenizer_validation_passed,
        "training_payload_ready_for_model_specific_tokenizer_gate": readiness[
            "training_payload_ready_for_model_specific_tokenizer_gate"
        ],
        "training_launch_allowed": training_launch_allowed,
        "model_release_allowed": False,
        "privacy_scan_passed": privacy_report["passed"],
        "public_safe_report_ready": True,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "next_recommended_step": readiness["next_recommended_step"],
        "artifacts": {name: rel(path) for name, path in paths.items()} | {"privacy_report": rel(privacy_path)},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("TRAINING_PAYLOAD_SCHEMA_QUALITY_TOKENIZATION_V1_OK")


if __name__ == "__main__":
    main()

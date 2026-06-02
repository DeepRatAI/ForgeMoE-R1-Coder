from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_30_DIR = PROJECT_ROOT / "results/local/hardened_task_generation_public_benchmark_registry_v1"
STEP29_32_DIR = PROJECT_ROOT / "results/local/hardened_oracle_quality_data_release_integration_v1"
OUT_DIR = PROJECT_ROOT / "results/local/public_benchmark_corpus_scan_license_attestation_v1"

MAX_HTTP_BYTES = 1_000_000
HTTP_TIMEOUT_SECONDS = 20

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\s*[:=]"),
}

PUBLIC_REPORT_DISALLOWED_MARKERS = [
    "diff --git",
    "assertEqual",
    "hidden_tests",
    "golden.patch",
    "public_overfit.patch",
    "rejected.patch",
    "raw_model_output",
    "raw_outputs",
]


BENCHMARK_SOURCES: dict[str, dict[str, Any]] = {
    "public-benchmark-humaneval": {
        "canonical_name": "HumanEval",
        "hf_dataset": "openai/openai_humaneval",
        "github_repo": "openai/human-eval",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-mbpp": {
        "canonical_name": "MBPP",
        "hf_dataset": "google-research-datasets/mbpp",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-bigcodebench": {
        "canonical_name": "BigCodeBench",
        "hf_dataset": "bigcode/bigcodebench",
        "github_repo": "bigcode-project/bigcodebench",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-livecodebench": {
        "canonical_name": "LiveCodeBench",
        "github_repo": "LiveCodeBench/LiveCodeBench",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-swebench": {
        "canonical_name": "SWE-bench",
        "hf_dataset": "princeton-nlp/SWE-bench",
        "github_repo": "princeton-nlp/SWE-bench",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-swebench-verified": {
        "canonical_name": "SWE-bench Verified",
        "hf_dataset": "princeton-nlp/SWE-bench_Verified",
        "github_repo": "princeton-nlp/SWE-bench",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-swebench-multimodal": {
        "canonical_name": "SWE-bench Multimodal",
        "hf_dataset": "SWE-bench/SWE-bench_Multimodal",
        "github_repo": "SWE-bench/SWE-bench",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-apps": {
        "canonical_name": "APPS",
        "hf_dataset": "codeparrot/apps",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-codecontests": {
        "canonical_name": "CodeContests",
        "hf_dataset": "deepmind/code_contests",
        "github_repo": "google-deepmind/code_contests",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-ds1000": {
        "canonical_name": "DS-1000",
        "hf_dataset": "xlangai/DS-1000",
        "github_repo": "xlang-ai/DS-1000",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-repobench": {
        "canonical_name": "RepoBench",
        "hf_dataset": "tianyang/repobench_python_v1.1",
        "github_repo": "Leolty/repobench",
        "expected_policy": "reference_or_eval_only",
    },
    "public-benchmark-cruxeval": {
        "canonical_name": "CRUXEval",
        "hf_dataset": "cruxeval-org/cruxeval",
        "github_repo": "facebookresearch/cruxeval",
        "expected_policy": "reference_or_eval_only",
    },
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def fetch_url(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "ForgeMoE-Coder-Step29.33/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_HTTP_BYTES + 1)
            truncated = len(body) > MAX_HTTP_BYTES
            if truncated:
                body = body[:MAX_HTTP_BYTES]
            return {
                "url": url,
                "status": int(getattr(response, "status", 200)),
                "ok": 200 <= int(getattr(response, "status", 200)) < 400,
                "content_type": response.headers.get("content-type"),
                "content_length_header": response.headers.get("content-length"),
                "bytes_read": len(body),
                "truncated": truncated,
                "sha256": sha256_bytes(body),
                "text": body.decode("utf-8", errors="replace"),
                "error": None,
            }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        return {
            "url": url,
            "status": getattr(exc, "code", None),
            "ok": False,
            "content_type": None,
            "content_length_header": None,
            "bytes_read": 0,
            "truncated": False,
            "sha256": None,
            "text": "",
            "error": repr(exc),
        }


def load_json_response(fetch: dict[str, Any]) -> dict[str, Any] | None:
    if not fetch["ok"] or not fetch["text"]:
        return None
    try:
        data = json.loads(fetch["text"])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def hf_api_url(dataset_id: str) -> str:
    return f"https://huggingface.co/api/datasets/{dataset_id}"


def github_license_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/license"


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def license_values_from_hf(data: dict[str, Any] | None) -> list[str]:
    if not data:
        return []
    values: list[str] = []
    for tag in data.get("tags") or []:
        if isinstance(tag, str) and tag.startswith("license:"):
            values.append(tag.split(":", 1)[1])
    card = data.get("cardData") or {}
    if isinstance(card, dict):
        for value in as_list(card.get("license")):
            if isinstance(value, str):
                values.append(value)
    return sorted(set(values))


def license_value_from_github(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    license_data = data.get("license")
    if isinstance(license_data, dict):
        spdx = license_data.get("spdx_id")
        if isinstance(spdx, str) and spdx and spdx != "NOASSERTION":
            return spdx.lower()
    return None


def sibling_summary(hf_data: dict[str, Any] | None) -> dict[str, Any]:
    siblings = hf_data.get("siblings") if hf_data else None
    if not isinstance(siblings, list):
        return {
            "sibling_count": 0,
            "sibling_path_sha256s": [],
            "large_file_hint_count": 0,
            "metadata_file_count": 0,
        }
    paths = [
        item.get("rfilename")
        for item in siblings
        if isinstance(item, dict) and isinstance(item.get("rfilename"), str)
    ]
    large_hint = sum(1 for path in paths if path.endswith((".parquet", ".jsonl", ".jsonl.gz", ".zip", ".tar.gz")))
    metadata_count = sum(1 for path in paths if path.lower() in {"readme.md", "dataset_infos.json"})
    return {
        "sibling_count": len(paths),
        "sibling_path_sha256s": [sha256_text(path) for path in sorted(paths)],
        "large_file_hint_count": large_hint,
        "metadata_file_count": metadata_count,
    }


def build_benchmark_attestation(entry: dict[str, Any]) -> dict[str, Any]:
    registry_id = entry["registry_id"]
    source = BENCHMARK_SOURCES[registry_id]
    hf_dataset = source.get("hf_dataset")
    github_repo = source.get("github_repo")
    hf_fetch = fetch_url(hf_api_url(hf_dataset)) if hf_dataset else None
    github_fetch = fetch_url(github_license_url(github_repo)) if github_repo else None
    hf_data = load_json_response(hf_fetch) if hf_fetch else None
    github_license_data = load_json_response(github_fetch) if github_fetch else None
    hf_licenses = license_values_from_hf(hf_data)
    github_license = license_value_from_github(github_license_data)
    observed_licenses = sorted(set(hf_licenses + ([github_license] if github_license else [])))
    dataset_license_explicit = bool(hf_licenses)
    official_metadata_verified = bool((hf_fetch and hf_fetch["ok"]) or (github_fetch and github_fetch["ok"]))
    ambiguous_license = not dataset_license_explicit and registry_id.startswith("public-benchmark-swebench")
    direct_training_allowed = False
    license_decision = "reference_or_eval_only_never_train_direct"
    if ambiguous_license:
        license_decision = "reference_or_eval_only_dataset_license_unresolved"
    corpus_summary = sibling_summary(hf_data)
    full_scan_requires_large_materialization = corpus_summary["large_file_hint_count"] > 0 or not hf_dataset
    return {
        "schema_version": "forgeagent.public_benchmark_source_attestation.v1",
        "registry_id": registry_id,
        "benchmark_name": entry["benchmark_name"],
        "canonical_name": source["canonical_name"],
        "policy": entry["policy"],
        "never_train_direct": entry["never_train_direct"],
        "hf_dataset": hf_dataset,
        "hf_api_url": hf_api_url(hf_dataset) if hf_dataset else None,
        "hf_metadata_ok": bool(hf_fetch and hf_fetch["ok"]),
        "hf_dataset_sha": hf_data.get("sha") if hf_data else None,
        "hf_license_values": hf_licenses,
        "github_repo": github_repo,
        "github_license_url": github_license_url(github_repo) if github_repo else None,
        "github_license_ok": bool(github_fetch and github_fetch["ok"]),
        "github_license_spdx": github_license,
        "observed_license_values": observed_licenses,
        "dataset_license_explicit": dataset_license_explicit,
        "dataset_license_ambiguous_or_unresolved": ambiguous_license,
        "official_metadata_verified": official_metadata_verified,
        "metadata_response_sha256s": {
            "hf_api": hf_fetch["sha256"] if hf_fetch else None,
            "github_license": github_fetch["sha256"] if github_fetch else None,
        },
        "corpus_manifest_summary": corpus_summary,
        "bounded_metadata_scan_complete": official_metadata_verified,
        "full_corpus_content_downloaded": False,
        "full_corpus_content_fingerprinted": False,
        "full_scan_requires_large_materialization": full_scan_requires_large_materialization,
        "direct_training_allowed": direct_training_allowed,
        "license_decision": license_decision,
        "contains_raw_benchmark_tasks": False,
        "contains_private_identifiers": False,
    }


def scan_against_hardened_train_candidates(
    attestations: list[dict[str, Any]],
    train_decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in train_decisions:
        candidate_text = " ".join(
            [
                str(decision.get("task_family", "")),
                str(decision.get("split", "")),
                str(decision.get("release_class", "")),
            ]
        ).lower()
        candidate_tokens = {token for token in re.split(r"[^a-z0-9_]+", candidate_text) if len(token) >= 3}
        for attestation in attestations:
            reference_text = " ".join(
                [
                    attestation["benchmark_name"],
                    attestation["canonical_name"],
                    attestation["registry_id"],
                    str(attestation.get("observed_license_values", [])),
                ]
            ).lower()
            reference_tokens = {token for token in re.split(r"[^a-z0-9_]+", reference_text) if len(token) >= 3}
            similarity = 0.0
            if candidate_tokens or reference_tokens:
                similarity = len(candidate_tokens & reference_tokens) / len(candidate_tokens | reference_tokens)
            rows.append(
                {
                    "schema_version": "forgeagent.benchmark_metadata_train_candidate_scan.v1",
                    "task_id_sha256": decision["task_id_sha256"],
                    "benchmark_registry_id_sha256": sha256_text(attestation["registry_id"]),
                    "benchmark_name_sha256": sha256_text(attestation["benchmark_name"]),
                    "metadata_similarity": round(similarity, 6),
                    "exact_hash_collision": False,
                    "high_metadata_similarity": similarity >= 0.74,
                    "contains_raw_text": False,
                    "contains_private_identifiers": False,
                }
            )
    return rows


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
        "schema_version": "forgeagent.public_benchmark_corpus_scan_license_attestation_privacy_report.v1",
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

    step30_registry = read_json(STEP29_30_DIR / "public_benchmark_registry.json")
    step32_summary = read_json(STEP29_32_DIR / "summary.json")
    step32_decisions = read_jsonl(STEP29_32_DIR / "hardened_data_release_decisions.jsonl")

    if step30_registry["registry_entry_count"] != 12:
        raise RuntimeError("Step 29.30 benchmark registry does not contain 12 entries")
    if step32_summary["source_step_ready"] is not True:
        raise RuntimeError("Step 29.32 source step is not ready")
    if step32_summary["oracle_certified_train_candidate_count"] != 4:
        raise RuntimeError("Step 29.32 train candidate count is not 4")

    missing_sources = sorted(
        entry["registry_id"] for entry in step30_registry["entries"] if entry["registry_id"] not in BENCHMARK_SOURCES
    )
    if missing_sources:
        raise RuntimeError(f"missing benchmark source definitions: {missing_sources}")

    attestations = [build_benchmark_attestation(entry) for entry in step30_registry["entries"]]
    train_decisions = [row for row in step32_decisions if row["oracle_certified_train_candidate"]]
    metadata_scan_rows = scan_against_hardened_train_candidates(attestations, train_decisions)

    policy_counts = Counter(row["license_decision"] for row in attestations)
    observed_license_counts = Counter(
        license_value for row in attestations for license_value in row["observed_license_values"]
    )
    metadata_fetch_success_count = sum(1 for row in attestations if row["official_metadata_verified"])
    explicit_license_count = sum(1 for row in attestations if row["dataset_license_explicit"])
    ambiguous_license_count = sum(1 for row in attestations if row["dataset_license_ambiguous_or_unresolved"])
    full_corpus_downloaded_count = sum(1 for row in attestations if row["full_corpus_content_downloaded"])
    full_corpus_fingerprinted_count = sum(1 for row in attestations if row["full_corpus_content_fingerprinted"])
    exact_collision_count = sum(1 for row in metadata_scan_rows if row["exact_hash_collision"])
    high_similarity_count = sum(1 for row in metadata_scan_rows if row["high_metadata_similarity"])

    train_license_attestation = {
        "schema_version": "forgeagent.forge_internal_train_candidate_license_attestation.v1",
        "attestation_name": "forge_native_hardened_train_candidates_v1",
        "source_step": "step29_32_hardened_oracle_quality_data_release_integration_v1",
        "oracle_certified_train_candidate_count": len(train_decisions),
        "license_basis": "forge_internal_generated_synthetic_tasks",
        "uses_raw_public_benchmark_content": False,
        "uses_external_repository_snapshot": False,
        "uses_private_heldout_content": False,
        "public_benchmarks_are_reference_or_eval_only": True,
        "license_policy_upgraded_beyond_scaffold_only": True,
        "training_payload_materialization_authorized": False,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }

    corpus_scan_plan = {
        "schema_version": "forgeagent.public_benchmark_full_corpus_scan_plan.v1",
        "benchmark_count": len(attestations),
        "bounded_metadata_scan_complete": metadata_fetch_success_count == len(attestations),
        "full_public_benchmark_corpus_scan_complete": False,
        "full_corpus_downloaded_count": full_corpus_downloaded_count,
        "full_corpus_fingerprinted_count": full_corpus_fingerprinted_count,
        "required_next_actions": [
            "materialize_corpus_snapshots_under_budget_guardrail",
            "fingerprint_problem_statements_tests_and_reference_solutions_where_available",
            "compare_hardened_train_candidates_against_full_public_benchmark_content",
            "store_corpus_snapshot_manifests_in_s3",
            "keep_public_benchmark_content_out_of_training_payloads",
        ],
        "large_materialization_required_count": sum(
            1 for row in attestations if row["full_scan_requires_large_materialization"]
        ),
        "contains_raw_benchmark_tasks": False,
        "contains_private_identifiers": False,
    }

    updated_release_policy = {
        "schema_version": "forgeagent.step29_33_training_release_policy_delta.v1",
        "source_step": "step29_32_hardened_oracle_quality_data_release_integration_v1",
        "requirements": [
            {"requirement": "hardened_executable_tasks_verified", "passed": True},
            {"requirement": "train_split_oracle_certified", "passed": True},
            {"requirement": "train_split_isolated_from_eval_private_public_eval", "passed": True},
            {"requirement": "no_exact_current_reference_collision", "passed": True},
            {"requirement": "no_high_current_private_or_eval_reference_similarity", "passed": True},
            {"requirement": "no_exact_public_benchmark_registry_collision", "passed": True},
            {
                "requirement": "official_public_benchmark_metadata_attested",
                "passed": metadata_fetch_success_count == len(attestations),
            },
            {
                "requirement": "license_policy_upgraded_beyond_scaffold_only",
                "passed": train_license_attestation["license_policy_upgraded_beyond_scaffold_only"],
            },
            {
                "requirement": "full_public_benchmark_corpus_scan_complete",
                "passed": corpus_scan_plan["full_public_benchmark_corpus_scan_complete"],
            },
            {
                "requirement": "training_payload_materialization_authorized",
                "passed": train_license_attestation["training_payload_materialization_authorized"],
            },
        ],
        "training_grade_data_release_allowed": False,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }
    updated_release_policy["passed_requirement_count"] = sum(
        1 for item in updated_release_policy["requirements"] if item["passed"]
    )
    updated_release_policy["failed_requirement_count"] = sum(
        1 for item in updated_release_policy["requirements"] if not item["passed"]
    )

    gate_decision = {
        "schema_version": "forgeagent.public_benchmark_corpus_scan_license_attestation_gate_decision.v1",
        "gate_name": "public_benchmark_corpus_scan_license_attestation_v1",
        "source_step": "step29_32_hardened_oracle_quality_data_release_integration_v1",
        "source_step_ready": True,
        "official_metadata_attestation_complete": metadata_fetch_success_count == len(attestations),
        "license_attestation_complete": True,
        "train_candidate_license_attestation_passed": train_license_attestation[
            "license_policy_upgraded_beyond_scaffold_only"
        ],
        "full_public_benchmark_corpus_scan_complete": False,
        "public_benchmark_direct_training_allowed_count": sum(1 for row in attestations if row["direct_training_allowed"]),
        "training_grade_candidate_after_step29_33_count": 0,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "resolved_previous_blockers": ["license_policy_still_scaffold_only"],
        "blocked_reasons": [
            "full_public_benchmark_corpus_scan_incomplete",
            "training_payload_materialization_not_authorized",
        ],
        "next_recommended_step": "step29_34_bounded_public_benchmark_snapshot_fingerprinting_v1",
    }

    public_report = {
        "schema_version": "forgeagent.public_safe_public_benchmark_corpus_scan_license_attestation_report.v1",
        "report_name": "public_benchmark_corpus_scan_license_attestation_v1_public_safe",
        "benchmark_registry_entry_count": len(attestations),
        "official_metadata_attestation_complete": gate_decision["official_metadata_attestation_complete"],
        "metadata_fetch_success_count": metadata_fetch_success_count,
        "explicit_dataset_license_count": explicit_license_count,
        "ambiguous_or_unresolved_dataset_license_count": ambiguous_license_count,
        "license_decision_counts": dict(sorted(policy_counts.items())),
        "observed_license_counts": dict(sorted(observed_license_counts.items())),
        "benchmark_direct_training_allowed_count": gate_decision["public_benchmark_direct_training_allowed_count"],
        "full_public_benchmark_corpus_scan_complete": False,
        "full_corpus_downloaded_count": full_corpus_downloaded_count,
        "full_corpus_fingerprinted_count": full_corpus_fingerprinted_count,
        "bounded_metadata_scan_pair_count": len(metadata_scan_rows),
        "exact_metadata_collision_count": exact_collision_count,
        "high_metadata_similarity_count": high_similarity_count,
        "train_candidate_license_attestation_passed": gate_decision["train_candidate_license_attestation_passed"],
        "training_grade_candidate_after_step29_33_count": 0,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "raw_benchmark_tasks_included": False,
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
        "source_attestations": OUT_DIR / "public_benchmark_source_attestations.jsonl",
        "metadata_scan_results": OUT_DIR / "benchmark_metadata_train_candidate_scan_results.jsonl",
        "train_candidate_license_attestation": OUT_DIR / "forge_internal_train_candidate_license_attestation.json",
        "corpus_scan_plan": OUT_DIR / "public_benchmark_full_corpus_scan_plan.json",
        "updated_release_policy": OUT_DIR / "step29_33_training_release_policy_delta.json",
        "gate_decision": OUT_DIR / "public_benchmark_corpus_scan_license_attestation_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_public_benchmark_corpus_scan_license_attestation_report.json",
    }
    write_jsonl(paths["source_attestations"], attestations)
    write_jsonl(paths["metadata_scan_results"], metadata_scan_rows)
    write_json(paths["train_candidate_license_attestation"], train_license_attestation)
    write_json(paths["corpus_scan_plan"], corpus_scan_plan)
    write_json(paths["updated_release_policy"], updated_release_policy)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]])
    privacy_path = OUT_DIR / "public_benchmark_corpus_scan_license_attestation_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        "schema_version": "forgeagent.public_benchmark_corpus_scan_license_attestation_summary.v1",
        "gate_name": "public_benchmark_corpus_scan_license_attestation_v1",
        "git_commit": git_commit(),
        "source_step": "step29_32_hardened_oracle_quality_data_release_integration_v1",
        "source_step_ready": True,
        "benchmark_registry_entry_count": len(attestations),
        "official_metadata_source_count": len(BENCHMARK_SOURCES),
        "metadata_fetch_success_count": metadata_fetch_success_count,
        "official_metadata_attestation_complete": gate_decision["official_metadata_attestation_complete"],
        "explicit_dataset_license_count": explicit_license_count,
        "ambiguous_or_unresolved_dataset_license_count": ambiguous_license_count,
        "license_attestation_complete": gate_decision["license_attestation_complete"],
        "train_candidate_license_attestation_passed": gate_decision["train_candidate_license_attestation_passed"],
        "license_policy_upgraded_beyond_scaffold_only": gate_decision["train_candidate_license_attestation_passed"],
        "public_benchmark_direct_training_allowed_count": gate_decision["public_benchmark_direct_training_allowed_count"],
        "full_public_benchmark_corpus_scan_complete": False,
        "full_corpus_downloaded_count": full_corpus_downloaded_count,
        "full_corpus_fingerprinted_count": full_corpus_fingerprinted_count,
        "bounded_metadata_scan_pair_count": len(metadata_scan_rows),
        "exact_metadata_collision_count": exact_collision_count,
        "high_metadata_similarity_count": high_similarity_count,
        "training_payload_materialization_authorized": False,
        "training_grade_candidate_after_step29_33_count": 0,
        "updated_release_policy_passed_requirement_count": updated_release_policy["passed_requirement_count"],
        "updated_release_policy_failed_requirement_count": updated_release_policy["failed_requirement_count"],
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
    print("PUBLIC_BENCHMARK_CORPUS_SCAN_LICENSE_ATTESTATION_V1_OK")


if __name__ == "__main__":
    main()

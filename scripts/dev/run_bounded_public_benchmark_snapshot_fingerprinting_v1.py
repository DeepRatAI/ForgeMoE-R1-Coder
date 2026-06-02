from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import quote
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_30_DIR = PROJECT_ROOT / "results/local/hardened_task_generation_public_benchmark_registry_v1"
STEP29_31_DIR = PROJECT_ROOT / "results/local/hardened_executable_task_generator_v1"
STEP29_32_DIR = PROJECT_ROOT / "results/local/hardened_oracle_quality_data_release_integration_v1"
STEP29_33_DIR = PROJECT_ROOT / "results/local/public_benchmark_corpus_scan_license_attestation_v1"
OUT_DIR = PROJECT_ROOT / "results/local/bounded_public_benchmark_snapshot_fingerprinting_v1"

HTTP_TIMEOUT_SECONDS = 25
MAX_METADATA_BYTES = 1_000_000
MAX_CONTENT_PREFIX_BYTES = 32_768
MAX_CONTENT_FILES_PER_BENCHMARK = 4
MAX_BYTES_PER_BENCHMARK = 131_072
MAX_TOTAL_CONTENT_BYTES = 2_000_000

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
    "content_prefix_sha256",
    "source_url",
]

PREFERRED_METADATA_FILENAMES = {
    "readme.md",
    "dataset_infos.json",
    "dataset_info.json",
    "license",
    "license.md",
    "license.txt",
    "pyproject.toml",
    "setup.py",
}

_GITHUB_TOKEN: str | None = None
_GITHUB_TOKEN_LOADED = False


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


def github_token() -> str | None:
    global _GITHUB_TOKEN, _GITHUB_TOKEN_LOADED
    if _GITHUB_TOKEN_LOADED:
        return _GITHUB_TOKEN
    _GITHUB_TOKEN_LOADED = True
    for env_name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(env_name)
        if value:
            _GITHUB_TOKEN = value.strip()
            return _GITHUB_TOKEN
    try:
        value = subprocess.check_output(["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        value = ""
    _GITHUB_TOKEN = value or None
    return _GITHUB_TOKEN


def fetch_url(url: str, *, max_bytes: int, range_prefix: bool = False) -> dict[str, Any]:
    headers = {"User-Agent": "ForgeMoE-Coder-Step29.34/1.0"}
    if range_prefix:
        headers["Range"] = f"bytes=0-{max_bytes - 1}"
    if url.startswith("https://api.github.com/"):
        token = github_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read(max_bytes + 1)
            truncated = len(body) > max_bytes
            if truncated:
                body = body[:max_bytes]
            status = int(getattr(response, "status", 200))
            return {
                "url": url,
                "status": status,
                "ok": 200 <= status < 400,
                "content_type": response.headers.get("content-type"),
                "content_length_header": response.headers.get("content-length"),
                "bytes_read": len(body),
                "truncated": truncated,
                "range_requested": range_prefix,
                "range_honored": status == 206,
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
            "range_requested": range_prefix,
            "range_honored": False,
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


def hf_resolve_url(dataset_id: str, revision: str, path: str) -> str:
    quoted_path = quote(path, safe="/")
    return f"https://huggingface.co/datasets/{dataset_id}/resolve/{revision}/{quoted_path}"


def github_repo_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}"


def github_tree_url(repo: str, ref: str) -> str:
    return f"https://api.github.com/repos/{repo}/git/trees/{quote(ref, safe='')}?recursive=1"


def github_raw_url(repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{quote(ref, safe='')}/{quote(path, safe='/')}"


def sibling_paths(hf_data: dict[str, Any] | None) -> list[str]:
    siblings = hf_data.get("siblings") if hf_data else None
    if not isinstance(siblings, list):
        return []
    return sorted(
        item["rfilename"]
        for item in siblings
        if isinstance(item, dict) and isinstance(item.get("rfilename"), str)
    )


def tree_entries(github_tree_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    tree = github_tree_data.get("tree") if github_tree_data else None
    if not isinstance(tree, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in tree:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str):
            continue
        rows.append(
            {
                "path": path,
                "mode": item.get("mode"),
                "type": item.get("type"),
                "sha": item.get("sha"),
                "size": item.get("size"),
            }
        )
    return sorted(rows, key=lambda row: row["path"])


def path_role(path: str) -> str:
    lower = path.lower()
    name = lower.rsplit("/", 1)[-1]
    if name.startswith("readme"):
        return "readme"
    if name.startswith("license"):
        return "license"
    if name in {"dataset_infos.json", "dataset_info.json"}:
        return "dataset_info"
    if lower.endswith((".py", ".toml", ".yaml", ".yml", ".json")):
        return "metadata_or_code"
    if lower.endswith((".parquet", ".jsonl", ".jsonl.gz", ".zip", ".tar.gz")):
        return "dataset_payload_prefix"
    return "other"


def select_paths(paths: list[str], limit: int) -> list[str]:
    def score(path: str) -> tuple[int, str]:
        lower = path.lower()
        name = lower.rsplit("/", 1)[-1]
        if name in PREFERRED_METADATA_FILENAMES:
            return (0, lower)
        if lower.endswith((".md", ".json", ".py", ".toml", ".yaml", ".yml")):
            return (1, lower)
        if lower.endswith((".parquet", ".jsonl", ".jsonl.gz")):
            return (2, lower)
        return (3, lower)

    return sorted(paths, key=score)[:limit]


def benchmark_snapshot(
    attestation: dict[str, Any],
    registry_entry: dict[str, Any],
    byte_budget: dict[str, int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    registry_id = attestation["registry_id"]
    hf_dataset = attestation.get("hf_dataset")
    github_repo = attestation.get("github_repo")
    content_rows: list[dict[str, Any]] = []
    hf_fetch = fetch_url(hf_api_url(hf_dataset), max_bytes=MAX_METADATA_BYTES) if hf_dataset else None
    hf_data = load_json_response(hf_fetch) if hf_fetch else None
    paths = sibling_paths(hf_data)
    hf_revision = hf_data.get("sha") if hf_data else attestation.get("hf_dataset_sha")

    github_repo_fetch = fetch_url(github_repo_url(github_repo), max_bytes=MAX_METADATA_BYTES) if github_repo else None
    github_repo_data = load_json_response(github_repo_fetch) if github_repo_fetch else None
    default_branch = github_repo_data.get("default_branch") if github_repo_data else None
    github_tree_fetch = (
        fetch_url(github_tree_url(github_repo, default_branch), max_bytes=MAX_METADATA_BYTES)
        if github_repo and isinstance(default_branch, str)
        else None
    )
    github_tree_data = load_json_response(github_tree_fetch) if github_tree_fetch else None
    tree = tree_entries(github_tree_data)

    selected_sources: list[tuple[str, str, str]] = []
    if hf_dataset and isinstance(hf_revision, str):
        for path in select_paths(paths, MAX_CONTENT_FILES_PER_BENCHMARK):
            selected_sources.append(("hf_dataset", path, hf_resolve_url(hf_dataset, hf_revision, path)))
    if github_repo and isinstance(default_branch, str):
        blob_paths = [row["path"] for row in tree if row.get("type") == "blob"]
        remaining = MAX_CONTENT_FILES_PER_BENCHMARK - len(selected_sources)
        for path in select_paths(blob_paths, max(0, remaining)):
            selected_sources.append(("github_repo", path, github_raw_url(github_repo, default_branch, path)))

    benchmark_bytes = 0
    for source_kind, path, url in selected_sources:
        if byte_budget["total_bytes_read"] >= MAX_TOTAL_CONTENT_BYTES:
            break
        if benchmark_bytes >= MAX_BYTES_PER_BENCHMARK:
            break
        allowed = min(
            MAX_CONTENT_PREFIX_BYTES,
            MAX_TOTAL_CONTENT_BYTES - byte_budget["total_bytes_read"],
            MAX_BYTES_PER_BENCHMARK - benchmark_bytes,
        )
        if allowed <= 0:
            break
        fetch = fetch_url(url, max_bytes=allowed, range_prefix=True)
        bytes_read = int(fetch["bytes_read"])
        benchmark_bytes += bytes_read
        byte_budget["total_bytes_read"] += bytes_read
        content_rows.append(
            {
                "schema_version": "forgeagent.public_benchmark_content_prefix_fingerprint.v1",
                "registry_id": registry_id,
                "source_kind": source_kind,
                "path_sha256": sha256_text(path),
                "path_role": path_role(path),
                "source_url_sha256": sha256_text(url),
                "status": fetch["status"],
                "ok": fetch["ok"],
                "content_type": fetch["content_type"],
                "content_length_header": fetch["content_length_header"],
                "bytes_read": bytes_read,
                "max_prefix_bytes": allowed,
                "range_requested": fetch["range_requested"],
                "range_honored": fetch["range_honored"],
                "truncated_to_budget": fetch["truncated"],
                "content_prefix_sha256": fetch["sha256"],
                "content_persisted": False,
                "contains_raw_text": False,
                "contains_private_identifiers": False,
            }
        )

    hf_path_fingerprint = sha256_json(paths)
    github_tree_fingerprint = sha256_json(
        [
            {
                "path_sha256": sha256_text(row["path"]),
                "mode": row.get("mode"),
                "type": row.get("type"),
                "sha": row.get("sha"),
                "size": row.get("size"),
            }
            for row in tree
        ]
    )
    successful_content = [row for row in content_rows if row["ok"] and row["bytes_read"] > 0]
    snapshot = {
        "schema_version": "forgeagent.public_benchmark_snapshot_fingerprint.v1",
        "registry_id": registry_id,
        "benchmark_name_sha256": sha256_text(attestation["benchmark_name"]),
        "policy": attestation["policy"],
        "never_train_direct": attestation["never_train_direct"],
        "contamination_risk": registry_entry["contamination_risk"],
        "hf_dataset_sha256": sha256_text(hf_dataset) if hf_dataset else None,
        "hf_revision_sha": hf_revision,
        "hf_metadata_ok": bool(hf_fetch and hf_fetch["ok"]),
        "hf_sibling_count": len(paths),
        "hf_sibling_path_fingerprint_sha256": hf_path_fingerprint,
        "github_repo_sha256": sha256_text(github_repo) if github_repo else None,
        "github_repo_metadata_ok": bool(github_repo_fetch and github_repo_fetch["ok"]),
        "github_default_branch_sha256": sha256_text(default_branch) if isinstance(default_branch, str) else None,
        "github_tree_ok": bool(github_tree_fetch and github_tree_fetch["ok"]),
        "github_tree_truncated": bool(github_tree_data.get("truncated")) if github_tree_data else False,
        "github_tree_entry_count": len(tree),
        "github_tree_fingerprint_sha256": github_tree_fingerprint,
        "selected_content_fingerprint_count": len(content_rows),
        "successful_content_fingerprint_count": len(successful_content),
        "selected_content_bytes_read": sum(row["bytes_read"] for row in content_rows),
        "selected_content_prefix_set_sha256": sha256_json(
            [
                {
                    "source_kind": row["source_kind"],
                    "path_sha256": row["path_sha256"],
                    "path_role": row["path_role"],
                    "content_prefix_sha256": row["content_prefix_sha256"],
                }
                for row in content_rows
            ]
        ),
        "bounded_snapshot_complete": bool(
            attestation["official_metadata_verified"]
            and (hf_fetch and hf_fetch["ok"] or github_repo_fetch and github_repo_fetch["ok"])
            and successful_content
        ),
        "full_corpus_content_downloaded": False,
        "full_corpus_content_fingerprinted": False,
        "content_persisted": False,
        "contains_raw_benchmark_tasks": False,
        "contains_private_identifiers": False,
    }
    return snapshot, content_rows


def token_set(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9_]+", text.lower()) if len(token) >= 3}


def build_overlap_rows(
    snapshots: list[dict[str, Any]],
    content_rows: list[dict[str, Any]],
    task_results: list[dict[str, Any]],
    train_decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    public_hashes: set[str] = set()
    for snapshot in snapshots:
        for key in (
            "hf_revision_sha",
            "hf_sibling_path_fingerprint_sha256",
            "github_tree_fingerprint_sha256",
            "selected_content_prefix_set_sha256",
        ):
            value = snapshot.get(key)
            if isinstance(value, str):
                public_hashes.add(value)
    for row in content_rows:
        value = row.get("content_prefix_sha256")
        if isinstance(value, str):
            public_hashes.add(value)

    task_by_id = {row["task_id_sha256"]: row for row in task_results}
    rows: list[dict[str, Any]] = []
    for decision in train_decisions:
        task_id_sha = decision["task_id_sha256"]
        task = task_by_id[task_id_sha]
        candidate_hashes = {
            task_id_sha,
            decision.get("target_patch_sha256"),
            decision.get("repo_snapshot_sha256"),
            task.get("hidden_test_sha256"),
            *(task.get("patch_sha256s") or {}).values(),
        }
        candidate_hashes = {value for value in candidate_hashes if isinstance(value, str)}
        candidate_tokens = token_set(" ".join([decision.get("task_family", ""), task.get("task_family", "")]))
        for snapshot in snapshots:
            public_tokens = token_set(
                " ".join(
                    [
                        snapshot["registry_id"],
                        snapshot["contamination_risk"],
                        snapshot["policy"],
                    ]
                )
            )
            similarity = 0.0
            if candidate_tokens or public_tokens:
                similarity = len(candidate_tokens & public_tokens) / len(candidate_tokens | public_tokens)
            hash_collisions = sorted(candidate_hashes & public_hashes)
            rows.append(
                {
                    "schema_version": "forgeagent.benchmark_snapshot_train_candidate_overlap.v1",
                    "task_id_sha256": task_id_sha,
                    "benchmark_registry_id_sha256": sha256_text(snapshot["registry_id"]),
                    "exact_hash_collision": bool(hash_collisions),
                    "exact_hash_collision_count": len(hash_collisions),
                    "high_token_similarity": similarity >= 0.74,
                    "token_similarity": round(similarity, 6),
                    "contains_raw_text": False,
                    "contains_private_identifiers": False,
                }
            )
    return rows


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
        "schema_version": "forgeagent.public_benchmark_snapshot_fingerprinting_privacy_report.v1",
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

    registry = read_json(STEP29_30_DIR / "public_benchmark_registry.json")
    step31_summary = read_json(STEP29_31_DIR / "summary.json")
    step32_summary = read_json(STEP29_32_DIR / "summary.json")
    step33_summary = read_json(STEP29_33_DIR / "summary.json")
    step33_gate = read_json(STEP29_33_DIR / "public_benchmark_corpus_scan_license_attestation_gate_decision.json")
    attestations = read_jsonl(STEP29_33_DIR / "public_benchmark_source_attestations.jsonl")
    task_results = read_jsonl(STEP29_31_DIR / "task_results.jsonl")
    train_decisions = [
        row for row in read_jsonl(STEP29_32_DIR / "hardened_data_release_decisions.jsonl")
        if row.get("oracle_certified_train_candidate")
    ]

    if registry["registry_entry_count"] != 12:
        raise RuntimeError("Step 29.30 benchmark registry does not contain 12 entries")
    if step31_summary["verified_task_count"] != 12:
        raise RuntimeError("Step 29.31 source tasks are not verified")
    if step32_summary["oracle_certified_train_candidate_count"] != 4:
        raise RuntimeError("Step 29.32 train candidate count is not 4")
    if step33_summary["metadata_fetch_success_count"] != 12 or not step33_gate["license_attestation_complete"]:
        raise RuntimeError("Step 29.33 source attestation is not ready")
    if len(attestations) != 12:
        raise RuntimeError("Step 29.33 source attestation row count is not 12")

    registry_by_id = {entry["registry_id"]: entry for entry in registry["entries"]}
    byte_budget = {"total_bytes_read": 0}
    snapshots: list[dict[str, Any]] = []
    content_rows: list[dict[str, Any]] = []
    for attestation in attestations:
        snapshot, rows = benchmark_snapshot(attestation, registry_by_id[attestation["registry_id"]], byte_budget)
        snapshots.append(snapshot)
        content_rows.extend(rows)

    overlap_rows = build_overlap_rows(snapshots, content_rows, task_results, train_decisions)
    bounded_complete_count = sum(1 for row in snapshots if row["bounded_snapshot_complete"])
    successful_content_fingerprint_count = sum(1 for row in content_rows if row["ok"] and row["bytes_read"] > 0)
    content_bytes_read = sum(row["bytes_read"] for row in content_rows)
    exact_hash_collision_count = sum(row["exact_hash_collision_count"] for row in overlap_rows)
    high_similarity_count = sum(1 for row in overlap_rows if row["high_token_similarity"])

    budget_report = {
        "schema_version": "forgeagent.bounded_public_benchmark_snapshot_budget_report.v1",
        "max_metadata_bytes_per_request": MAX_METADATA_BYTES,
        "max_content_prefix_bytes_per_file": MAX_CONTENT_PREFIX_BYTES,
        "max_content_files_per_benchmark": MAX_CONTENT_FILES_PER_BENCHMARK,
        "max_bytes_per_benchmark": MAX_BYTES_PER_BENCHMARK,
        "max_total_content_bytes": MAX_TOTAL_CONTENT_BYTES,
        "observed_total_content_bytes_read": content_bytes_read,
        "observed_benchmark_count": len(snapshots),
        "selected_content_fingerprint_count": len(content_rows),
        "successful_content_fingerprint_count": successful_content_fingerprint_count,
        "budget_exceeded": content_bytes_read > MAX_TOTAL_CONTENT_BYTES,
        "content_persisted": False,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }

    updated_release_policy = {
        "schema_version": "forgeagent.step29_34_training_release_policy_delta.v1",
        "source_step": "step29_33_public_benchmark_corpus_scan_license_attestation_v1",
        "requirements": [
            {"requirement": "hardened_executable_tasks_verified", "passed": True},
            {"requirement": "train_split_oracle_certified", "passed": True},
            {"requirement": "train_split_isolated_from_eval_private_public_eval", "passed": True},
            {"requirement": "official_public_benchmark_metadata_attested", "passed": True},
            {"requirement": "license_policy_upgraded_beyond_scaffold_only", "passed": True},
            {
                "requirement": "bounded_public_benchmark_snapshot_fingerprinting_complete",
                "passed": bounded_complete_count == len(snapshots),
            },
            {
                "requirement": "no_exact_public_benchmark_snapshot_collision",
                "passed": exact_hash_collision_count == 0,
            },
            {
                "requirement": "no_high_public_benchmark_snapshot_similarity",
                "passed": high_similarity_count == 0,
            },
            {"requirement": "full_public_benchmark_corpus_scan_complete", "passed": False},
            {"requirement": "training_payload_materialization_authorized", "passed": False},
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
        "schema_version": "forgeagent.public_benchmark_snapshot_fingerprinting_gate_decision.v1",
        "gate_name": "bounded_public_benchmark_snapshot_fingerprinting_v1",
        "source_step": "step29_33_public_benchmark_corpus_scan_license_attestation_v1",
        "source_step_ready": True,
        "bounded_snapshot_fingerprinting_complete": bounded_complete_count == len(snapshots),
        "benchmark_snapshot_count": len(snapshots),
        "bounded_snapshot_complete_count": bounded_complete_count,
        "public_benchmark_direct_training_allowed_count": 0,
        "content_prefix_fingerprint_count": len(content_rows),
        "successful_content_prefix_fingerprint_count": successful_content_fingerprint_count,
        "content_prefix_bytes_read": content_bytes_read,
        "content_prefix_bytes_persisted": 0,
        "budget_exceeded": budget_report["budget_exceeded"],
        "exact_public_benchmark_snapshot_collision_count": exact_hash_collision_count,
        "high_public_benchmark_snapshot_similarity_count": high_similarity_count,
        "full_public_benchmark_corpus_scan_complete": False,
        "training_grade_candidate_after_step29_34_count": 0,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "resolved_previous_blockers": ["bounded_public_benchmark_snapshot_fingerprinting_not_started"],
        "blocked_reasons": [
            "full_public_benchmark_corpus_scan_incomplete",
            "training_payload_materialization_not_authorized",
        ],
        "next_recommended_step": "step29_35_full_public_benchmark_corpus_materialization_and_contamination_scan_v1",
    }

    source_kind_counts = Counter(row["source_kind"] for row in content_rows)
    public_report = {
        "schema_version": "forgeagent.public_safe_public_benchmark_snapshot_fingerprinting_report.v1",
        "report_name": "bounded_public_benchmark_snapshot_fingerprinting_v1_public_safe",
        "benchmark_snapshot_count": len(snapshots),
        "bounded_snapshot_fingerprinting_complete": gate_decision["bounded_snapshot_fingerprinting_complete"],
        "bounded_snapshot_complete_count": bounded_complete_count,
        "content_prefix_fingerprint_count": len(content_rows),
        "successful_content_prefix_fingerprint_count": successful_content_fingerprint_count,
        "content_prefix_source_kind_counts": dict(sorted(source_kind_counts.items())),
        "content_prefix_bytes_read": content_bytes_read,
        "content_prefix_bytes_persisted": 0,
        "budget_exceeded": budget_report["budget_exceeded"],
        "public_benchmark_direct_training_allowed_count": 0,
        "exact_public_benchmark_snapshot_collision_count": exact_hash_collision_count,
        "high_public_benchmark_snapshot_similarity_count": high_similarity_count,
        "full_public_benchmark_corpus_scan_complete": False,
        "training_grade_candidate_after_step29_34_count": 0,
        "updated_release_policy_passed_requirement_count": updated_release_policy["passed_requirement_count"],
        "updated_release_policy_failed_requirement_count": updated_release_policy["failed_requirement_count"],
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "raw_benchmark_tasks_included": False,
        "raw_task_ids_included": False,
        "raw_rows_included": False,
        "raw_text_included": False,
        "content_prefix_hashes_included": False,
        "path_values_included": False,
        "patch_content_included": False,
        "hidden_test_content_included": False,
        "private_identifier_values_included": False,
        "model_outputs_included": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": gate_decision["next_recommended_step"],
    }

    paths = {
        "snapshot_fingerprints": OUT_DIR / "public_benchmark_snapshot_fingerprints.jsonl",
        "content_prefix_fingerprints": OUT_DIR / "public_benchmark_content_prefix_fingerprints.jsonl",
        "overlap_results": OUT_DIR / "benchmark_snapshot_train_candidate_overlap_results.jsonl",
        "budget_report": OUT_DIR / "bounded_snapshot_fingerprinting_budget_report.json",
        "updated_release_policy": OUT_DIR / "step29_34_training_release_policy_delta.json",
        "gate_decision": OUT_DIR / "public_benchmark_snapshot_fingerprinting_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_public_benchmark_snapshot_fingerprinting_report.json",
    }
    write_jsonl(paths["snapshot_fingerprints"], snapshots)
    write_jsonl(paths["content_prefix_fingerprints"], content_rows)
    write_jsonl(paths["overlap_results"], overlap_rows)
    write_json(paths["budget_report"], budget_report)
    write_json(paths["updated_release_policy"], updated_release_policy)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]])
    privacy_path = OUT_DIR / "public_benchmark_snapshot_fingerprinting_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        "schema_version": "forgeagent.bounded_public_benchmark_snapshot_fingerprinting_summary.v1",
        "gate_name": "bounded_public_benchmark_snapshot_fingerprinting_v1",
        "git_commit": git_commit(),
        "source_step": "step29_33_public_benchmark_corpus_scan_license_attestation_v1",
        "source_step_ready": True,
        "benchmark_snapshot_count": len(snapshots),
        "bounded_snapshot_complete_count": bounded_complete_count,
        "bounded_snapshot_fingerprinting_complete": gate_decision["bounded_snapshot_fingerprinting_complete"],
        "hf_revision_fingerprinted_count": sum(1 for row in snapshots if row["hf_revision_sha"]),
        "hf_sibling_manifest_fingerprinted_count": sum(1 for row in snapshots if row["hf_sibling_count"] > 0),
        "github_tree_fingerprinted_count": sum(1 for row in snapshots if row["github_tree_ok"]),
        "content_prefix_fingerprint_count": len(content_rows),
        "successful_content_prefix_fingerprint_count": successful_content_fingerprint_count,
        "content_prefix_bytes_read": content_bytes_read,
        "content_prefix_bytes_persisted": 0,
        "budget_exceeded": budget_report["budget_exceeded"],
        "public_benchmark_direct_training_allowed_count": 0,
        "snapshot_train_candidate_overlap_pair_count": len(overlap_rows),
        "exact_public_benchmark_snapshot_collision_count": exact_hash_collision_count,
        "high_public_benchmark_snapshot_similarity_count": high_similarity_count,
        "full_public_benchmark_corpus_scan_complete": False,
        "full_corpus_downloaded_count": 0,
        "full_corpus_fingerprinted_count": 0,
        "training_payload_materialization_authorized": False,
        "training_grade_candidate_after_step29_34_count": 0,
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
        "artifacts": {key: rel(path) for key, path in {**paths, "privacy_report": privacy_path}.items()},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print("BOUNDED_PUBLIC_BENCHMARK_SNAPSHOT_FINGERPRINTING_V1_OK")


if __name__ == "__main__":
    main()

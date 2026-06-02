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
import time
import urllib.error
import urllib.request
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_31_DIR = PROJECT_ROOT / "results/local/hardened_executable_task_generator_v1"
STEP29_32_DIR = PROJECT_ROOT / "results/local/hardened_oracle_quality_data_release_integration_v1"
STEP29_33_DIR = PROJECT_ROOT / "results/local/public_benchmark_corpus_scan_license_attestation_v1"
STEP29_34_DIR = PROJECT_ROOT / "results/local/bounded_public_benchmark_snapshot_fingerprinting_v1"
OUT_DIR = PROJECT_ROOT / "results/local/full_public_benchmark_corpus_materialization_scan_v1"
CACHE_DIR = PROJECT_ROOT / "results/local/cache/full_public_benchmark_corpus_materialization_scan_v1"
CACHE_PATH = CACHE_DIR / "corpus_file_fingerprint_cache.jsonl"

HTTP_TIMEOUT_SECONDS = 45
MAX_METADATA_BYTES = 5_000_000
MAX_TOTAL_STREAM_BYTES = 15_000_000_000
CHUNK_BYTES = 1024 * 1024
STREAM_RETRY_ATTEMPTS = 4
STREAM_RETRY_BACKOFF_SECONDS = 1.5

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
    "content_sha256",
    "source_url",
    "path_sha256",
]

TEXT_SUFFIXES = (".md", ".txt", ".py", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".csv")

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


def headers_for_url(url: str) -> dict[str, str]:
    headers = {"User-Agent": "ForgeMoE-Coder-Step29.35/1.0"}
    if url.startswith("https://api.github.com/"):
        token = github_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_json(url: str, *, max_bytes: int = MAX_METADATA_BYTES) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers=headers_for_url(url))
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read(max_bytes + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    if len(body) > max_bytes:
        body = body[:max_bytes]
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def head_size(url: str) -> tuple[int | None, int | None]:
    request = urllib.request.Request(url, headers=headers_for_url(url), method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            linked_size = response.headers.get("x-linked-size")
            length = response.headers.get("content-length")
            size = int(linked_size or length) if (linked_size or length) else None
            return size, int(getattr(response, "status", 200))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        return None, getattr(exc, "code", None)


def hf_api_url(dataset_id: str) -> str:
    return f"https://huggingface.co/api/datasets/{dataset_id}"


def hf_resolve_url(dataset_id: str, revision: str, path: str) -> str:
    return f"https://huggingface.co/datasets/{dataset_id}/resolve/{revision}/{quote(path, safe='/')}"


def github_repo_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}"


def github_tree_url(repo: str, ref: str) -> str:
    return f"https://api.github.com/repos/{repo}/git/trees/{quote(ref, safe='')}?recursive=1"


def github_raw_url(repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{quote(ref, safe='')}/{quote(path, safe='/')}"


def path_role(path: str) -> str:
    lower = path.lower()
    name = lower.rsplit("/", 1)[-1]
    if name.startswith("readme"):
        return "readme"
    if name.startswith("license"):
        return "license"
    if name in {"dataset_infos.json", "dataset_info.json"}:
        return "dataset_info"
    if lower.endswith((".parquet", ".jsonl", ".jsonl.gz", ".zip", ".tar.gz")):
        return "dataset_payload"
    if lower.endswith(TEXT_SUFFIXES):
        return "text_or_metadata"
    return "other"


def source_key(row: dict[str, Any]) -> str:
    parts = [
        row["source_kind"],
        row["source_id"],
        row["source_revision"],
        row["path_sha256"],
        str(row.get("expected_size_bytes")),
    ]
    return sha256_text("\n".join(parts))


def load_cache() -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(CACHE_PATH):
        cache[row["source_key"]] = row
    return cache


def save_cache(rows: list[dict[str, Any]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        dedup[row["source_key"]] = row
    write_jsonl(CACHE_PATH, sorted(dedup.values(), key=lambda item: item["source_key"]))


def text_token_fingerprint(chunks: list[bytes], path: str) -> str | None:
    if not path.lower().endswith(TEXT_SUFFIXES):
        return None
    text = b"".join(chunks[:8]).decode("utf-8", errors="ignore").lower()
    tokens = sorted({token for token in re.split(r"[^a-z0-9_]+", text) if len(token) >= 4})
    if not tokens:
        return None
    return sha256_json(tokens[:2048])


def is_retryable_stream_error(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, ConnectionResetError):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        return isinstance(reason, (TimeoutError, ConnectionResetError))
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {429, 500, 502, 503, 504}
    return False


def stream_hash_file(source: dict[str, Any], budget: dict[str, int]) -> dict[str, Any]:
    key = source_key(source)
    url = source["source_url"]
    started = time.time()
    last_exc: BaseException | None = None
    last_bytes_read = 0
    for attempt in range(1, STREAM_RETRY_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers=headers_for_url(url))
        h = hashlib.sha256()
        preview_chunks: list[bytes] = []
        bytes_read = 0
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                status = int(getattr(response, "status", 200))
                while True:
                    chunk = response.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    budget["streamed_bytes"] += len(chunk)
                    if budget["streamed_bytes"] > MAX_TOTAL_STREAM_BYTES:
                        raise RuntimeError("Step 29.35 exceeded max total stream budget")
                    h.update(chunk)
                    if len(preview_chunks) < 8:
                        preview_chunks.append(chunk[: min(len(chunk), 8192)])
        except Exception as exc:
            last_exc = exc
            last_bytes_read = bytes_read
            if attempt < STREAM_RETRY_ATTEMPTS and is_retryable_stream_error(exc):
                time.sleep(STREAM_RETRY_BACKOFF_SECONDS * attempt)
                continue
            return {
                **source,
                "source_key": key,
                "schema_version": "forgeagent.public_benchmark_full_corpus_file_fingerprint.v1",
                "status": getattr(exc, "code", None),
                "ok": False,
                "bytes_read": last_bytes_read,
                "content_sha256": None,
                "text_token_fingerprint_sha256": None,
                "duration_seconds": round(time.time() - started, 3),
                "error": repr(last_exc),
                "content_persisted": False,
                "contains_raw_text": False,
                "contains_private_identifiers": False,
                "cache_status": "miss_failed",
                "attempt_count": attempt,
            }
        break
    return {
        **source,
        "source_key": key,
        "schema_version": "forgeagent.public_benchmark_full_corpus_file_fingerprint.v1",
        "status": status,
        "ok": 200 <= status < 400,
        "bytes_read": bytes_read,
        "content_sha256": h.hexdigest(),
        "text_token_fingerprint_sha256": text_token_fingerprint(preview_chunks, source["path_role"]),
        "duration_seconds": round(time.time() - started, 3),
        "error": None,
        "content_persisted": False,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
        "cache_status": "miss_streamed",
        "attempt_count": attempt,
    }


def build_sources(attestations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows: list[dict[str, Any]] = []
    source_manifests: list[dict[str, Any]] = []
    for attestation in attestations:
        registry_id = attestation["registry_id"]
        if attestation.get("hf_dataset"):
            dataset_id = attestation["hf_dataset"]
            hf_data = fetch_json(hf_api_url(dataset_id))
            revision = hf_data.get("sha") if hf_data else attestation.get("hf_dataset_sha")
            siblings = hf_data.get("siblings") if hf_data else []
            paths = sorted(
                item["rfilename"]
                for item in siblings
                if isinstance(item, dict) and isinstance(item.get("rfilename"), str)
            )
            for path in paths:
                url = hf_resolve_url(dataset_id, revision, path)
                size, status = head_size(url)
                source_rows.append(
                    {
                        "registry_id": registry_id,
                        "source_kind": "hf_dataset",
                        "source_id": dataset_id,
                        "source_revision": revision,
                        "path_sha256": sha256_text(path),
                        "path_role": path_role(path),
                        "source_url": url,
                        "source_url_sha256": sha256_text(url),
                        "expected_size_bytes": size,
                        "head_status": status,
                        "content_persisted": False,
                    }
                )
            source_manifests.append(
                {
                    "schema_version": "forgeagent.public_benchmark_full_corpus_source_manifest.v1",
                    "registry_id": registry_id,
                    "source_kind": "hf_dataset",
                    "source_id_sha256": sha256_text(dataset_id),
                    "source_revision": revision,
                    "file_count": len(paths),
                    "expected_size_bytes": sum(row.get("expected_size_bytes") or 0 for row in source_rows if row["registry_id"] == registry_id and row["source_kind"] == "hf_dataset"),
                    "manifest_path_set_sha256": sha256_json([sha256_text(path) for path in paths]),
                    "metadata_ok": bool(hf_data and revision),
                    "contains_raw_text": False,
                    "contains_private_identifiers": False,
                }
            )
        if attestation.get("github_repo"):
            repo = attestation["github_repo"]
            repo_data = fetch_json(github_repo_url(repo))
            branch = repo_data.get("default_branch") if repo_data else None
            tree_data = fetch_json(github_tree_url(repo, branch)) if isinstance(branch, str) else None
            tree = tree_data.get("tree") if tree_data else []
            blob_rows = [
                item for item in tree
                if isinstance(item, dict) and item.get("type") == "blob" and isinstance(item.get("path"), str)
            ]
            for item in sorted(blob_rows, key=lambda x: x["path"]):
                path = item["path"]
                size = int(item.get("size") or 0)
                url = github_raw_url(repo, branch, path)
                source_rows.append(
                    {
                        "registry_id": registry_id,
                        "source_kind": "github_repo",
                        "source_id": repo,
                        "source_revision": branch,
                        "source_blob_sha": item.get("sha"),
                        "path_sha256": sha256_text(path),
                        "path_role": path_role(path),
                        "source_url": url,
                        "source_url_sha256": sha256_text(url),
                        "expected_size_bytes": size,
                        "head_status": 200,
                        "content_persisted": False,
                    }
                )
            source_manifests.append(
                {
                    "schema_version": "forgeagent.public_benchmark_full_corpus_source_manifest.v1",
                    "registry_id": registry_id,
                    "source_kind": "github_repo",
                    "source_id_sha256": sha256_text(repo),
                    "source_revision": branch,
                    "file_count": len(blob_rows),
                    "expected_size_bytes": sum(int(item.get("size") or 0) for item in blob_rows),
                    "manifest_path_set_sha256": sha256_json([sha256_text(item["path"]) for item in blob_rows]),
                    "metadata_ok": bool(tree_data and not tree_data.get("truncated")),
                    "contains_raw_text": False,
                    "contains_private_identifiers": False,
                }
            )
    return source_rows, source_manifests


def build_overlap_rows(
    file_rows: list[dict[str, Any]],
    task_results: list[dict[str, Any]],
    train_decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    public_hashes = {
        value for row in file_rows for value in (
            row.get("content_sha256"),
            row.get("text_token_fingerprint_sha256"),
            row.get("source_blob_sha"),
        )
        if isinstance(value, str)
    }
    task_by_id = {row["task_id_sha256"]: row for row in task_results}
    rows: list[dict[str, Any]] = []
    for decision in train_decisions:
        task = task_by_id[decision["task_id_sha256"]]
        candidate_hashes = {
            decision["task_id_sha256"],
            decision.get("target_patch_sha256"),
            decision.get("repo_snapshot_sha256"),
            task.get("hidden_test_sha256"),
            *(task.get("patch_sha256s") or {}).values(),
        }
        candidate_hashes = {value for value in candidate_hashes if isinstance(value, str)}
        collisions = sorted(candidate_hashes & public_hashes)
        for registry_id in sorted({row["registry_id"] for row in file_rows}):
            registry_public_hashes = {
                value for row in file_rows if row["registry_id"] == registry_id
                for value in (row.get("content_sha256"), row.get("text_token_fingerprint_sha256"), row.get("source_blob_sha"))
                if isinstance(value, str)
            }
            registry_collisions = sorted(candidate_hashes & registry_public_hashes)
            rows.append(
                {
                    "schema_version": "forgeagent.full_corpus_train_candidate_contamination_result.v1",
                    "task_id_sha256": decision["task_id_sha256"],
                    "benchmark_registry_id_sha256": sha256_text(registry_id),
                    "exact_hash_collision": bool(registry_collisions),
                    "exact_hash_collision_count": len(registry_collisions),
                    "global_exact_hash_collision": bool(collisions),
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
        "schema_version": "forgeagent.full_public_benchmark_corpus_materialization_privacy_report.v1",
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

    step34_summary = read_json(STEP29_34_DIR / "summary.json")
    attestations = read_jsonl(STEP29_33_DIR / "public_benchmark_source_attestations.jsonl")
    task_results = read_jsonl(STEP29_31_DIR / "task_results.jsonl")
    train_decisions = [
        row for row in read_jsonl(STEP29_32_DIR / "hardened_data_release_decisions.jsonl")
        if row.get("oracle_certified_train_candidate")
    ]
    if step34_summary["bounded_snapshot_fingerprinting_complete"] is not True:
        raise RuntimeError("Step 29.34 bounded snapshot fingerprinting is not complete")
    if len(attestations) != 12:
        raise RuntimeError("Step 29.33 source attestation row count is not 12")
    if len(train_decisions) != 4:
        raise RuntimeError("Step 29.32 oracle-certified train candidate count is not 4")

    source_rows, source_manifests = build_sources(attestations)
    source_rows = sorted(source_rows, key=lambda row: (row["registry_id"], row["source_kind"], row["path_sha256"]))
    expected_total_bytes = sum(row.get("expected_size_bytes") or 0 for row in source_rows)
    if expected_total_bytes > MAX_TOTAL_STREAM_BYTES:
        raise RuntimeError(f"estimated corpus bytes {expected_total_bytes} exceeds stream budget {MAX_TOTAL_STREAM_BYTES}")

    cache = load_cache()
    cache_rows: list[dict[str, Any]] = list(cache.values())
    force_refresh = os.environ.get("FORGEMOE_STEP29_35_REFRESH") == "1"
    budget = {"streamed_bytes": 0}
    file_rows: list[dict[str, Any]] = []
    streamed_count = 0
    reused_count = 0
    for index, source in enumerate(source_rows, start=1):
        key = source_key(source)
        cached = cache.get(key)
        if cached and not force_refresh and cached.get("ok") is True:
            row = {
                **source,
                "source_key": key,
                "schema_version": "forgeagent.public_benchmark_full_corpus_file_fingerprint.v1",
                "status": cached.get("status"),
                "ok": cached.get("ok"),
                "bytes_read": cached.get("bytes_read"),
                "content_sha256": cached.get("content_sha256"),
                "text_token_fingerprint_sha256": cached.get("text_token_fingerprint_sha256"),
                "duration_seconds": 0.0,
                "error": None,
                "content_persisted": False,
                "contains_raw_text": False,
                "contains_private_identifiers": False,
                "cache_status": "hit_reused",
            }
            reused_count += 1
        else:
            row = stream_hash_file(source, budget)
            streamed_count += 1
            if row.get("ok") is True:
                cache[key] = row
            cache_rows.append(row)
        file_rows.append(row)
        if index % 25 == 0 or index == len(source_rows):
            print(
                json.dumps(
                    {
                        "progress": "step29_35_streaming",
                        "processed": index,
                        "total": len(source_rows),
                        "streamed_bytes": budget["streamed_bytes"],
                        "streamed_count": streamed_count,
                        "reused_count": reused_count,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    save_cache(cache_rows)

    ok_file_count = sum(1 for row in file_rows if row.get("ok") is True)
    failed_rows = [row for row in file_rows if row.get("ok") is not True]
    bytes_hashed = sum(int(row.get("bytes_read") or 0) for row in file_rows)
    overlap_rows = build_overlap_rows(file_rows, task_results, train_decisions)
    exact_collision_count = sum(row["exact_hash_collision_count"] for row in overlap_rows)
    registry_complete_count = 0
    for registry_id in {row["registry_id"] for row in source_rows}:
        expected = [row for row in source_rows if row["registry_id"] == registry_id]
        observed_ok = [row for row in file_rows if row["registry_id"] == registry_id and row.get("ok") is True]
        if len(expected) == len(observed_ok):
            registry_complete_count += 1

    full_scan_complete = ok_file_count == len(source_rows) and not failed_rows
    source_kind_counts = Counter(row["source_kind"] for row in source_rows)
    budget_report = {
        "schema_version": "forgeagent.full_public_benchmark_corpus_streaming_budget_report.v1",
        "max_total_stream_bytes": MAX_TOTAL_STREAM_BYTES,
        "expected_total_bytes": expected_total_bytes,
        "observed_total_bytes_hashed": bytes_hashed,
        "fresh_streamed_bytes": budget["streamed_bytes"],
        "source_file_count": len(source_rows),
        "ok_file_count": ok_file_count,
        "failed_file_count": len(failed_rows),
        "fresh_streamed_file_count": streamed_count,
        "reused_cached_file_count": reused_count,
        "budget_exceeded": bytes_hashed > MAX_TOTAL_STREAM_BYTES,
        "content_persisted": False,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }

    updated_release_policy = {
        "schema_version": "forgeagent.step29_35_training_release_policy_delta.v1",
        "source_step": "step29_34_bounded_public_benchmark_snapshot_fingerprinting_v1",
        "requirements": [
            {"requirement": "hardened_executable_tasks_verified", "passed": True},
            {"requirement": "train_split_oracle_certified", "passed": True},
            {"requirement": "official_public_benchmark_metadata_attested", "passed": True},
            {"requirement": "license_policy_upgraded_beyond_scaffold_only", "passed": True},
            {"requirement": "bounded_public_benchmark_snapshot_fingerprinting_complete", "passed": True},
            {"requirement": "full_public_benchmark_corpus_scan_complete", "passed": full_scan_complete},
            {"requirement": "no_exact_full_public_benchmark_corpus_collision", "passed": exact_collision_count == 0},
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
        "schema_version": "forgeagent.full_public_benchmark_corpus_materialization_gate_decision.v1",
        "gate_name": "full_public_benchmark_corpus_materialization_scan_v1",
        "source_step": "step29_34_bounded_public_benchmark_snapshot_fingerprinting_v1",
        "source_step_ready": True,
        "full_public_benchmark_corpus_scan_complete": full_scan_complete,
        "benchmark_registry_entry_count": len(attestations),
        "benchmark_complete_scan_count": registry_complete_count,
        "source_file_count": len(source_rows),
        "ok_file_count": ok_file_count,
        "failed_file_count": len(failed_rows),
        "fresh_streamed_file_count": streamed_count,
        "reused_cached_file_count": reused_count,
        "expected_total_bytes": expected_total_bytes,
        "observed_total_bytes_hashed": bytes_hashed,
        "fresh_streamed_bytes": budget["streamed_bytes"],
        "content_bytes_persisted": 0,
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "exact_full_public_benchmark_corpus_collision_count": exact_collision_count,
        "training_grade_candidate_after_step29_35_count": 0,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "resolved_previous_blockers": ["full_public_benchmark_corpus_scan_incomplete"] if full_scan_complete else [],
        "blocked_reasons": ["training_payload_materialization_not_authorized"],
        "next_recommended_step": "step29_36_training_payload_materialization_authorization_v1",
    }

    public_report = {
        "schema_version": "forgeagent.public_safe_full_public_benchmark_corpus_materialization_report.v1",
        "report_name": "full_public_benchmark_corpus_materialization_scan_v1_public_safe",
        "full_public_benchmark_corpus_scan_complete": full_scan_complete,
        "benchmark_registry_entry_count": len(attestations),
        "benchmark_complete_scan_count": registry_complete_count,
        "source_file_count": len(source_rows),
        "ok_file_count": ok_file_count,
        "failed_file_count": len(failed_rows),
        "fresh_streamed_file_count": streamed_count,
        "reused_cached_file_count": reused_count,
        "expected_total_bytes": expected_total_bytes,
        "observed_total_bytes_hashed": bytes_hashed,
        "fresh_streamed_bytes": budget["streamed_bytes"],
        "content_bytes_persisted": 0,
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "exact_full_public_benchmark_corpus_collision_count": exact_collision_count,
        "training_grade_candidate_after_step29_35_count": 0,
        "updated_release_policy_passed_requirement_count": updated_release_policy["passed_requirement_count"],
        "updated_release_policy_failed_requirement_count": updated_release_policy["failed_requirement_count"],
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "raw_benchmark_tasks_included": False,
        "raw_task_ids_included": False,
        "raw_rows_included": False,
        "raw_text_included": False,
        "content_hashes_included": False,
        "path_values_included": False,
        "patch_content_included": False,
        "hidden_test_content_included": False,
        "private_identifier_values_included": False,
        "model_outputs_included": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": bytes_hashed > 1_000_000_000,
        "gpu_required": False,
        "next_recommended_step": gate_decision["next_recommended_step"],
    }

    paths = {
        "source_manifest": OUT_DIR / "public_benchmark_full_corpus_source_manifest.jsonl",
        "file_fingerprints": OUT_DIR / "public_benchmark_full_corpus_file_fingerprints.jsonl",
        "overlap_results": OUT_DIR / "full_corpus_train_candidate_contamination_results.jsonl",
        "budget_report": OUT_DIR / "full_corpus_streaming_budget_report.json",
        "updated_release_policy": OUT_DIR / "step29_35_training_release_policy_delta.json",
        "gate_decision": OUT_DIR / "full_public_benchmark_corpus_materialization_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_full_public_benchmark_corpus_materialization_report.json",
    }
    write_jsonl(paths["source_manifest"], source_manifests)
    write_jsonl(paths["file_fingerprints"], file_rows)
    write_jsonl(paths["overlap_results"], overlap_rows)
    write_json(paths["budget_report"], budget_report)
    write_json(paths["updated_release_policy"], updated_release_policy)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]])
    privacy_path = OUT_DIR / "full_public_benchmark_corpus_materialization_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        "schema_version": "forgeagent.full_public_benchmark_corpus_materialization_summary.v1",
        "gate_name": "full_public_benchmark_corpus_materialization_scan_v1",
        "git_commit": git_commit(),
        "source_step": "step29_34_bounded_public_benchmark_snapshot_fingerprinting_v1",
        "source_step_ready": True,
        "benchmark_registry_entry_count": len(attestations),
        "benchmark_complete_scan_count": registry_complete_count,
        "source_file_count": len(source_rows),
        "ok_file_count": ok_file_count,
        "failed_file_count": len(failed_rows),
        "fresh_streamed_file_count": streamed_count,
        "reused_cached_file_count": reused_count,
        "expected_total_bytes": expected_total_bytes,
        "observed_total_bytes_hashed": bytes_hashed,
        "fresh_streamed_bytes": budget["streamed_bytes"],
        "content_bytes_persisted": 0,
        "full_public_benchmark_corpus_scan_complete": full_scan_complete,
        "exact_full_public_benchmark_corpus_collision_count": exact_collision_count,
        "training_payload_materialization_authorized": False,
        "training_grade_candidate_after_step29_35_count": 0,
        "updated_release_policy_passed_requirement_count": updated_release_policy["passed_requirement_count"],
        "updated_release_policy_failed_requirement_count": updated_release_policy["failed_requirement_count"],
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "privacy_scan_passed": privacy_report["passed"],
        "public_safe_report_ready": True,
        "downloads_large_dataset": bytes_hashed > 1_000_000_000,
        "gpu_required": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "next_recommended_step": gate_decision["next_recommended_step"],
        "artifacts": {key: rel(path) for key, path in {**paths, "privacy_report": privacy_path}.items()},
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print("FULL_PUBLIC_BENCHMARK_CORPUS_MATERIALIZATION_SCAN_V1_OK")


if __name__ == "__main__":
    main()

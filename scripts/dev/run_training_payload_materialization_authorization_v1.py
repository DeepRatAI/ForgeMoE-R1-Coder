from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_31_DIR = PROJECT_ROOT / "results/local/hardened_executable_task_generator_v1"
STEP29_32_DIR = PROJECT_ROOT / "results/local/hardened_oracle_quality_data_release_integration_v1"
STEP29_33_DIR = PROJECT_ROOT / "results/local/public_benchmark_corpus_scan_license_attestation_v1"
STEP29_35_DIR = PROJECT_ROOT / "results/local/full_public_benchmark_corpus_materialization_scan_v1"
OUT_DIR = PROJECT_ROOT / "results/local/training_payload_materialization_authorization_v1"
RUN_DIR = PROJECT_ROOT / "tmp/training_payload_materialization_authorization_v1_runs"

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
    "hidden_tests",
    "golden.patch",
    "rejected.patch",
    "public_overfit.patch",
    "wrong_file.patch",
    "semantic_noop.patch",
    "target_patch",
    "repo_files",
    "messages",
    "content_sha256",
    '"raw_text_included": true',
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


def run_command(command: list[str], cwd: Path, timeout_seconds: int = 30) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_seconds": round(time.time() - started, 6),
            "timed_out": False,
            "passed": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "elapsed_seconds": round(time.time() - started, 6),
            "timed_out": True,
            "passed": False,
        }


def ensure_passed(result: dict[str, Any], context: str) -> None:
    if result["passed"]:
        return
    raise RuntimeError(
        f"{context} failed with exit code {result['exit_code']}\n"
        f"command: {' '.join(result['command'])}\n"
        f"cwd: {result['cwd']}\n"
        f"stdout:\n{result.get('stdout') or ''}\n"
        f"stderr:\n{result.get('stderr') or ''}"
    )


def compact_command_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": result["command"],
        "exit_code": result["exit_code"],
        "passed": result["passed"],
        "timed_out": result["timed_out"],
        "stdout_sha256": sha256_text(result.get("stdout", "")),
        "stderr_sha256": sha256_text(result.get("stderr", "")),
    }


def init_git_repo(work_dir: Path) -> None:
    ensure_passed(run_command(["git", "init", "-q"], cwd=work_dir), "git init")
    ensure_passed(
        run_command(["git", "config", "user.email", "forge@example.invalid"], cwd=work_dir),
        "git config user.email",
    )
    ensure_passed(
        run_command(["git", "config", "user.name", "Forge Training Payload Verifier"], cwd=work_dir),
        "git config user.name",
    )
    ensure_passed(run_command(["git", "add", "."], cwd=work_dir), "git add baseline")
    ensure_passed(run_command(["git", "commit", "-q", "-m", "baseline"], cwd=work_dir), "git commit baseline")


def changed_files_from_patch(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        parts = line.split()
        if len(parts) >= 4 and parts[3].startswith("b/"):
            files.append(parts[3][2:])
    return files


def load_instruction_map() -> dict[str, str]:
    module_path = PROJECT_ROOT / "scripts/dev/run_hardened_executable_task_generator_v1.py"
    spec = importlib.util.spec_from_file_location("forge_step29_31_generator", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Step 29.31 generator module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {task.task_id: task.instruction for task in module.task_definitions()}


def text_files_under(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8")
        rows.append(
            {
                "path": rel_path,
                "content": text,
                "content_sha256": sha256_text(text),
            }
        )
    return rows


def build_prompt(*, instruction: str, repo_files: list[dict[str, str]], public_tests: list[dict[str, str]]) -> str:
    sections = [
        "You are an autonomous software engineering agent.",
        "Fix the repository by returning a valid git diff patch only.",
        f"Task: {instruction}",
        "The public tests below currently fail. Produce the minimal correct patch that makes them pass while preserving general behavior.",
        "",
        "Repository files:",
    ]
    for file_row in repo_files:
        sections.extend(
            [
                f"--- FILE: {file_row['path']} ---",
                file_row["content"].rstrip(),
            ]
        )
    sections.append("")
    sections.append("Public tests:")
    for test_row in public_tests:
        sections.extend(
            [
                f"--- TEST: {test_row['path']} ---",
                test_row["content"].rstrip(),
            ]
        )
    sections.extend(
        [
            "",
            "Validation command: python3 -B -m unittest discover -s tests",
            "Return only a git diff patch.",
        ]
    )
    return "\n".join(sections).rstrip() + "\n"


def validate_payload_task(task_dir: Path, payload_row: dict[str, Any], expected_patch_files: list[str]) -> dict[str, Any]:
    task_id = payload_row["task_id"]
    work_dir = RUN_DIR / task_id
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(task_dir / "repo_before", work_dir)
    init_git_repo(work_dir)

    pre_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
    patch_path = work_dir / "_target.patch"
    patch_path.write_text(payload_row["target_patch"], encoding="utf-8")
    patch_check = run_command(["git", "apply", "--check", patch_path.name], cwd=work_dir)
    if patch_check["passed"]:
        patch_apply = run_command(["git", "apply", patch_path.name], cwd=work_dir)
    else:
        patch_apply = {
            "command": ["git", "apply", patch_path.name],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "git apply --check failed; apply skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }
    if patch_apply["passed"]:
        changed = run_command(["git", "diff", "--name-only"], cwd=work_dir)
        post_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
        shutil.copy2(task_dir / "hidden_tests/test_hidden.py", work_dir / "tests/test_hidden.py")
        post_hidden = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
    else:
        changed = {
            "command": ["git", "diff", "--name-only"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; changed-file listing skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }
        post_public = {
            "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; public post-test skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }
        post_hidden = {
            "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; hidden post-test skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }

    changed_files = [line for line in changed.get("stdout", "").splitlines() if line.strip()]
    patch_files = changed_files_from_patch(payload_row["target_patch"])
    edit_scope_passed = changed_files == expected_patch_files and patch_files == expected_patch_files
    payload_valid = (
        not pre_public["passed"]
        and patch_check["passed"]
        and patch_apply["passed"]
        and post_public["passed"]
        and post_hidden["passed"]
        and edit_scope_passed
    )
    return {
        "schema_version": "forgeagent.training_payload_validation_result.v1",
        "task_id_sha256": payload_row["task_id_sha256"],
        "payload_id_sha256": payload_row["payload_id_sha256"],
        "task_id": task_id,
        "pre_public_failed_as_expected": not pre_public["passed"],
        "git_apply_check_passed": patch_check["passed"],
        "patch_applied": patch_apply["passed"],
        "post_public_passed": post_public["passed"],
        "post_hidden_passed": post_hidden["passed"],
        "changed_files": changed_files,
        "patch_files": patch_files,
        "expected_patch_files": expected_patch_files,
        "edit_scope_passed": edit_scope_passed,
        "payload_valid": payload_valid,
        "pre_public": compact_command_result(pre_public),
        "patch_check": compact_command_result(patch_check),
        "post_public": compact_command_result(post_public),
        "post_hidden": compact_command_result(post_hidden),
        "contains_raw_text": False,
        "contains_private_identifiers": False,
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
        "schema_version": "forgeagent.training_payload_materialization_privacy_report.v1",
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
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    step31_summary = read_json(STEP29_31_DIR / "summary.json")
    step32_summary = read_json(STEP29_32_DIR / "summary.json")
    step33_summary = read_json(STEP29_33_DIR / "summary.json")
    license_attestation = read_json(STEP29_33_DIR / "forge_internal_train_candidate_license_attestation.json")
    step35_summary = read_json(STEP29_35_DIR / "summary.json")
    step35_gate = read_json(STEP29_35_DIR / "full_public_benchmark_corpus_materialization_gate_decision.json")
    step35_overlaps = read_jsonl(STEP29_35_DIR / "full_corpus_train_candidate_contamination_results.jsonl")
    tasks = read_jsonl(STEP29_31_DIR / "task_results.jsonl")
    release_decisions_v1 = read_jsonl(STEP29_32_DIR / "hardened_data_release_decisions.jsonl")

    if step31_summary["verified_task_count"] != 12:
        raise RuntimeError("Step 29.31 verified task count is not 12")
    if step32_summary["oracle_certified_train_candidate_count"] != 4:
        raise RuntimeError("Step 29.32 oracle-certified train candidate count is not 4")
    if step33_summary["license_policy_upgraded_beyond_scaffold_only"] is not True:
        raise RuntimeError("Step 29.33 license policy is not upgraded")
    if license_attestation["license_basis"] != "forge_internal_generated_synthetic_tasks":
        raise RuntimeError("Step 29.33 license basis is not Forge-internal synthetic tasks")
    if license_attestation["uses_raw_public_benchmark_content"] is not False:
        raise RuntimeError("Forge train candidates unexpectedly use raw public benchmark content")
    if license_attestation["uses_private_heldout_content"] is not False:
        raise RuntimeError("Forge train candidates unexpectedly use private heldout content")
    if step35_summary["full_public_benchmark_corpus_scan_complete"] is not True:
        raise RuntimeError("Step 29.35 full public benchmark corpus scan is not complete")
    if step35_summary["exact_full_public_benchmark_corpus_collision_count"] != 0:
        raise RuntimeError("Step 29.35 exact full-corpus public benchmark collisions are non-zero")
    if step35_gate["content_bytes_persisted"] != 0:
        raise RuntimeError("Step 29.35 persisted public benchmark content")
    if any(row.get("exact_hash_collision") for row in step35_overlaps):
        raise RuntimeError("Step 29.35 overlap rows contain exact collisions")

    instruction_map = load_instruction_map()
    release_by_hash = {row["task_id_sha256"]: row for row in release_decisions_v1}
    public_hashes = {
        value
        for row in read_jsonl(STEP29_35_DIR / "public_benchmark_full_corpus_file_fingerprints.jsonl")
        for value in (row.get("content_sha256"), row.get("text_token_fingerprint_sha256"), row.get("source_blob_sha"))
        if isinstance(value, str)
    }

    payload_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    authorization_decisions: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    excluded_non_train_count = 0
    hidden_export_count = 0
    negative_patch_export_count = 0

    for task in sorted(tasks, key=lambda row: row["task_id"]):
        task_hash = task["task_id_sha256"]
        decision_v1 = release_by_hash[task_hash]
        train_candidate = (
            task["split"] == "train"
            and task["verified"] is True
            and decision_v1["oracle_certified_train_candidate"] is True
            and decision_v1["oracle_strength_score"] == 1.0
            and task.get("never_train_on") is False
        )
        task_dir = PROJECT_ROOT / task["task_dir"]
        blockers: list[str] = []
        if not train_candidate:
            blockers.append("not_authorized_train_candidate")
        if task["split"] != "train":
            blockers.append("not_train_split")
        if not step35_summary["full_public_benchmark_corpus_scan_complete"]:
            blockers.append("full_public_benchmark_corpus_scan_incomplete")
        if step35_summary["exact_full_public_benchmark_corpus_collision_count"] != 0:
            blockers.append("exact_full_public_benchmark_corpus_collision_present")
        if not step33_summary["license_policy_upgraded_beyond_scaffold_only"]:
            blockers.append("license_policy_not_upgraded")
        if blockers:
            excluded_non_train_count += 1 if task["split"] != "train" else 0
            authorization_decisions.append(
                {
                    "schema_version": "forgeagent.training_payload_authorization_decision.v1",
                    "task_id_sha256": task_hash,
                    "source_blueprint_id_sha256": task["source_blueprint_id_sha256"],
                    "split": task["split"],
                    "task_family": task["task_family"],
                    "oracle_certified": decision_v1["oracle_certified"],
                    "oracle_certified_train_candidate": decision_v1["oracle_certified_train_candidate"],
                    "training_payload_materialization_authorized": False,
                    "training_export_allowed": False,
                    "release_class": "never_train_reference" if task["split"] != "train" else "train_candidate_blocked",
                    "blocked_reasons": sorted(set(blockers)),
                    "contains_raw_text": False,
                    "contains_private_identifiers": False,
                }
            )
            continue

        spec = read_json(task_dir / "task_spec.json")
        instruction = instruction_map[task["task_id"]]
        if sha256_text(instruction) != spec["instruction_sha256"]:
            raise RuntimeError(f"instruction hash mismatch for {task['task_id']}")
        repo_files = [row for row in text_files_under(task_dir / "repo_before") if not row["path"].startswith("tests/")]
        public_tests = text_files_under(task_dir / "repo_before/tests")
        target_patch = (task_dir / "golden.patch").read_text(encoding="utf-8")
        hidden_text = (task_dir / "hidden_tests/test_hidden.py").read_text(encoding="utf-8")
        negative_texts = [
            (task_dir / name).read_text(encoding="utf-8")
            for name in ("rejected.patch", "public_overfit.patch", "wrong_file.patch", "semantic_noop.patch")
        ]
        prompt = build_prompt(instruction=instruction, repo_files=repo_files, public_tests=public_tests)
        payload_id = sha256_json(
            {
                "task_id_sha256": task_hash,
                "repo_snapshot_sha256": task["repo_snapshot_sha256"],
                "target_patch_sha256": sha256_text(target_patch),
                "prompt_sha256": sha256_text(prompt),
            }
        )
        row = {
            "schema_version": "forgeagent.patch_sft_training_payload_row.v1",
            "payload_id_sha256": payload_id,
            "task_id": task["task_id"],
            "task_id_sha256": task_hash,
            "source_blueprint_id_sha256": task["source_blueprint_id_sha256"],
            "split": "train",
            "task_family": task["task_family"],
            "difficulty_label": task["difficulty_label"],
            "behavioral_axes": task["behavioral_axes"],
            "instruction": instruction,
            "repo_snapshot_sha256": task["repo_snapshot_sha256"],
            "repo_files": repo_files,
            "public_tests": public_tests,
            "validation_command": "python3 -B -m unittest discover -s tests",
            "target_patch": target_patch,
            "target_patch_sha256": sha256_text(target_patch),
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": target_patch},
            ],
            "license_basis": license_attestation["license_basis"],
            "public_benchmark_contamination_checked": True,
            "hidden_tests_exported": False,
            "negative_patches_exported": False,
            "eval_private_or_public_eval_exported": False,
            "training_export_allowed": True,
            "training_grade": True,
            "contains_private_identifiers": False,
        }
        row_blob = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if hidden_text and hidden_text in row_blob:
            hidden_export_count += 1
        if any(text and text in row_blob for text in negative_texts):
            negative_patch_export_count += 1
        if row["target_patch_sha256"] in public_hashes or row["payload_id_sha256"] in public_hashes:
            raise RuntimeError(f"payload hash collision with public benchmark corpus for {task['task_id']}")
        expected_patch_files = list(spec["expected_edit_scope"]["files"])
        validation = validate_payload_task(task_dir, row, expected_patch_files)
        validation_rows.append(validation)
        materialized = validation["payload_valid"] and hidden_export_count == 0 and negative_patch_export_count == 0
        payload_rows.append(row)
        manifest_rows.append(
            {
                "schema_version": "forgeagent.patch_sft_training_payload_manifest_row.v1",
                "payload_id_sha256": payload_id,
                "task_id_sha256": task_hash,
                "source_blueprint_id_sha256": task["source_blueprint_id_sha256"],
                "split": "train",
                "task_family": task["task_family"],
                "repo_snapshot_sha256": task["repo_snapshot_sha256"],
                "prompt_sha256": sha256_text(prompt),
                "target_patch_sha256": row["target_patch_sha256"],
                "payload_row_sha256": sha256_text(row_blob),
                "repo_file_count": len(repo_files),
                "public_test_file_count": len(public_tests),
                "hidden_tests_exported": False,
                "negative_patches_exported": False,
                "training_export_allowed": materialized,
                "contains_raw_text": False,
                "contains_private_identifiers": False,
            }
        )
        authorization_decisions.append(
            {
                "schema_version": "forgeagent.training_payload_authorization_decision.v1",
                "task_id_sha256": task_hash,
                "source_blueprint_id_sha256": task["source_blueprint_id_sha256"],
                "payload_id_sha256": payload_id,
                "split": "train",
                "task_family": task["task_family"],
                "oracle_certified": True,
                "oracle_certified_train_candidate": True,
                "payload_validation_passed": validation["payload_valid"],
                "training_payload_materialization_authorized": materialized,
                "training_export_allowed": materialized,
                "release_class": "training_grade_patch_sft_materialized" if materialized else "train_candidate_blocked",
                "blocked_reasons": [] if materialized else ["payload_validation_failed"],
                "contains_raw_text": False,
                "contains_private_identifiers": False,
            }
        )

    payload_valid_count = sum(1 for row in validation_rows if row["payload_valid"])
    authorized_count = sum(1 for row in authorization_decisions if row["training_payload_materialization_authorized"])
    materialized_count = len(payload_rows)
    split_counts = Counter(row["split"] for row in authorization_decisions)
    release_class_counts = Counter(row["release_class"] for row in authorization_decisions)
    blocked_reason_counts = Counter(reason for row in authorization_decisions for reason in row["blocked_reasons"])
    training_grade_allowed = (
        authorized_count == 4
        and materialized_count == 4
        and payload_valid_count == 4
        and excluded_non_train_count == 8
        and hidden_export_count == 0
        and negative_patch_export_count == 0
    )

    split_report = {
        "schema_version": "forgeagent.training_payload_split_isolation_report.v1",
        "source_task_count": len(tasks),
        "source_split_counts": dict(sorted(Counter(row["split"] for row in tasks).items())),
        "materialized_training_payload_row_count": materialized_count,
        "materialized_split_counts": {"train": materialized_count},
        "excluded_non_train_task_count": excluded_non_train_count,
        "eval_rows_materialized": 0,
        "private_heldout_rows_materialized": 0,
        "public_eval_rows_materialized": 0,
        "non_train_rows_materialized": 0,
        "private_heldout_leakage_to_training_payload": False,
        "public_eval_leakage_to_training_payload": False,
        "eval_leakage_to_training_payload": False,
        "passed": excluded_non_train_count == 8 and materialized_count == 4,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }
    release_policy = {
        "schema_version": "forgeagent.training_payload_release_policy_v2.v1",
        "policy_name": "training_payload_materialization_authorization_v1",
        "source_step": "step29_35_full_public_benchmark_corpus_materialization_scan_v1",
        "requirements": [
            {"requirement": "hardened_executable_tasks_verified", "passed": step31_summary["verified_task_count"] == 12},
            {"requirement": "train_split_oracle_certified", "passed": step32_summary["oracle_certified_train_candidate_count"] == 4},
            {"requirement": "train_split_isolated_from_eval_private_public_eval", "passed": split_report["passed"]},
            {"requirement": "license_policy_upgraded_beyond_scaffold_only", "passed": step33_summary["license_policy_upgraded_beyond_scaffold_only"] is True},
            {"requirement": "forge_internal_generated_synthetic_task_license_basis", "passed": license_attestation["license_basis"] == "forge_internal_generated_synthetic_tasks"},
            {"requirement": "full_public_benchmark_corpus_scan_complete", "passed": step35_summary["full_public_benchmark_corpus_scan_complete"] is True},
            {"requirement": "no_exact_full_public_benchmark_corpus_collision", "passed": step35_summary["exact_full_public_benchmark_corpus_collision_count"] == 0},
            {"requirement": "payload_rows_materialized", "passed": materialized_count == 4},
            {"requirement": "payload_validation_passed", "passed": payload_valid_count == 4},
            {"requirement": "hidden_tests_excluded_from_training_payload", "passed": hidden_export_count == 0},
            {"requirement": "negative_patches_excluded_from_training_payload", "passed": negative_patch_export_count == 0},
            {"requirement": "training_payload_materialization_authorized", "passed": authorized_count == 4},
        ],
        "authorized_release_classes": ["training_grade_patch_sft_materialized"],
        "training_grade_data_release_allowed": training_grade_allowed,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }
    release_policy["passed_requirement_count"] = sum(1 for item in release_policy["requirements"] if item["passed"])
    release_policy["failed_requirement_count"] = sum(1 for item in release_policy["requirements"] if not item["passed"])

    gate_decision = {
        "schema_version": "forgeagent.training_payload_materialization_gate_decision.v1",
        "gate_name": "training_payload_materialization_authorization_v1",
        "source_step": "step29_35_full_public_benchmark_corpus_materialization_scan_v1",
        "source_step_ready": True,
        "authorized_train_candidate_count": authorized_count,
        "materialized_training_payload_row_count": materialized_count,
        "excluded_non_train_task_count": excluded_non_train_count,
        "payload_validation_pass_count": payload_valid_count,
        "payload_hidden_test_export_count": hidden_export_count,
        "payload_negative_patch_export_count": negative_patch_export_count,
        "training_payload_materialization_authorized": authorized_count == 4,
        "training_grade_data_release_allowed": training_grade_allowed,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "resolved_previous_blockers": ["training_payload_materialization_not_authorized"] if training_grade_allowed else [],
        "blocked_reasons": [] if training_grade_allowed else sorted(blocked_reason_counts),
        "next_recommended_step": "step29_37_training_payload_schema_quality_and_tokenization_gate_v1",
    }
    public_report = {
        "schema_version": "forgeagent.public_safe_training_payload_materialization_report.v1",
        "report_name": "training_payload_materialization_authorization_v1_public_safe",
        "authorized_train_candidate_count": authorized_count,
        "materialized_training_payload_row_count": materialized_count,
        "excluded_non_train_task_count": excluded_non_train_count,
        "payload_validation_pass_count": payload_valid_count,
        "payload_hidden_test_export_count": hidden_export_count,
        "payload_negative_patch_export_count": negative_patch_export_count,
        "release_policy_passed_requirement_count": release_policy["passed_requirement_count"],
        "release_policy_failed_requirement_count": release_policy["failed_requirement_count"],
        "training_payload_materialization_authorized": authorized_count == 4,
        "training_grade_data_release_allowed": training_grade_allowed,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "raw_task_ids_included": False,
        "raw_rows_included": False,
        "raw_text_included": False,
        "repo_content_included": False,
        "patch_content_included": False,
        "hidden_test_content_included": False,
        "negative_patch_content_included": False,
        "private_identifier_values_included": False,
        "model_outputs_included": False,
        "next_recommended_step": gate_decision["next_recommended_step"],
    }

    paths = {
        "authorization_decisions": OUT_DIR / "training_payload_authorization_decisions.jsonl",
        "validation_results": OUT_DIR / "payload_validation_results.jsonl",
        "split_isolation_report": OUT_DIR / "payload_split_isolation_report.json",
        "release_policy": OUT_DIR / "training_release_policy_v2.json",
        "gate_decision": OUT_DIR / "training_payload_materialization_gate_decision.json",
        "public_safe_report": OUT_DIR / "public_safe_training_payload_materialization_report.json",
        "payload": OUT_DIR / "dataset_exports/patch_sft_training_payload.jsonl",
        "payload_manifest": OUT_DIR / "dataset_exports/patch_sft_training_payload_manifest.jsonl",
    }
    write_jsonl(paths["authorization_decisions"], authorization_decisions)
    write_jsonl(paths["validation_results"], validation_rows)
    write_json(paths["split_isolation_report"], split_report)
    write_json(paths["release_policy"], release_policy)
    write_json(paths["gate_decision"], gate_decision)
    write_json(paths["public_safe_report"], public_report)
    write_jsonl(paths["payload"], payload_rows)
    write_jsonl(paths["payload_manifest"], manifest_rows)

    privacy_report = scan_outputs(list(paths.values()), [paths["public_safe_report"]])
    privacy_path = OUT_DIR / "training_payload_materialization_privacy_report.json"
    write_json(privacy_path, privacy_report)

    summary = {
        "schema_version": "forgeagent.training_payload_materialization_authorization_summary.v1",
        "gate_name": "training_payload_materialization_authorization_v1",
        "git_commit": git_commit(),
        "source_step": "step29_35_full_public_benchmark_corpus_materialization_scan_v1",
        "source_step_ready": True,
        "source_task_count": len(tasks),
        "oracle_certified_train_candidate_count": step32_summary["oracle_certified_train_candidate_count"],
        "authorized_train_candidate_count": authorized_count,
        "materialized_training_payload_row_count": materialized_count,
        "excluded_non_train_task_count": excluded_non_train_count,
        "payload_validation_pass_count": payload_valid_count,
        "payload_hidden_test_export_count": hidden_export_count,
        "payload_negative_patch_export_count": negative_patch_export_count,
        "payload_public_benchmark_exact_collision_count": 0,
        "split_counts": dict(sorted(split_counts.items())),
        "release_class_counts": dict(sorted(release_class_counts.items())),
        "blocked_reason_counts": dict(sorted(blocked_reason_counts.items())),
        "release_policy_passed_requirement_count": release_policy["passed_requirement_count"],
        "release_policy_failed_requirement_count": release_policy["failed_requirement_count"],
        "training_payload_materialization_authorized": authorized_count == 4,
        "training_grade_data_release_allowed": training_grade_allowed,
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
    print("TRAINING_PAYLOAD_MATERIALIZATION_AUTHORIZATION_V1_OK")


if __name__ == "__main__":
    main()

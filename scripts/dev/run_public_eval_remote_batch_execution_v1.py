from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
from typing import Any

from run_model_candidate_eval_contract_v1 import (
    build_contract,
    scan_text_for_secrets,
    validate_candidate_package,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_22_DIR = PROJECT_ROOT / "results/local/public_eval_remote_batch_adapter_v1"
PUBLIC_SUITE_DIR = PROJECT_ROOT / "results/local/public_eval_suite_scaleout_v1"
CONTRACT_DIR = PROJECT_ROOT / "results/local/model_candidate_eval_contract_v1"
HELDOUT_PROTOCOL_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
OUT_DIR = PROJECT_ROOT / "results/local/public_eval_remote_batch_execution_v1"
APPROVAL_EVIDENCE_PATH = PROJECT_ROOT / "configs/eval/public_eval_remote_batch_execution_approval_v1.json"
PRICING_EVIDENCE_PATH = PROJECT_ROOT / "configs/eval/public_eval_remote_batch_pricing_evidence_v1.json"

AWS_PROFILE = os.environ.get("AWS_PROFILE", "forgemoe")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
EXECUTE_FLAG = os.environ.get("FORGEMOE_EXECUTE_PUBLIC_EVAL_REMOTE_BATCH", "0")

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\\s*[:=]"),
}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def append_jsonl(path: Path, row: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(data: object) -> str:
    return sha256_text(json.dumps(data, sort_keys=True, ensure_ascii=False))


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def run_command(command: list[str], *, cwd: Path, timeout_seconds: int = 30) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "stdout_sha256": sha256_text(completed.stdout),
        "stderr_sha256": sha256_text(completed.stderr),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "ok": completed.returncode == 0,
    }


def extract_converse_text(response: dict[str, Any]) -> str:
    content = (((response.get("output") or {}).get("message") or {}).get("content") or [])
    chunks = [item.get("text", "") for item in content if isinstance(item, dict)]
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def extract_unified_diff(text: str) -> str:
    stripped = text.strip()
    if "```" in stripped:
        lines = [line for line in stripped.splitlines() if not line.strip().startswith("```")]
        stripped = "\n".join(lines).strip()
    marker = "diff --git "
    index = stripped.find(marker)
    if index < 0:
        return ""
    return stripped[index:].strip() + "\n"


def load_approval(default_approval: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if APPROVAL_EVIDENCE_PATH.exists():
        return read_json(APPROVAL_EVIDENCE_PATH), str(APPROVAL_EVIDENCE_PATH)
    return default_approval, str(STEP29_22_DIR / "public_eval_remote_batch_approval_record.json")


def load_pricing() -> dict[str, Any] | None:
    if PRICING_EVIDENCE_PATH.exists():
        return read_json(PRICING_EVIDENCE_PATH)
    return None


def validate_authorization(
    *,
    manifest: dict[str, Any],
    cost_policy: dict[str, Any],
    approval: dict[str, Any],
    pricing: dict[str, Any] | None,
    approval_source: str,
) -> dict[str, Any]:
    request_hashes = manifest["request_hashes"]
    approved_hashes = approval.get("approved_request_sha256_values") or []
    checks: dict[str, Any] = {
        "schema_version": "forgeagent.public_eval_remote_batch_execution_authorization_check.v1",
        "execute_flag_set": EXECUTE_FLAG == "1",
        "approval_record_approved": approval.get("approved") is True,
        "approved_model_matches": approval.get("approved_model_id") == manifest["selected_model_id"],
        "approved_batch_hash_matches": approval.get("approved_batch_request_sha256")
        == manifest["batch_request_sha256"],
        "approved_request_hashes_match": sorted(approved_hashes) == sorted(request_hashes),
        "approved_call_count_positive": int(approval.get("approved_max_remote_inference_calls") or 0)
        >= manifest["request_count"],
        "approved_call_count_within_policy": int(approval.get("approved_max_remote_inference_calls") or 0)
        <= int(cost_policy["max_remote_inference_calls"]),
        "approved_cost_positive": isinstance(approval.get("approved_max_total_usd"), int | float)
        and float(approval["approved_max_total_usd"]) > 0,
        "pricing_evidence_present": pricing is not None,
        "pricing_model_matches": pricing is not None
        and pricing.get("model_id") == manifest["selected_model_id"],
        "pricing_batch_hash_matches": pricing is not None
        and pricing.get("batch_request_sha256") == manifest["batch_request_sha256"],
        "pricing_region_matches": pricing is not None and pricing.get("region") == AWS_REGION,
        "pricing_source_recorded": pricing is not None and bool(pricing.get("official_pricing_source")),
        "pricing_cost_within_approval": False,
        "token_ceiling_within_policy": int(manifest["estimated_total_token_ceiling"])
        <= int(cost_policy["estimated_total_token_ceiling"]),
        "request_count_within_policy": int(manifest["request_count"])
        <= int(cost_policy["max_remote_inference_calls"]),
    }
    if pricing is not None and isinstance(approval.get("approved_max_total_usd"), int | float):
        estimated_total_usd = pricing.get("estimated_total_usd")
        checks["pricing_cost_within_approval"] = isinstance(estimated_total_usd, int | float) and float(
            estimated_total_usd
        ) <= float(approval["approved_max_total_usd"])

    required = [
        "execute_flag_set",
        "approval_record_approved",
        "approved_model_matches",
        "approved_batch_hash_matches",
        "approved_request_hashes_match",
        "approved_call_count_positive",
        "approved_call_count_within_policy",
        "approved_cost_positive",
        "pricing_evidence_present",
        "pricing_model_matches",
        "pricing_batch_hash_matches",
        "pricing_region_matches",
        "pricing_source_recorded",
        "pricing_cost_within_approval",
        "token_ceiling_within_policy",
        "request_count_within_policy",
    ]
    failed = [name for name in required if checks[name] is not True]
    checks["execution_authorized"] = not failed
    checks["failed_checks"] = failed
    checks["approval_source"] = approval_source
    checks["pricing_evidence_source"] = str(PRICING_EVIDENCE_PATH) if pricing is not None else None
    checks["remote_inference_invoked"] = False
    checks["local_model_execution_used"] = False
    return checks


def invoke_bedrock_converse(request_path: Path, response_path: Path) -> dict[str, Any]:
    command = [
        "aws",
        "--profile",
        AWS_PROFILE,
        "--region",
        AWS_REGION,
        "bedrock-runtime",
        "converse",
        "--cli-input-json",
        f"file://{request_path}",
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    status = {
        "command": command,
        "returncode": completed.returncode,
        "stdout_sha256": sha256_text(completed.stdout),
        "stderr_sha256": sha256_text(completed.stderr),
        "remote_inference_invoked": True,
        "response_json_parse_ok": False,
        "usage": {},
        "metrics": {},
    }
    if completed.returncode == 0:
        response = json.loads(completed.stdout)
        status["response_json_parse_ok"] = True
        status["usage"] = response.get("usage") or {}
        status["metrics"] = response.get("metrics") or {}
        write_json(response_path, response)
    else:
        write_text(response_path.with_suffix(".stderr.txt"), completed.stderr)
    return status


def prepare_git_repo(source_repo: Path, destination_repo: Path) -> None:
    if destination_repo.exists():
        shutil.rmtree(destination_repo)
    shutil.copytree(source_repo, destination_repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    for command in [
        ["git", "init", "-q"],
        ["git", "config", "user.email", "forge@example.invalid"],
        ["git", "config", "user.name", "ForgeMoE Eval"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", "baseline"],
    ]:
        result = run_command(command, cwd=destination_repo, timeout_seconds=30)
        if not result["ok"]:
            raise RuntimeError(f"failed to prepare git repo: {command}: {result['stderr']}")


def changed_files_from_patch(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        parts = line.split()
        if len(parts) >= 4 and parts[3].startswith("b/"):
            files.append(parts[3][2:])
    return files


def validate_patch(
    *,
    task_id: str,
    diff_text: str,
    source_repo: Path,
    task_dir: Path,
    test_command: str,
) -> dict[str, Any]:
    eval_repo = OUT_DIR / "patch_eval_workspaces" / task_id / "repo"
    prepare_git_repo(source_repo, eval_repo)
    patch_path = OUT_DIR / "candidate_patches" / f"{task_id}.patch"
    write_text(patch_path, diff_text)

    apply_check = run_command(["git", "apply", "--check", str(patch_path)], cwd=eval_repo, timeout_seconds=30)
    apply_result: dict[str, Any] | None = None
    post_public: subprocess.CompletedProcess[str] | None = None
    post_hidden: subprocess.CompletedProcess[str] | None = None
    changed_files: list[str] = []
    if apply_check["ok"]:
        apply_result = run_command(["git", "apply", str(patch_path)], cwd=eval_repo, timeout_seconds=30)
        if apply_result["ok"]:
            changed = run_command(["git", "diff", "--name-only"], cwd=eval_repo, timeout_seconds=30)
            changed_files = [line for line in changed.get("stdout", "").splitlines() if line.strip()]
            post_public = subprocess.run(
                test_command,
                cwd=eval_repo,
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
            shutil.copy2(task_dir / "hidden_tests/test_hidden.py", eval_repo / "tests/test_hidden.py")
            post_hidden = subprocess.run(
                test_command,
                cwd=eval_repo,
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )

    patch_files = changed_files_from_patch(diff_text)
    edit_scope_passed = changed_files == ["app/utils.py"] and patch_files == ["app/utils.py"]
    public_passed = post_public is not None and post_public.returncode == 0
    hidden_passed = post_hidden is not None and post_hidden.returncode == 0
    solved = apply_check["ok"] and bool(apply_result and apply_result["ok"]) and public_passed and hidden_passed
    return {
        "schema_version": "forgeagent.public_eval_remote_batch_patch_validation_result.v1",
        "task_id": task_id,
        "patch_present": True,
        "patch_sha256": sha256_text(diff_text),
        "patch_files": patch_files,
        "changed_files": changed_files,
        "edit_scope_passed": edit_scope_passed,
        "git_apply_check_passed": apply_check["ok"],
        "git_apply_passed": bool(apply_result and apply_result["ok"]),
        "post_public_executed": post_public is not None,
        "post_public_passed": public_passed,
        "post_hidden_executed": post_hidden is not None,
        "post_hidden_passed": hidden_passed,
        "solved": solved and edit_scope_passed,
    }


def build_candidate_package(
    *,
    manifest: dict[str, Any],
    heldout_summary: dict[str, Any],
    authorization: dict[str, Any],
    response_rows: list[dict[str, Any]],
    parse_rows: list[dict[str, Any]],
    patch_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    response_count = sum(1 for row in response_rows if row["remote_inference_invoked"])
    parsed_count = sum(1 for row in parse_rows if row["patch_extracted"])
    public_pass_count = sum(1 for row in patch_rows if row["post_public_passed"])
    hidden_pass_count = sum(1 for row in patch_rows if row["post_hidden_passed"])
    regression_free_count = sum(1 for row in patch_rows if row["solved"])
    public_overfit_caught = sum(
        1 for row in patch_rows if row["post_public_passed"] and not row["post_hidden_passed"]
    )
    task_count = int(manifest["public_eval_task_count"])
    return {
        "candidate_identity": {
            "candidate_id": "public-eval-remote-batch-execution-v1",
            "candidate_kind": "remote_public_eval_batch_execution",
            "created_by_step": "step29_23_public_eval_remote_batch_execution",
            "is_real_model_candidate": response_count == task_count and authorization["execution_authorized"],
        },
        "model_metadata": {
            "model_id": manifest["selected_model_id"],
            "model_size_class": "7b" if "7b" in manifest["selected_model_id"].lower() else "tiny_smoke",
            "adapter_name": "BedrockConversePublicEvalBatchExecutionAdapter",
            "runtime": "bedrock_on_demand",
            "base_or_tuned": "base",
            "revision": "remote_inventory_selected",
            "provider": manifest.get("selected_model_provider"),
        },
        "run_provenance": {
            "git_commit": git_commit(),
            "prompt_contract_version": "public_eval_batch_prompt_v1",
            "candidate_pipeline_version": "public_eval_remote_batch_execution_v1",
            "heldout_protocol_version": "heldout_aware_eval_protocol_v1",
            "public_eval_suite_version": "public_eval_suite_scaleout_v1",
            "batch_request_sha256": manifest["batch_request_sha256"],
            "execution_authorized": authorization["execution_authorized"],
        },
        "generation_config": {
            "max_new_tokens": manifest["max_output_tokens_per_task"],
            "temperature": 0.0,
            "top_p": 1.0,
            "do_sample": False,
            "num_return_sequences": 1 if response_count else 0,
            "seed": 2923,
        },
        "eval_scope": {
            "train_rows_observed": 0,
            "public_eval_task_count": task_count,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_aggregate_only": True,
            "private_heldout_task_ids_exposed": False,
            "candidate_outputs_contain_private_material": False,
            "private_heldout_evaluated": False,
            "remote_inference_executed": response_count > 0,
            "local_model_execution_used": False,
        },
        "aggregate_metrics": {
            "raw_response_count": response_count,
            "parsed_candidate_count": parsed_count,
            "parse_failure_count": max(response_count - parsed_count, 0),
            "parse_validity_rate": parsed_count / task_count,
            "public_eval_task_count": task_count,
            "public_eval_solve_rate": public_pass_count / task_count,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_pass_rate": 0.0,
            "public_overfit_detection_rate": public_overfit_caught / task_count,
            "regression_free_patch_rate": regression_free_count / task_count,
            "hidden_oracle_pass_rate": hidden_pass_count / task_count,
        },
        "privacy_attestation": {
            "private_heldout_used_for_training": False,
            "private_heldout_used_for_prompt_iteration": False,
            "private_task_ids_in_public_report": False,
            "private_patch_content_in_public_report": False,
            "private_hidden_test_content_in_public_report": False,
        },
        "cost_profile": {
            "gpu_required": False,
            "training_job_launched": False,
            "large_dataset_downloaded": False,
            "estimated_eval_cost_usd": 0.0,
            "remote_inference_invoked": response_count > 0,
            "local_model_execution_used": False,
        },
    }


def scan_outputs(
    *,
    output_paths: list[Path],
    public_report_paths: list[Path],
    private_task_ids: set[str],
) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    private_id_leaks: list[dict[str, Any]] = []
    public_report_content_leaks: list[dict[str, Any]] = []
    public_report_markers = ["diff --git", "assertEqual", "def ", "hidden_tests", "repo_before"]

    for path in output_paths:
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for finding in scan_text_for_secrets(text):
            secret_findings.append({"path": str(path), **finding})
        for pattern_name, pattern in SECRET_PATTERNS.items():
            matches = list(pattern.finditer(text))
            if matches:
                secret_findings.append({"path": str(path), "pattern": pattern_name, "count": len(matches)})
        for task_id in private_task_ids:
            if task_id in text:
                private_id_leaks.append({"path": str(path), "task_id": task_id})

    for path in public_report_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in public_report_markers:
            if marker in text:
                public_report_content_leaks.append({"path": str(path), "marker": marker})

    return {
        "schema_version": "forgeagent.public_eval_remote_batch_execution_privacy_report.v1",
        "scanned_paths": [str(path) for path in output_paths],
        "public_report_paths": [str(path) for path in public_report_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "private_task_id_leak_count": len(private_id_leaks),
        "private_task_id_leaks": private_id_leaks,
        "public_report_content_leak_count": len(public_report_content_leaks),
        "public_report_content_leaks": public_report_content_leaks,
        "passed": len(secret_findings) == 0
        and len(private_id_leaks) == 0
        and len(public_report_content_leaks) == 0,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    step22_summary = read_json(STEP29_22_DIR / "summary.json")
    manifest = read_json(STEP29_22_DIR / "public_eval_batch_request_manifest.json")
    cost_policy = read_json(STEP29_22_DIR / "public_eval_remote_batch_cost_policy.json")
    default_approval = read_json(STEP29_22_DIR / "public_eval_remote_batch_approval_record.json")
    heldout_summary = read_json(HELDOUT_PROTOCOL_DIR / "summary.json")
    contract_summary = read_json(CONTRACT_DIR / "summary.json")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if not step22_summary["request_manifest_ready"]:
        raise RuntimeError("Step 29.22 request manifest is not ready")
    if step22_summary["remote_inference_invoked"]:
        raise RuntimeError("Step 29.23 must start from a non-invoked Step 29.22 state")
    if not contract_summary["candidate_contract_ready"]:
        raise RuntimeError("model candidate eval contract is not ready")
    if not heldout_summary["protocol_ready"]:
        raise RuntimeError("heldout-aware protocol is not ready")
    if manifest["batch_request_sha256"] != step22_summary["batch_request_sha256"]:
        raise RuntimeError("batch request hash drift detected between Step 29.22 summary and manifest")
    if sha256_json(manifest["request_hashes"]) != manifest["batch_request_sha256"]:
        raise RuntimeError("batch request hash does not match request hashes")

    for row in manifest["task_requests"]:
        request_path = Path(row["request_path"])
        if sha256_json(read_json(request_path)) != row["request_sha256"]:
            raise RuntimeError(f"request hash drift detected for {row['task_id']}")

    approval, approval_source = load_approval(default_approval)
    pricing = load_pricing()
    authorization = validate_authorization(
        manifest=manifest,
        cost_policy=cost_policy,
        approval=approval,
        pricing=pricing,
        approval_source=approval_source,
    )

    approval_requirement = {
        "schema_version": "forgeagent.public_eval_remote_batch_execution_approval_requirement.v1",
        "accepted_evidence_file": str(APPROVAL_EVIDENCE_PATH),
        "required_model_id": manifest["selected_model_id"],
        "required_batch_request_sha256": manifest["batch_request_sha256"],
        "required_request_sha256_values": manifest["request_hashes"],
        "required_max_remote_inference_calls": manifest["request_count"],
        "required_region": AWS_REGION,
    }
    pricing_requirement = {
        "schema_version": "forgeagent.public_eval_remote_batch_execution_pricing_requirement.v1",
        "accepted_evidence_file": str(PRICING_EVIDENCE_PATH),
        "required_model_id": manifest["selected_model_id"],
        "required_batch_request_sha256": manifest["batch_request_sha256"],
        "required_region": AWS_REGION,
        "required_source": "official_provider_pricing_page_or_aws_pricing_api",
    }

    approval_requirement_path = OUT_DIR / "approval_evidence_requirement.json"
    pricing_requirement_path = OUT_DIR / "pricing_evidence_requirement.json"
    approval_observed_path = OUT_DIR / "approval_record_observed.json"
    authorization_path = OUT_DIR / "execution_authorization_check.json"
    write_json(approval_requirement_path, approval_requirement)
    write_json(pricing_requirement_path, pricing_requirement)
    write_json(approval_observed_path, approval)
    if pricing is not None:
        write_json(OUT_DIR / "pricing_evidence_observed.json", pricing)
    write_json(authorization_path, authorization)

    execution_plan = {
        "schema_version": "forgeagent.public_eval_remote_batch_execution_runtime_plan.v1",
        "runner_name": "public_eval_remote_batch_execution_v1",
        "selected_model_id": manifest["selected_model_id"],
        "batch_request_sha256": manifest["batch_request_sha256"],
        "request_count": manifest["request_count"],
        "execution_authorized": authorization["execution_authorized"],
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
    }
    execution_plan_path = OUT_DIR / "public_eval_remote_batch_execution_runtime_plan.json"
    write_json(execution_plan_path, execution_plan)

    response_rows: list[dict[str, Any]] = []
    parse_rows: list[dict[str, Any]] = []
    patch_rows: list[dict[str, Any]] = []
    response_status_path = OUT_DIR / "remote_response_statuses.jsonl"
    parse_result_path = OUT_DIR / "candidate_response_parse_results.jsonl"
    patch_validation_path = OUT_DIR / "patch_validation_results.jsonl"

    for row in manifest["task_requests"]:
        task_id = row["task_id"]
        request_path = Path(row["request_path"])
        response_path = OUT_DIR / "remote_responses" / f"{task_id}.json"
        if authorization["execution_authorized"]:
            response_status = invoke_bedrock_converse(request_path, response_path)
            response_text = ""
            if response_status["response_json_parse_ok"]:
                response_text = extract_converse_text(read_json(response_path))
                write_text(OUT_DIR / "remote_response_texts" / f"{task_id}.txt", response_text)
            diff_text = extract_unified_diff(response_text)
        else:
            response_status = {
                "task_id": task_id,
                "request_sha256": row["request_sha256"],
                "remote_inference_invoked": False,
                "response_json_parse_ok": False,
                "usage": {},
                "metrics": {},
                "blocked_reason": "authorization_or_pricing_gate_failed",
            }
            diff_text = ""

        response_status = {"schema_version": "forgeagent.public_eval_remote_batch_response_status.v1", **response_status}
        response_rows.append(response_status)
        append_jsonl(response_status_path, response_status)

        parse_result = {
            "schema_version": "forgeagent.public_eval_remote_batch_response_parse_result.v1",
            "task_id": task_id,
            "response_text_present": bool(diff_text),
            "patch_extracted": bool(diff_text),
            "patch_sha256": sha256_text(diff_text) if diff_text else None,
            "raw_response_in_public_report": False,
            "patch_content_in_public_report": False,
        }
        parse_rows.append(parse_result)
        append_jsonl(parse_result_path, parse_result)

        if diff_text:
            task_json = PUBLIC_SUITE_DIR / "public_eval_tasks" / task_id / "task.json"
            task = read_json(task_json)
            source_repo = task_json.parent / task["repo_dir"]
            patch_validation = validate_patch(
                task_id=task_id,
                diff_text=diff_text,
                source_repo=source_repo,
                task_dir=task_json.parent,
                test_command=task["test_command"],
            )
        else:
            patch_validation = {
                "schema_version": "forgeagent.public_eval_remote_batch_patch_validation_result.v1",
                "task_id": task_id,
                "patch_present": False,
                "patch_sha256": None,
                "patch_files": [],
                "changed_files": [],
                "edit_scope_passed": False,
                "git_apply_check_passed": False,
                "git_apply_passed": False,
                "post_public_executed": False,
                "post_public_passed": False,
                "post_hidden_executed": False,
                "post_hidden_passed": False,
                "solved": False,
            }
        patch_rows.append(patch_validation)
        append_jsonl(patch_validation_path, patch_validation)

    package = build_candidate_package(
        manifest=manifest,
        heldout_summary=heldout_summary,
        authorization=authorization,
        response_rows=response_rows,
        parse_rows=parse_rows,
        patch_rows=patch_rows,
    )
    validation = validate_candidate_package(package, build_contract(heldout_summary), private_task_ids)
    package_path = OUT_DIR / "candidate_packages/public_eval_remote_batch_execution_candidate.json"
    validation_path = OUT_DIR / "candidate_validation_result.json"
    write_json(package_path, package)
    write_json(validation_path, validation)

    remote_invoked_count = sum(1 for row in response_rows if row["remote_inference_invoked"])
    patch_extracted_count = sum(1 for row in parse_rows if row["patch_extracted"])
    public_pass_count = sum(1 for row in patch_rows if row["post_public_passed"])
    hidden_pass_count = sum(1 for row in patch_rows if row["post_hidden_passed"])
    solved_count = sum(1 for row in patch_rows if row["solved"])

    gate = {
        "schema_version": "forgeagent.public_eval_remote_batch_execution_gate_decision.v1",
        "runner_name": "public_eval_remote_batch_execution_v1",
        "source_step_ready": True,
        "request_hashes_verified": True,
        "approval_required": True,
        "pricing_evidence_required": True,
        "execution_authorized": authorization["execution_authorized"],
        "remote_inference_invoked_count": remote_invoked_count,
        "remote_inference_invoked": remote_invoked_count > 0,
        "local_model_execution_used": False,
        "patch_extracted_count": patch_extracted_count,
        "public_tests_passed_count": public_pass_count,
        "hidden_oracle_passed_count": hidden_pass_count,
        "solved_task_count": solved_count,
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_execution_blocked": None
        if authorization["execution_authorized"]
        else "explicit approval, execute flag and official pricing evidence are required",
        "reason_release_blocked": "private heldout aggregate evaluation has not run for this candidate",
    }
    gate_path = OUT_DIR / "public_eval_remote_batch_execution_gate_decision.json"
    write_json(gate_path, gate)

    public_report = {
        "schema_version": "forgeagent.public_safe_public_eval_remote_batch_execution_report.v1",
        "report_name": "public_eval_remote_batch_execution_v1_public_safe",
        "selected_model_id": manifest["selected_model_id"],
        "public_eval_task_count": manifest["public_eval_task_count"],
        "batch_request_sha256": manifest["batch_request_sha256"],
        "execution_authorized": authorization["execution_authorized"],
        "remote_inference_invoked_count": remote_invoked_count,
        "remote_inference_invoked": remote_invoked_count > 0,
        "patch_extracted_count": patch_extracted_count,
        "public_tests_passed_count": public_pass_count,
        "hidden_oracle_passed_count": hidden_pass_count,
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "prompt_content_included": False,
            "raw_response_included": False,
            "patch_content_included": False,
            "hidden_test_content_included": False,
            "private_task_ids_included": False,
        },
    }
    public_report_path = OUT_DIR / "public_safe_public_eval_remote_batch_execution_report.json"
    write_json(public_report_path, public_report)

    output_paths = [
        approval_requirement_path,
        pricing_requirement_path,
        approval_observed_path,
        authorization_path,
        execution_plan_path,
        response_status_path,
        parse_result_path,
        patch_validation_path,
        package_path,
        validation_path,
        gate_path,
        public_report_path,
    ]
    privacy = scan_outputs(
        output_paths=output_paths,
        public_report_paths=[public_report_path],
        private_task_ids=private_task_ids,
    )
    privacy_path = OUT_DIR / "public_eval_remote_batch_execution_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.public_eval_remote_batch_execution_summary.v1",
        "runner_name": "public_eval_remote_batch_execution_v1",
        "source_step": "step29_22_public_eval_remote_batch_adapter_v1",
        "source_step_ready": True,
        "selected_model_id": manifest["selected_model_id"],
        "selected_model_provider": manifest.get("selected_model_provider"),
        "public_eval_task_count": manifest["public_eval_task_count"],
        "request_count": manifest["request_count"],
        "batch_request_sha256": manifest["batch_request_sha256"],
        "request_hashes_verified": True,
        "pricing_evidence_present": authorization["pricing_evidence_present"],
        "execute_flag_set": authorization["execute_flag_set"],
        "approval_record_approved": authorization["approval_record_approved"],
        "execution_authorized": authorization["execution_authorized"],
        "remote_inference_invoked_count": remote_invoked_count,
        "remote_inference_invoked": remote_invoked_count > 0,
        "remote_response_present_count": sum(1 for row in response_rows if row["response_json_parse_ok"]),
        "patch_extracted_count": patch_extracted_count,
        "git_apply_check_passed_count": sum(1 for row in patch_rows if row["git_apply_check_passed"]),
        "public_tests_passed_count": public_pass_count,
        "hidden_oracle_passed_count": hidden_pass_count,
        "solved_task_count": solved_count,
        "candidate_package_count": 1,
        "candidate_package_valid_count": 1 if validation["contract_valid"] else 0,
        "release_gate_passed_count": 1 if validation["release_gate_passed"] else 0,
        "public_safe_report_ready": True,
        "private_task_id_leak_count": privacy["private_task_id_leak_count"],
        "public_report_content_leak_count": privacy["public_report_content_leak_count"],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_24_private_heldout_aggregate_candidate_eval_gate",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "approval_evidence_requirement": str(approval_requirement_path),
            "pricing_evidence_requirement": str(pricing_requirement_path),
            "approval_record_observed": str(approval_observed_path),
            "authorization_check": str(authorization_path),
            "runtime_plan": str(execution_plan_path),
            "response_statuses": str(response_status_path),
            "parse_results": str(parse_result_path),
            "patch_validation_results": str(patch_validation_path),
            "candidate_package": str(package_path),
            "candidate_validation_result": str(validation_path),
            "gate_decision": str(gate_path),
            "public_safe_report": str(public_report_path),
            "privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("PUBLIC_EVAL_REMOTE_BATCH_EXECUTION_V1_OK")


if __name__ == "__main__":
    main()

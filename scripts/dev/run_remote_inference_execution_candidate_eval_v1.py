from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
from typing import Any

from run_model_candidate_eval_contract_v1 import (
    build_contract,
    scan_text_for_secrets,
    validate_candidate_package,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_17_DIR = PROJECT_ROOT / "results/local/remote_code_model_candidate_smoke_eval_v1"
STEP29_18_DIR = PROJECT_ROOT / "results/local/remote_inference_cost_approval_gate_v1"
CONTRACT_DIR = PROJECT_ROOT / "results/local/model_candidate_eval_contract_v1"
HELDOUT_PROTOCOL_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
OUT_DIR = PROJECT_ROOT / "results/local/remote_inference_execution_candidate_eval_v1"
APPROVAL_EVIDENCE_PATH = PROJECT_ROOT / "configs/eval/remote_inference_execution_approval_v1.json"
PRICING_EVIDENCE_PATH = PROJECT_ROOT / "configs/eval/remote_inference_pricing_evidence_v1.json"

AWS_PROFILE = os.environ.get("AWS_PROFILE", "forgemoe")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
EXECUTE_FLAG = os.environ.get("FORGEMOE_EXECUTE_REMOTE_INFERENCE", "0")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


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


def run_command(command: list[str], *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
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
        lines = [
            line
            for line in stripped.splitlines()
            if not line.strip().startswith("```")
        ]
        stripped = "\n".join(lines).strip()
    marker = "diff --git "
    index = stripped.find(marker)
    if index < 0:
        return ""
    return stripped[index:].strip() + "\n"


def load_pricing_evidence() -> dict[str, Any] | None:
    if not PRICING_EVIDENCE_PATH.exists():
        return None
    return read_json(PRICING_EVIDENCE_PATH)


def load_approval_evidence(default_approval: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if APPROVAL_EVIDENCE_PATH.exists():
        return read_json(APPROVAL_EVIDENCE_PATH), str(APPROVAL_EVIDENCE_PATH)
    return default_approval, str(STEP29_18_DIR / "approval_record.json")


def build_approval_requirement(selected_model_id: str, request_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.remote_inference_approval_evidence_requirement.v1",
        "required": True,
        "accepted_evidence_file": str(APPROVAL_EVIDENCE_PATH),
        "fallback_observed_record": str(STEP29_18_DIR / "approval_record.json"),
        "required_model_id": selected_model_id,
        "required_request_sha256": request_sha256,
        "required_region": AWS_REGION,
        "required_fields": [
            "schema_version",
            "approval_id",
            "approved",
            "approved_model_id",
            "approved_request_sha256",
            "approved_max_total_usd",
            "approved_max_remote_inference_calls",
            "approval_timestamp",
            "approval_evidence",
        ],
    }


def build_pricing_requirement(selected_model_id: str, request_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.remote_inference_pricing_evidence_requirement.v1",
        "required": True,
        "accepted_evidence_file": str(PRICING_EVIDENCE_PATH),
        "required_model_id": selected_model_id,
        "required_request_sha256": request_sha256,
        "required_region": AWS_REGION,
        "required_source": "official_provider_pricing_page_or_aws_pricing_api",
        "required_fields": [
            "schema_version",
            "model_id",
            "request_sha256",
            "region",
            "official_pricing_source",
            "pricing_captured_at",
            "estimated_total_usd",
            "estimated_input_tokens",
            "estimated_output_tokens",
        ],
    }


def validate_approval_and_pricing(
    *,
    approval: dict[str, Any],
    policy: dict[str, Any],
    pricing: dict[str, Any] | None,
    approval_source: str,
    selected_model_id: str,
    request_sha256: str,
    token_budget: dict[str, Any],
) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "schema_version": "forgeagent.remote_inference_execution_authorization_check.v1",
        "execute_flag_set": EXECUTE_FLAG == "1",
        "approval_record_approved": approval.get("approved") is True,
        "approved_model_matches": approval.get("approved_model_id") == selected_model_id,
        "approved_request_hash_matches": approval.get("approved_request_sha256") == request_sha256,
        "approved_call_count_positive": int(approval.get("approved_max_remote_inference_calls") or 0) >= 1,
        "approved_call_count_within_policy": int(approval.get("approved_max_remote_inference_calls") or 0)
        <= int(policy.get("max_remote_inference_calls") or 0),
        "approved_cost_positive": isinstance(approval.get("approved_max_total_usd"), int | float)
        and float(approval["approved_max_total_usd"]) > 0,
        "pricing_evidence_present": pricing is not None,
        "pricing_model_matches": pricing is not None and pricing.get("model_id") == selected_model_id,
        "pricing_request_hash_matches": pricing is not None
        and pricing.get("request_sha256") == request_sha256,
        "pricing_region_matches": pricing is not None and pricing.get("region") == AWS_REGION,
        "pricing_source_recorded": pricing is not None
        and bool(pricing.get("official_pricing_source")),
        "pricing_cost_within_approval": False,
        "token_ceiling_within_policy": int(token_budget["estimated_total_token_ceiling"])
        <= int(policy["estimated_total_token_ceiling"]),
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
        "approved_request_hash_matches",
        "approved_call_count_positive",
        "approved_call_count_within_policy",
        "approved_cost_positive",
        "pricing_evidence_present",
        "pricing_model_matches",
        "pricing_request_hash_matches",
        "pricing_region_matches",
        "pricing_source_recorded",
        "pricing_cost_within_approval",
        "token_ceiling_within_policy",
    ]
    failed = [name for name in required if checks[name] is not True]
    checks["execution_authorized"] = not failed
    checks["failed_checks"] = failed
    checks["approval_source"] = approval_source
    checks["pricing_evidence_source"] = str(PRICING_EVIDENCE_PATH) if pricing is not None else None
    return checks


def invoke_bedrock_converse(request_path: Path) -> dict[str, Any]:
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
        "schema_version": "forgeagent.remote_inference_response_status.v1",
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
        write_json(OUT_DIR / "remote_inference_response.json", response)
    else:
        write_text(OUT_DIR / "remote_inference_stderr.txt", completed.stderr)
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


def validate_patch(diff_text: str, source_repo: Path, test_command: str) -> dict[str, Any]:
    patch_path = OUT_DIR / "candidate.patch"
    write_text(patch_path, diff_text)
    eval_repo = OUT_DIR / "patch_eval_workspace/repo"
    prepare_git_repo(source_repo, eval_repo)

    apply_check = run_command(["git", "apply", "--check", str(patch_path)], cwd=eval_repo, timeout_seconds=30)
    applied = False
    post_test = None
    if apply_check["ok"]:
        apply_result = run_command(["git", "apply", str(patch_path)], cwd=eval_repo, timeout_seconds=30)
        applied = apply_result["ok"]
        if applied:
            post_test = subprocess.run(
                test_command,
                cwd=eval_repo,
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )

    return {
        "schema_version": "forgeagent.remote_inference_patch_validation_result.v1",
        "patch_present": True,
        "patch_sha256": sha256_text(diff_text),
        "git_apply_check_passed": apply_check["ok"],
        "git_apply_check_exit_code": apply_check["returncode"],
        "git_apply_executed": apply_check["ok"],
        "git_apply_passed": applied,
        "public_tests_executed": post_test is not None,
        "public_tests_passed": post_test is not None and post_test.returncode == 0,
        "public_tests_exit_code": None if post_test is None else post_test.returncode,
        "public_tests_stdout_sha256": None if post_test is None else sha256_text(post_test.stdout),
        "public_tests_stderr_sha256": None if post_test is None else sha256_text(post_test.stderr),
    }


def build_candidate_package(
    *,
    step18_summary: dict[str, Any],
    heldout_summary: dict[str, Any],
    authorization: dict[str, Any],
    response_status: dict[str, Any],
    parse_result: dict[str, Any],
    patch_validation: dict[str, Any],
) -> dict[str, Any]:
    response_invoked = response_status["remote_inference_invoked"]
    parsed = parse_result["patch_extracted"]
    public_passed = patch_validation["public_tests_passed"]
    return {
        "candidate_identity": {
            "candidate_id": "remote-inference-execution-candidate-smoke-v1",
            "candidate_kind": "remote_inference_execution_smoke",
            "created_by_step": "step29_19_remote_inference_execution_candidate_eval",
            "is_real_model_candidate": response_invoked,
        },
        "model_metadata": {
            "model_id": step18_summary["selected_model_id"],
            "model_size_class": "7b" if "7b" in step18_summary["selected_model_id"].lower() else "tiny_smoke",
            "adapter_name": "BedrockConverseRemoteInferenceAdapter",
            "runtime": "bedrock_on_demand",
            "base_or_tuned": "base",
            "revision": "remote_inventory_selected",
            "provider": step18_summary["selected_model_provider"],
        },
        "run_provenance": {
            "git_commit": git_commit(),
            "prompt_contract_version": "remote_code_smoke_prompt_v1",
            "candidate_pipeline_version": "remote_inference_execution_candidate_eval_v1",
            "heldout_protocol_version": "heldout_aware_eval_protocol_v1",
            "request_sha256": step18_summary["request_sha256"],
            "execution_authorized": authorization["execution_authorized"],
        },
        "generation_config": {
            "max_new_tokens": step18_summary["max_output_tokens"],
            "temperature": 0.0,
            "top_p": 1.0,
            "do_sample": False,
            "num_return_sequences": 1 if response_invoked else 0,
            "seed": 2919,
        },
        "eval_scope": {
            "train_rows_observed": 0,
            "public_eval_task_count": 1,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_aggregate_only": True,
            "private_heldout_task_ids_exposed": False,
            "candidate_outputs_contain_private_material": False,
            "private_heldout_evaluated": False,
            "remote_inference_executed": response_invoked,
            "local_model_execution_used": False,
        },
        "aggregate_metrics": {
            "raw_response_count": 1 if response_invoked else 0,
            "parsed_candidate_count": 1 if parsed else 0,
            "parse_failure_count": 0 if parsed else 1,
            "parse_validity_rate": 1.0 if parsed else 0.0,
            "public_eval_task_count": 1,
            "public_eval_solve_rate": 1.0 if public_passed else 0.0,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_pass_rate": 0.0,
            "public_overfit_detection_rate": 0.0,
            "regression_free_patch_rate": 1.0 if public_passed else 0.0,
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
            "remote_inference_invoked": response_invoked,
            "local_model_execution_used": False,
            "usage": response_status.get("usage") or {},
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
    private_content_leaks: list[dict[str, Any]] = []
    private_content_markers = ["forge-private-heldout-", "private_heldout_seed_scores", "private_tasks"]
    for path in output_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for finding in scan_text_for_secrets(text):
            secret_findings.append({"path": str(path), **finding})
    for path in public_report_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for task_id in private_task_ids:
            if task_id in text:
                private_id_leaks.append({"path": str(path), "task_id": task_id})
        for marker in private_content_markers:
            if marker in text:
                private_content_leaks.append({"path": str(path), "marker": marker})
    return {
        "schema_version": "forgeagent.remote_inference_execution_privacy_report.v1",
        "scanned_paths": [str(path) for path in output_paths],
        "public_report_paths": [str(path) for path in public_report_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "public_safe_private_task_id_leak_count": len(private_id_leaks),
        "public_safe_private_task_id_leaks": private_id_leaks,
        "public_safe_private_content_leak_count": len(private_content_leaks),
        "public_safe_private_content_leaks": private_content_leaks,
        "passed": len(secret_findings) == 0
        and len(private_id_leaks) == 0
        and len(private_content_leaks) == 0,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    step17_summary = read_json(STEP29_17_DIR / "summary.json")
    step18_summary = read_json(STEP29_18_DIR / "summary.json")
    token_budget = read_json(STEP29_18_DIR / "token_budget.json")
    cost_policy = read_json(STEP29_18_DIR / "cost_approval_policy.json")
    default_approval = read_json(STEP29_18_DIR / "approval_record.json")
    request = read_json(STEP29_17_DIR / "bedrock_converse_request.json")
    heldout_summary = read_json(HELDOUT_PROTOCOL_DIR / "summary.json")
    contract_summary = read_json(CONTRACT_DIR / "summary.json")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if not step17_summary["bedrock_converse_request_ready"]:
        raise RuntimeError("Step 29.17 request is not ready")
    if not step18_summary["cost_policy_ready"]:
        raise RuntimeError("Step 29.18 cost policy is not ready")
    if not contract_summary["candidate_contract_ready"]:
        raise RuntimeError("model candidate eval contract is not ready")
    if not heldout_summary["protocol_ready"]:
        raise RuntimeError("heldout-aware protocol is not ready")

    request_sha256 = sha256_json(request)
    if request_sha256 != step18_summary["request_sha256"]:
        raise RuntimeError("request hash drift detected between Step 29.17 and Step 29.18")

    approval, approval_source = load_approval_evidence(default_approval)
    pricing = load_pricing_evidence()
    approval_requirement = build_approval_requirement(step18_summary["selected_model_id"], request_sha256)
    pricing_requirement = build_pricing_requirement(step18_summary["selected_model_id"], request_sha256)
    authorization = validate_approval_and_pricing(
        approval=approval,
        policy=cost_policy,
        pricing=pricing,
        approval_source=approval_source,
        selected_model_id=step18_summary["selected_model_id"],
        request_sha256=request_sha256,
        token_budget=token_budget,
    )

    request_copy_path = OUT_DIR / "bedrock_converse_request.json"
    write_json(request_copy_path, request)
    write_json(OUT_DIR / "approval_evidence_requirement.json", approval_requirement)
    write_json(OUT_DIR / "pricing_evidence_requirement.json", pricing_requirement)
    write_json(OUT_DIR / "approval_record_observed.json", approval)
    if pricing is not None:
        write_json(OUT_DIR / "pricing_evidence_observed.json", pricing)

    invocation_plan = {
        "schema_version": "forgeagent.remote_inference_invocation_plan.v1",
        "runner_name": "remote_inference_execution_candidate_eval_v1",
        "selected_model_id": step18_summary["selected_model_id"],
        "request_sha256": request_sha256,
        "command": [
            "aws",
            "--profile",
            AWS_PROFILE,
            "--region",
            AWS_REGION,
            "bedrock-runtime",
            "converse",
            "--cli-input-json",
            f"file://{request_copy_path}",
        ],
        "timeout_seconds": 120,
        "execution_authorized": authorization["execution_authorized"],
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
    }

    response_status: dict[str, Any]
    response_text = ""
    if authorization["execution_authorized"]:
        response_status = invoke_bedrock_converse(request_copy_path)
        if response_status["response_json_parse_ok"]:
            response = read_json(OUT_DIR / "remote_inference_response.json")
            response_text = extract_converse_text(response)
            write_text(OUT_DIR / "remote_inference_response_text.txt", response_text)
    else:
        response_status = {
            "schema_version": "forgeagent.remote_inference_response_status.v1",
            "command": invocation_plan["command"],
            "returncode": None,
            "remote_inference_invoked": False,
            "response_json_parse_ok": False,
            "usage": {},
            "metrics": {},
            "blocked_reason": "authorization_or_pricing_gate_failed",
        }

    diff_text = extract_unified_diff(response_text) if response_text else ""
    parse_result = {
        "schema_version": "forgeagent.remote_inference_response_parse_result.v1",
        "response_text_present": bool(response_text),
        "response_text_sha256": sha256_text(response_text) if response_text else None,
        "patch_extracted": bool(diff_text),
        "patch_sha256": sha256_text(diff_text) if diff_text else None,
        "raw_response_in_public_report": False,
        "patch_content_in_public_report": False,
    }

    if diff_text:
        task_json = STEP29_17_DIR / "public_smoke_task_workspace/task/task.json"
        task = read_json(task_json)
        source_repo = (task_json.parent / task["repo_dir"]).resolve()
        patch_validation = validate_patch(diff_text, source_repo, task["test_command"])
    else:
        patch_validation = {
            "schema_version": "forgeagent.remote_inference_patch_validation_result.v1",
            "patch_present": False,
            "patch_sha256": None,
            "git_apply_check_passed": False,
            "git_apply_check_exit_code": None,
            "git_apply_executed": False,
            "git_apply_passed": False,
            "public_tests_executed": False,
            "public_tests_passed": False,
            "public_tests_exit_code": None,
        }

    package = build_candidate_package(
        step18_summary=step18_summary,
        heldout_summary=heldout_summary,
        authorization=authorization,
        response_status=response_status,
        parse_result=parse_result,
        patch_validation=patch_validation,
    )
    validation = validate_candidate_package(package, build_contract(heldout_summary), private_task_ids)

    authorization_path = OUT_DIR / "execution_authorization_check.json"
    invocation_plan_path = OUT_DIR / "remote_inference_invocation_plan.json"
    response_status_path = OUT_DIR / "remote_inference_response_status.json"
    parse_result_path = OUT_DIR / "candidate_response_parse_result.json"
    patch_validation_path = OUT_DIR / "patch_validation_result.json"
    package_path = OUT_DIR / "candidate_packages/remote_inference_execution_candidate.json"
    validation_path = OUT_DIR / "candidate_validation_result.json"
    gate_path = OUT_DIR / "remote_inference_execution_candidate_eval_gate_decision.json"
    public_report_path = OUT_DIR / "public_safe_remote_inference_execution_candidate_eval_report.json"

    write_json(authorization_path, authorization)
    write_json(invocation_plan_path, invocation_plan)
    write_json(response_status_path, response_status)
    write_json(parse_result_path, parse_result)
    write_json(patch_validation_path, patch_validation)
    write_json(package_path, package)
    write_json(validation_path, validation)

    gate = {
        "schema_version": "forgeagent.remote_inference_execution_candidate_eval_gate_decision.v1",
        "runner_name": "remote_inference_execution_candidate_eval_v1",
        "step29_17_ready": True,
        "step29_18_ready": True,
        "request_hash_verified": True,
        "pricing_evidence_present": authorization["pricing_evidence_present"],
        "execution_authorized": authorization["execution_authorized"],
        "remote_inference_invoked": response_status["remote_inference_invoked"],
        "remote_response_present": response_status["response_json_parse_ok"],
        "patch_extracted": parse_result["patch_extracted"],
        "git_apply_check_passed": patch_validation["git_apply_check_passed"],
        "public_tests_passed": patch_validation["public_tests_passed"],
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_execution_blocked": None
        if authorization["execution_authorized"]
        else "approval, pricing evidence or execute flag is missing",
        "reason_release_blocked": "private heldout aggregate evaluation has not run for this candidate",
    }
    write_json(gate_path, gate)

    public_report = {
        "schema_version": "forgeagent.public_safe_remote_inference_execution_candidate_eval_report.v1",
        "report_name": "remote_inference_execution_candidate_eval_v1_public_safe",
        "selected_model_id": step18_summary["selected_model_id"],
        "request_sha256": request_sha256,
        "execution_authorized": authorization["execution_authorized"],
        "remote_inference_invoked": response_status["remote_inference_invoked"],
        "remote_response_present": response_status["response_json_parse_ok"],
        "patch_extracted": parse_result["patch_extracted"],
        "patch_sha256": parse_result["patch_sha256"],
        "git_apply_check_passed": patch_validation["git_apply_check_passed"],
        "public_tests_passed": patch_validation["public_tests_passed"],
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "request_prompt_included": False,
            "raw_response_included": False,
            "patch_content_included": False,
            "private_task_ids_included": False,
            "private_patch_content_included": False,
            "private_hidden_test_content_included": False,
        },
    }
    write_json(public_report_path, public_report)

    privacy = scan_outputs(
        output_paths=[
            authorization_path,
            invocation_plan_path,
            response_status_path,
            parse_result_path,
            patch_validation_path,
            package_path,
            validation_path,
            gate_path,
            public_report_path,
        ],
        public_report_paths=[public_report_path],
        private_task_ids=private_task_ids,
    )
    privacy_path = OUT_DIR / "remote_inference_execution_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.remote_inference_execution_candidate_eval_summary.v1",
        "runner_name": "remote_inference_execution_candidate_eval_v1",
        "source_step": "step29_18_remote_inference_cost_approval_gate_v1",
        "step29_17_ready": True,
        "step29_18_ready": True,
        "selected_model_id": step18_summary["selected_model_id"],
        "request_sha256": request_sha256,
        "request_hash_verified": True,
        "pricing_evidence_present": authorization["pricing_evidence_present"],
        "execute_flag_set": authorization["execute_flag_set"],
        "approval_record_approved": authorization["approval_record_approved"],
        "execution_authorized": authorization["execution_authorized"],
        "remote_inference_invoked": response_status["remote_inference_invoked"],
        "remote_response_present": response_status["response_json_parse_ok"],
        "patch_extracted": parse_result["patch_extracted"],
        "git_apply_check_passed": patch_validation["git_apply_check_passed"],
        "public_tests_passed": patch_validation["public_tests_passed"],
        "candidate_package_count": 1,
        "candidate_package_valid_count": 1 if validation["contract_valid"] else 0,
        "release_gate_passed_count": 1 if validation["release_gate_passed"] else 0,
        "public_safe_report_ready": True,
        "public_safe_private_task_id_leak_count": privacy["public_safe_private_task_id_leak_count"],
        "public_safe_private_content_leak_count": privacy["public_safe_private_content_leak_count"],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_19_authorized_remote_inference_smoke_eval_after_approval",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "approval_evidence_requirement": str(OUT_DIR / "approval_evidence_requirement.json"),
            "pricing_evidence_requirement": str(OUT_DIR / "pricing_evidence_requirement.json"),
            "approval_record_observed": str(OUT_DIR / "approval_record_observed.json"),
            "execution_authorization_check": str(authorization_path),
            "remote_inference_invocation_plan": str(invocation_plan_path),
            "remote_inference_response_status": str(response_status_path),
            "candidate_response_parse_result": str(parse_result_path),
            "patch_validation_result": str(patch_validation_path),
            "candidate_package": str(package_path),
            "candidate_validation_result": str(validation_path),
            "gate_decision": str(gate_path),
            "public_safe_report": str(public_report_path),
            "privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("REMOTE_INFERENCE_EXECUTION_CANDIDATE_EVAL_V1_OK")


if __name__ == "__main__":
    main()

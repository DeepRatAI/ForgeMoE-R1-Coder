from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.prompt_builder import build_patch_generation_messages  # noqa: E402
from forgeagentcoder.data.task_schema import AgentTask  # noqa: E402
from forgeagentcoder.eval.command_runner import run_shell_command  # noqa: E402
from run_model_candidate_eval_contract_v1 import (  # noqa: E402
    build_contract,
    scan_text_for_secrets,
    validate_candidate_package,
)


PUBLIC_SUITE_DIR = PROJECT_ROOT / "results/local/public_eval_suite_scaleout_v1"
RUNNER_DIR = PROJECT_ROOT / "results/local/public_eval_candidate_runner_scaleout_v1"
STEP29_17_DIR = PROJECT_ROOT / "results/local/remote_code_model_candidate_smoke_eval_v1"
STEP29_19_DIR = PROJECT_ROOT / "results/local/remote_inference_execution_candidate_eval_v1"
CONTRACT_DIR = PROJECT_ROOT / "results/local/model_candidate_eval_contract_v1"
HELDOUT_PROTOCOL_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
OUT_DIR = PROJECT_ROOT / "results/local/public_eval_remote_batch_adapter_v1"

AWS_PROFILE = "forgemoe"
AWS_REGION = "us-west-2"
MAX_OUTPUT_TOKENS_PER_TASK = 1024

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\\s*[:=]"),
}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


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


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def model_size_class(model_id: str) -> str:
    lowered = model_id.lower()
    if "7b" in lowered:
        return "7b"
    if "9b" in lowered:
        return "9b"
    if "14b" in lowered:
        return "14b"
    if "12b" in lowered:
        return "14b"
    return "tiny_smoke"


def task_paths() -> list[Path]:
    return sorted((PUBLIC_SUITE_DIR / "public_eval_tasks").glob("*/task.json"))


def build_bedrock_converse_request(*, model_id: str, messages: list[dict[str, str]], task_id: str) -> dict[str, Any]:
    system_text = "\n\n".join(message["content"] for message in messages if message["role"] == "system")
    user_text = "\n\n".join(message["content"] for message in messages if message["role"] == "user")
    return {
        "modelId": model_id,
        "system": [{"text": system_text}],
        "messages": [
            {
                "role": "user",
                "content": [{"text": user_text}],
            }
        ],
        "inferenceConfig": {
            "maxTokens": MAX_OUTPUT_TOKENS_PER_TASK,
            "temperature": 0.0,
            "topP": 1.0,
        },
        "requestMetadata": {
            "forge_step": "step29_22_public_eval_remote_batch_adapter",
            "public_eval_task_id": task_id,
            "execution_mode": "prepared_not_invoked",
        },
    }


def build_batch_candidate_package(
    *,
    selected_model_id: str,
    selected_model_provider: str | None,
    heldout_summary: dict[str, Any],
    batch_request_sha256: str,
    public_eval_task_count: int,
) -> dict[str, Any]:
    return {
        "candidate_identity": {
            "candidate_id": "public-eval-remote-batch-prepared-v1",
            "candidate_kind": "remote_public_eval_batch_prepared",
            "created_by_step": "step29_22_public_eval_remote_batch_adapter",
            "is_real_model_candidate": False,
        },
        "model_metadata": {
            "model_id": selected_model_id,
            "model_size_class": model_size_class(selected_model_id),
            "adapter_name": "BedrockConversePublicEvalBatchAdapter",
            "runtime": "bedrock_on_demand",
            "base_or_tuned": "base",
            "revision": "remote_inventory_selected",
            "provider": selected_model_provider,
        },
        "run_provenance": {
            "git_commit": git_commit(),
            "prompt_contract_version": "public_eval_batch_prompt_v1",
            "candidate_pipeline_version": "public_eval_remote_batch_adapter_v1",
            "heldout_protocol_version": "heldout_aware_eval_protocol_v1",
            "public_eval_suite_version": "public_eval_suite_scaleout_v1",
            "batch_request_sha256": batch_request_sha256,
            "execution_authorized": False,
        },
        "generation_config": {
            "max_new_tokens": MAX_OUTPUT_TOKENS_PER_TASK,
            "temperature": 0.0,
            "top_p": 1.0,
            "do_sample": False,
            "num_return_sequences": 0,
            "seed": 2922,
        },
        "eval_scope": {
            "train_rows_observed": 0,
            "public_eval_task_count": public_eval_task_count,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_aggregate_only": True,
            "private_heldout_task_ids_exposed": False,
            "candidate_outputs_contain_private_material": False,
            "private_heldout_evaluated": False,
            "remote_inference_executed": False,
            "local_model_execution_used": False,
        },
        "aggregate_metrics": {
            "raw_response_count": 0,
            "parsed_candidate_count": 0,
            "parse_failure_count": 0,
            "parse_validity_rate": 0.0,
            "public_eval_task_count": public_eval_task_count,
            "public_eval_solve_rate": 0.0,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_pass_rate": 0.0,
            "public_overfit_detection_rate": 0.0,
            "regression_free_patch_rate": 0.0,
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
            "remote_inference_invoked": False,
            "local_model_execution_used": False,
            "approval_required_before_execution": True,
        },
    }


def build_public_safe_report(
    *,
    selected_model_id: str,
    selected_model_provider: str | None,
    task_count: int,
    total_token_ceiling: int,
    validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.public_safe_public_eval_remote_batch_adapter_report.v1",
        "report_name": "public_eval_remote_batch_adapter_v1_public_safe",
        "selected_model_id": selected_model_id,
        "selected_model_provider": selected_model_provider,
        "public_eval_task_count": task_count,
        "bedrock_converse_request_count": task_count,
        "estimated_total_token_ceiling": total_token_ceiling,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "task_level_prompt_text_included": False,
            "raw_response_included": False,
            "patch_content_included": False,
            "public_test_content_included": False,
            "hidden_test_content_included": False,
            "private_task_ids_included": False,
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
        "schema_version": "forgeagent.public_eval_remote_batch_adapter_privacy_report.v1",
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

    public_suite_summary = read_json(PUBLIC_SUITE_DIR / "summary.json")
    runner_summary = read_json(RUNNER_DIR / "summary.json")
    step17_summary = read_json(STEP29_17_DIR / "summary.json")
    step19_summary = read_json(STEP29_19_DIR / "summary.json")
    contract_summary = read_json(CONTRACT_DIR / "summary.json")
    heldout_summary = read_json(HELDOUT_PROTOCOL_DIR / "summary.json")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if public_suite_summary["verified_public_eval_task_count"] != public_suite_summary["public_eval_task_count"]:
        raise RuntimeError("public eval suite is not fully verified")
    if not runner_summary["candidate_eval_runner_ready"]:
        raise RuntimeError("public eval candidate runner is not ready")
    if not step17_summary["bedrock_converse_request_ready"]:
        raise RuntimeError("remote code model request seed is not ready")
    if step19_summary["remote_inference_invoked"]:
        raise RuntimeError("Step 29.22 must not start from an already-invoked Step 29.19 state")
    if not contract_summary["candidate_contract_ready"]:
        raise RuntimeError("model candidate eval contract is not ready")
    if not heldout_summary["protocol_ready"]:
        raise RuntimeError("heldout-aware protocol is not ready")

    selected_model_id = step17_summary["selected_model_id"]
    selected_model_provider = step17_summary.get("selected_model_provider")
    request_dir = OUT_DIR / "bedrock_converse_requests"
    message_dir = OUT_DIR / "bedrock_converse_messages"
    pretest_path = OUT_DIR / "public_eval_batch_pretest_results.jsonl"
    request_manifest_path = OUT_DIR / "public_eval_batch_request_manifest.json"

    task_rows: list[dict[str, Any]] = []
    request_hashes: list[str] = []
    total_input_tokens = 0
    total_token_ceiling = 0

    for task_json in task_paths():
        task = AgentTask.from_json_file(task_json)
        task.validate()
        pre_test = run_shell_command(
            task.test_command,
            cwd=task.repo_dir,
            timeout_seconds=task.timeout_seconds,
        )
        if pre_test.passed:
            raise RuntimeError(f"public eval task must fail before candidate generation: {task.task_id}")

        messages = build_patch_generation_messages(
            task,
            pre_test_stderr=pre_test.stderr or pre_test.stdout,
            max_files=20,
            max_file_chars=4000,
        )
        request = build_bedrock_converse_request(
            model_id=selected_model_id,
            messages=messages,
            task_id=task.task_id,
        )
        request_hash = sha256_json(request)
        request_hashes.append(request_hash)
        prompt_blob = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        input_tokens = estimate_tokens(prompt_blob)
        token_ceiling = input_tokens + MAX_OUTPUT_TOKENS_PER_TASK
        total_input_tokens += input_tokens
        total_token_ceiling += token_ceiling

        message_path = message_dir / f"{task.task_id}.json"
        request_path = request_dir / f"{task.task_id}.json"
        write_json(message_path, messages)
        write_json(request_path, request)
        append_jsonl(
            pretest_path,
            {
                "schema_version": "forgeagent.public_eval_batch_pretest_result.v1",
                "task_id": task.task_id,
                "test_command": task.test_command,
                "exit_code": pre_test.exit_code,
                "passed": pre_test.passed,
                "timed_out": pre_test.timed_out,
                "stdout_sha256": sha256_text(pre_test.stdout),
                "stderr_sha256": sha256_text(pre_test.stderr),
                "elapsed_seconds": pre_test.elapsed_seconds,
            },
        )
        task_rows.append(
            {
                "task_id": task.task_id,
                "request_sha256": request_hash,
                "message_sha256": sha256_json(messages),
                "estimated_input_tokens": input_tokens,
                "max_output_tokens": MAX_OUTPUT_TOKENS_PER_TASK,
                "estimated_total_token_ceiling": token_ceiling,
                "pre_public_failed": not pre_test.passed,
                "request_path": str(request_path),
                "message_path": str(message_path),
            }
        )

    batch_request_sha256 = sha256_json(request_hashes)
    request_manifest = {
        "schema_version": "forgeagent.public_eval_remote_batch_request_manifest.v1",
        "runner_name": "public_eval_remote_batch_adapter_v1",
        "selected_model_id": selected_model_id,
        "selected_model_provider": selected_model_provider,
        "public_eval_task_count": len(task_rows),
        "request_count": len(task_rows),
        "request_hashes": request_hashes,
        "batch_request_sha256": batch_request_sha256,
        "estimated_input_tokens": total_input_tokens,
        "max_output_tokens_per_task": MAX_OUTPUT_TOKENS_PER_TASK,
        "estimated_total_token_ceiling": total_token_ceiling,
        "task_requests": task_rows,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
    }
    write_json(request_manifest_path, request_manifest)

    cost_policy = {
        "schema_version": "forgeagent.public_eval_remote_batch_cost_policy.v1",
        "selected_model_id": selected_model_id,
        "batch_request_sha256": batch_request_sha256,
        "public_eval_task_count": len(task_rows),
        "max_remote_inference_calls": len(task_rows),
        "max_output_tokens_per_task": MAX_OUTPUT_TOKENS_PER_TASK,
        "estimated_input_tokens": total_input_tokens,
        "estimated_total_token_ceiling": total_token_ceiling,
        "pricing_quote_required": True,
        "approval_required": True,
        "execution_authorized": False,
    }
    cost_policy_path = OUT_DIR / "public_eval_remote_batch_cost_policy.json"
    write_json(cost_policy_path, cost_policy)

    approval_record = {
        "schema_version": "forgeagent.public_eval_remote_batch_approval_record.v1",
        "approval_id": "public-eval-remote-batch-unapproved-v1",
        "approved": False,
        "approved_model_id": selected_model_id,
        "approved_batch_request_sha256": batch_request_sha256,
        "approved_request_sha256_values": request_hashes,
        "approved_max_remote_inference_calls": 0,
        "approved_max_total_usd": 0.0,
        "approval_evidence": "not_approved",
        "execution_authorized": False,
    }
    approval_path = OUT_DIR / "public_eval_remote_batch_approval_record.json"
    write_json(approval_path, approval_record)

    pricing_requirement = {
        "schema_version": "forgeagent.public_eval_remote_batch_pricing_evidence_requirement.v1",
        "required": True,
        "required_model_id": selected_model_id,
        "required_batch_request_sha256": batch_request_sha256,
        "required_region": AWS_REGION,
        "required_source": "official_provider_pricing_page_or_aws_pricing_api",
        "required_fields": [
            "schema_version",
            "model_id",
            "batch_request_sha256",
            "region",
            "official_pricing_source",
            "pricing_captured_at",
            "estimated_total_usd",
            "estimated_input_tokens",
            "estimated_output_tokens",
        ],
    }
    pricing_requirement_path = OUT_DIR / "public_eval_remote_batch_pricing_evidence_requirement.json"
    write_json(pricing_requirement_path, pricing_requirement)

    authorization = {
        "schema_version": "forgeagent.public_eval_remote_batch_authorization_check.v1",
        "execution_authorized": False,
        "execute_flag_set": False,
        "approval_record_approved": False,
        "pricing_evidence_present": False,
        "request_count_within_policy": len(task_rows) <= cost_policy["max_remote_inference_calls"],
        "token_ceiling_recorded": total_token_ceiling > 0,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "failed_checks": [
            "execute_flag_set",
            "approval_record_approved",
            "pricing_evidence_present",
        ],
    }
    authorization_path = OUT_DIR / "public_eval_remote_batch_authorization_check.json"
    write_json(authorization_path, authorization)

    execution_plan = {
        "schema_version": "forgeagent.public_eval_remote_batch_execution_plan.v1",
        "runner_name": "public_eval_remote_batch_adapter_v1",
        "selected_model_id": selected_model_id,
        "batch_request_sha256": batch_request_sha256,
        "request_count": len(task_rows),
        "commands": [
            {
                "task_id": row["task_id"],
                "command": [
                    "aws",
                    "--profile",
                    AWS_PROFILE,
                    "--region",
                    AWS_REGION,
                    "bedrock-runtime",
                    "converse",
                    "--cli-input-json",
                    f"file://{row['request_path']}",
                ],
            }
            for row in task_rows
        ],
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
    }
    execution_plan_path = OUT_DIR / "public_eval_remote_batch_execution_plan.json"
    write_json(execution_plan_path, execution_plan)

    package = build_batch_candidate_package(
        selected_model_id=selected_model_id,
        selected_model_provider=selected_model_provider,
        heldout_summary=heldout_summary,
        batch_request_sha256=batch_request_sha256,
        public_eval_task_count=len(task_rows),
    )
    validation = validate_candidate_package(package, build_contract(heldout_summary), private_task_ids)
    package_path = OUT_DIR / "candidate_packages/public_eval_remote_batch_prepared.json"
    validation_path = OUT_DIR / "candidate_validation_result.json"
    write_json(package_path, package)
    write_json(validation_path, validation)

    gate = {
        "schema_version": "forgeagent.public_eval_remote_batch_adapter_gate_decision.v1",
        "runner_name": "public_eval_remote_batch_adapter_v1",
        "public_eval_suite_ready": True,
        "public_eval_candidate_runner_ready": True,
        "public_eval_task_count": len(task_rows),
        "request_count": len(task_rows),
        "all_public_pretests_failed": all(row["pre_public_failed"] for row in task_rows),
        "request_manifest_ready": True,
        "cost_policy_ready": True,
        "approval_required": True,
        "pricing_evidence_required": True,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_execution_blocked": "batch approval and official pricing evidence are required",
        "reason_release_blocked": "prepared batch has no real candidate responses, patches or private heldout aggregate result",
    }
    gate_path = OUT_DIR / "public_eval_remote_batch_adapter_gate_decision.json"
    write_json(gate_path, gate)

    public_report = build_public_safe_report(
        selected_model_id=selected_model_id,
        selected_model_provider=selected_model_provider,
        task_count=len(task_rows),
        total_token_ceiling=total_token_ceiling,
        validation=validation,
    )
    public_report_path = OUT_DIR / "public_safe_public_eval_remote_batch_adapter_report.json"
    write_json(public_report_path, public_report)

    output_paths = [
        request_manifest_path,
        cost_policy_path,
        approval_path,
        pricing_requirement_path,
        authorization_path,
        execution_plan_path,
        package_path,
        validation_path,
        gate_path,
        public_report_path,
        pretest_path,
        *sorted(request_dir.glob("*.json")),
        *sorted(message_dir.glob("*.json")),
    ]
    privacy = scan_outputs(
        output_paths=output_paths,
        public_report_paths=[public_report_path],
        private_task_ids=private_task_ids,
    )
    privacy_path = OUT_DIR / "public_eval_remote_batch_adapter_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.public_eval_remote_batch_adapter_summary.v1",
        "runner_name": "public_eval_remote_batch_adapter_v1",
        "source_step": "step29_21_public_eval_candidate_runner_scaleout_v1",
        "public_eval_suite_ready": True,
        "public_eval_candidate_runner_ready": True,
        "selected_model_id": selected_model_id,
        "selected_model_provider": selected_model_provider,
        "public_eval_task_count": len(task_rows),
        "bedrock_converse_request_count": len(task_rows),
        "all_public_pretests_failed": all(row["pre_public_failed"] for row in task_rows),
        "request_manifest_ready": True,
        "batch_request_sha256": batch_request_sha256,
        "estimated_input_tokens": total_input_tokens,
        "max_output_tokens_per_task": MAX_OUTPUT_TOKENS_PER_TASK,
        "estimated_total_token_ceiling": total_token_ceiling,
        "cost_policy_ready": True,
        "approval_record_present": True,
        "approval_record_approved": False,
        "pricing_evidence_present": False,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "candidate_package_count": 1,
        "candidate_package_valid_count": 1 if validation["contract_valid"] else 0,
        "release_gate_passed_count": 1 if validation["release_gate_passed"] else 0,
        "public_safe_report_ready": True,
        "private_task_id_leak_count": privacy["private_task_id_leak_count"],
        "public_report_content_leak_count": privacy["public_report_content_leak_count"],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_23_authorized_public_eval_remote_batch_execution",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "request_manifest": str(request_manifest_path),
            "bedrock_converse_requests": str(request_dir),
            "bedrock_converse_messages": str(message_dir),
            "pretest_results": str(pretest_path),
            "cost_policy": str(cost_policy_path),
            "approval_record": str(approval_path),
            "pricing_evidence_requirement": str(pricing_requirement_path),
            "authorization_check": str(authorization_path),
            "execution_plan": str(execution_plan_path),
            "candidate_package": str(package_path),
            "candidate_validation_result": str(validation_path),
            "gate_decision": str(gate_path),
            "public_safe_report": str(public_report_path),
            "privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("PUBLIC_EVAL_REMOTE_BATCH_ADAPTER_V1_OK")


if __name__ == "__main__":
    main()

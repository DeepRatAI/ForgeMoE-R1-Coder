from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
from typing import Any

from run_model_candidate_eval_contract_v1 import scan_text_for_secrets


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP29_17_DIR = PROJECT_ROOT / "results/local/remote_code_model_candidate_smoke_eval_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
OUT_DIR = PROJECT_ROOT / "results/local/remote_inference_cost_approval_gate_v1"

AWS_PROFILE = os.environ.get("AWS_PROFILE", "forgemoe")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
DEFAULT_MAX_APPROVED_USD = 1.00


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def estimate_tokens_from_text(text: str) -> int:
    # Conservative planning estimate for approval only. Real billing must use provider usage data.
    return max(1, (len(text) + 2) // 3)


def count_request_tokens(request: dict[str, Any]) -> dict[str, Any]:
    system_text = "\n\n".join(item.get("text", "") for item in request.get("system", []))
    message_text = "\n\n".join(
        content.get("text", "")
        for message in request.get("messages", [])
        for content in message.get("content", [])
    )
    prompt_text = "\n\n".join([system_text, message_text]).strip()
    max_output_tokens = int((request.get("inferenceConfig") or {}).get("maxTokens", 0))
    estimated_input_tokens = estimate_tokens_from_text(prompt_text)
    return {
        "schema_version": "forgeagent.remote_inference_token_budget.v1",
        "prompt_sha256": sha256_text(prompt_text),
        "prompt_char_count": len(prompt_text),
        "estimated_input_tokens": estimated_input_tokens,
        "max_output_tokens": max_output_tokens,
        "estimated_total_token_ceiling": estimated_input_tokens + max_output_tokens,
        "estimation_method": "ceil(prompt_chars/3)+max_output_tokens",
        "billing_note": "actual billing must use provider-reported input/output token usage",
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
    private_content_markers = ["forge-private-heldout-", "diff --git", "assertEqual"]

    for path in output_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for finding in scan_text_for_secrets(text):
            secret_findings.append({"path": str(path), **finding})

    for path in public_report_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for task_id in private_task_ids:
            if task_id in text:
                private_id_leaks.append({"path": str(path), "task_id": task_id})
        for marker in private_content_markers:
            if marker in text:
                private_content_leaks.append({"path": str(path), "marker": marker})

    return {
        "schema_version": "forgeagent.remote_inference_cost_approval_privacy_report.v1",
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
    request = read_json(STEP29_17_DIR / "bedrock_converse_request.json")
    command_plan = read_json(STEP29_17_DIR / "bedrock_converse_command_plan.json")
    step17_gate = read_json(STEP29_17_DIR / "remote_code_model_candidate_smoke_eval_gate_decision.json")
    step17_validation = read_json(STEP29_17_DIR / "candidate_validation_result.json")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if not step17_summary["bedrock_converse_request_ready"]:
        raise RuntimeError("Step 29.17 Bedrock Converse request is not ready")
    if step17_summary["remote_inference_invoked"]:
        raise RuntimeError("Step 29.17 unexpectedly invoked remote inference")
    if step17_summary["local_model_execution_used"]:
        raise RuntimeError("Step 29.17 unexpectedly used local model execution")
    if step17_gate["remote_inference_invoked"]:
        raise RuntimeError("Step 29.17 gate unexpectedly recorded remote inference")
    if step17_gate["execution_authorized"]:
        raise RuntimeError("Step 29.17 gate unexpectedly authorized execution")

    token_budget = count_request_tokens(request)
    cost_policy = {
        "schema_version": "forgeagent.remote_inference_cost_approval_policy.v1",
        "policy_name": "remote_inference_cost_approval_gate_v1",
        "selected_model_id": step17_summary["selected_model_id"],
        "selected_model_provider": step17_summary["selected_model_provider"],
        "aws_region": AWS_REGION,
        "approval_status": "not_approved",
        "approved_by_user": False,
        "max_approved_total_usd": DEFAULT_MAX_APPROVED_USD,
        "max_remote_inference_calls": 1,
        "max_input_tokens_estimate": token_budget["estimated_input_tokens"],
        "max_output_tokens": token_budget["max_output_tokens"],
        "estimated_total_token_ceiling": token_budget["estimated_total_token_ceiling"],
        "pricing_quote_status": "required_before_execution",
        "pricing_quote_source_required": "official_provider_pricing_or_billing_api",
        "abort_conditions": [
            "approval_status_is_not_approved",
            "selected_model_id_differs_from_approved_model",
            "request_hash_differs_from_approved_request",
            "estimated_token_ceiling_exceeds_policy",
            "private_heldout_content_present_in_request",
            "local_model_runtime_detected",
        ],
    }

    request_hash = sha256_text(json.dumps(request, sort_keys=True, ensure_ascii=False))
    execution_plan = {
        "schema_version": "forgeagent.remote_inference_execution_plan.v1",
        "plan_name": "step29_18_remote_inference_execution_plan",
        "status": "blocked_until_user_cost_approval",
        "git_commit": git_commit(),
        "selected_model_id": step17_summary["selected_model_id"],
        "request_sha256": request_hash,
        "request_artifact": str(STEP29_17_DIR / "bedrock_converse_request.json"),
        "output_artifact_planned": str(OUT_DIR / "remote_inference_response.json"),
        "command": command_plan["command"],
        "timeout_seconds": 120,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "post_execution_required_checks": [
            "response_json_parse",
            "extract_text_response",
            "extract_unified_diff",
            "git_apply_check",
            "public_tests_post_patch",
            "candidate_package_contract_validation",
            "public_safe_report_privacy_scan",
        ],
    }

    approval_record = {
        "schema_version": "forgeagent.remote_inference_user_approval_record.v1",
        "approval_id": "step29_18_remote_inference_cost_approval",
        "approved": False,
        "approved_model_id": None,
        "approved_request_sha256": None,
        "approved_max_total_usd": None,
        "approved_max_remote_inference_calls": 0,
        "approval_timestamp": None,
        "approval_evidence": "not_provided",
        "remote_inference_invoked": False,
    }

    gate_decision = {
        "schema_version": "forgeagent.remote_inference_cost_approval_gate_decision.v1",
        "gate_name": "remote_inference_cost_approval_gate_v1",
        "step29_17_ready": True,
        "selected_model_id": step17_summary["selected_model_id"],
        "request_ready": True,
        "request_sha256": request_hash,
        "token_budget_ready": True,
        "cost_policy_ready": True,
        "pricing_quote_required": True,
        "approval_record_present": True,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_execution_blocked": "explicit user approval and official pricing quote are required",
        "reason_release_blocked": "no remote inference response or patch validation exists",
        "candidate_validation_errors_from_step29_17": step17_validation["errors"],
        "next_required_action": "approve_remote_inference_cost_before_execution",
    }

    public_report = {
        "schema_version": "forgeagent.public_safe_remote_inference_cost_approval_report.v1",
        "report_name": "remote_inference_cost_approval_gate_v1_public_safe",
        "selected_model_id": step17_summary["selected_model_id"],
        "selected_model_provider": step17_summary["selected_model_provider"],
        "request_ready": True,
        "estimated_input_tokens": token_budget["estimated_input_tokens"],
        "max_output_tokens": token_budget["max_output_tokens"],
        "estimated_total_token_ceiling": token_budget["estimated_total_token_ceiling"],
        "max_remote_inference_calls": cost_policy["max_remote_inference_calls"],
        "approval_status": cost_policy["approval_status"],
        "pricing_quote_required": True,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "request_prompt_included": False,
            "private_task_ids_included": False,
            "private_patch_content_included": False,
            "private_hidden_test_content_included": False,
            "candidate_raw_outputs_included": False,
        },
    }

    token_budget_path = OUT_DIR / "token_budget.json"
    cost_policy_path = OUT_DIR / "cost_approval_policy.json"
    execution_plan_path = OUT_DIR / "remote_inference_execution_plan.json"
    approval_record_path = OUT_DIR / "approval_record.json"
    gate_path = OUT_DIR / "remote_inference_cost_approval_gate_decision.json"
    public_report_path = OUT_DIR / "public_safe_remote_inference_cost_approval_report.json"

    write_json(token_budget_path, token_budget)
    write_json(cost_policy_path, cost_policy)
    write_json(execution_plan_path, execution_plan)
    write_json(approval_record_path, approval_record)
    write_json(gate_path, gate_decision)
    write_json(public_report_path, public_report)

    privacy = scan_outputs(
        output_paths=[
            token_budget_path,
            cost_policy_path,
            execution_plan_path,
            approval_record_path,
            gate_path,
            public_report_path,
        ],
        public_report_paths=[public_report_path],
        private_task_ids=private_task_ids,
    )
    privacy_path = OUT_DIR / "remote_inference_cost_approval_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.remote_inference_cost_approval_gate_summary.v1",
        "gate_name": "remote_inference_cost_approval_gate_v1",
        "source_step": "step29_17_remote_code_model_candidate_smoke_eval_v1",
        "step29_17_ready": True,
        "selected_model_id": step17_summary["selected_model_id"],
        "selected_model_provider": step17_summary["selected_model_provider"],
        "request_ready": True,
        "request_sha256": request_hash,
        "token_budget_ready": True,
        "estimated_input_tokens": token_budget["estimated_input_tokens"],
        "max_output_tokens": token_budget["max_output_tokens"],
        "estimated_total_token_ceiling": token_budget["estimated_total_token_ceiling"],
        "cost_policy_ready": True,
        "pricing_quote_required": True,
        "approval_record_present": True,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "remote_response_present": False,
        "candidate_eval_executed": False,
        "public_safe_report_ready": True,
        "public_safe_private_task_id_leak_count": privacy["public_safe_private_task_id_leak_count"],
        "public_safe_private_content_leak_count": privacy["public_safe_private_content_leak_count"],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_19_remote_inference_execution_candidate_eval",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "token_budget": str(token_budget_path),
            "cost_approval_policy": str(cost_policy_path),
            "remote_inference_execution_plan": str(execution_plan_path),
            "approval_record": str(approval_record_path),
            "gate_decision": str(gate_path),
            "public_safe_report": str(public_report_path),
            "privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("REMOTE_INFERENCE_COST_APPROVAL_GATE_V1_OK")


if __name__ == "__main__":
    main()

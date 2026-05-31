from __future__ import annotations

from pathlib import Path
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
CONTRACT_DIR = PROJECT_ROOT / "results/local/model_candidate_eval_contract_v1"
HELDOUT_PROTOCOL_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
CANDIDATE_RUNNER_DIR = PROJECT_ROOT / "results/local/candidate_eval_runner_dry_run_v1"
OUT_DIR = PROJECT_ROOT / "results/local/remote_candidate_smoke_preflight_v1"

AWS_PROFILE = os.environ.get("AWS_PROFILE", "forgemoe")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
S3_BUCKET = os.environ.get("FORGEMOE_S3_BUCKET", "forgemoe-coder-568844635400-us-west-2-an")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def run_aws(args: list[str]) -> dict[str, Any]:
    command = [
        "aws",
        "--profile",
        AWS_PROFILE,
        "--region",
        AWS_REGION,
        *args,
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": ["aws", "--profile", AWS_PROFILE, "--region", AWS_REGION, *args],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "ok": completed.returncode == 0,
    }


def parse_json_output(result: dict[str, Any]) -> dict[str, Any]:
    if not result["ok"]:
        return {}
    try:
        return json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError:
        return {}


def redact_aws_identity(identity: dict[str, Any]) -> dict[str, Any]:
    arn = identity.get("Arn", "")
    return {
        "account_present": bool(identity.get("Account")),
        "user_id_present": bool(identity.get("UserId")),
        "arn_type": "iam_user" if ":user/" in arn else "unknown",
    }


def bedrock_candidate_summary(models: list[dict[str, Any]]) -> dict[str, Any]:
    text_models = [
        model
        for model in models
        if "TEXT" in model.get("inputModalities", [])
        and "TEXT" in model.get("outputModalities", [])
        and model.get("modelLifecycle", {}).get("status") in {"ACTIVE", "LEGACY"}
    ]
    on_demand_models = [
        model for model in text_models if "ON_DEMAND" in model.get("inferenceTypesSupported", [])
    ]
    open_weight_like = [
        model
        for model in on_demand_models
        if any(
            marker in model.get("modelId", "").lower()
            for marker in ["mistral", "llama", "qwen", "deepseek", "openai.gpt-oss", "nvidia"]
        )
    ]
    preferred = [
        model
        for model in open_weight_like
        if any(marker in model.get("modelName", "").lower() for marker in ["7b", "9b", "12b", "14b"])
    ]
    selected_pool = preferred or open_weight_like or on_demand_models
    selected = selected_pool[0] if selected_pool else {}
    return {
        "text_model_count": len(text_models),
        "on_demand_text_model_count": len(on_demand_models),
        "open_weight_like_on_demand_count": len(open_weight_like),
        "preferred_size_match_count": len(preferred),
        "selected_public_model_id": selected.get("modelId"),
        "selected_public_model_name": selected.get("modelName"),
        "selected_public_provider": selected.get("providerName"),
        "selected_inference_types": selected.get("inferenceTypesSupported", []),
    }


def build_blocked_preflight_package(
    *,
    heldout_summary: dict[str, Any],
    bedrock_summary: dict[str, Any],
    sagemaker_endpoint_count: int,
    sagemaker_model_count: int,
) -> dict[str, Any]:
    return {
        "candidate_identity": {
            "candidate_id": "remote-candidate-smoke-preflight",
            "candidate_kind": "remote_runtime_preflight",
            "created_by_step": "step29_16_remote_candidate_smoke_preflight",
            "is_real_model_candidate": False,
        },
        "model_metadata": {
            "model_id": bedrock_summary.get("selected_public_model_id") or "remote-candidate-not-executed",
            "model_size_class": "7b" if bedrock_summary.get("preferred_size_match_count") else "tiny_smoke",
            "adapter_name": "AwsRemoteCandidatePreflightAdapter",
            "runtime": "bedrock_on_demand",
            "base_or_tuned": "base",
            "revision": "not_executed",
            "sagemaker_endpoint_count": sagemaker_endpoint_count,
            "sagemaker_model_count": sagemaker_model_count,
        },
        "run_provenance": {
            "git_commit": git_commit(),
            "prompt_contract_version": "not_executed_preflight_only",
            "candidate_pipeline_version": "remote_candidate_smoke_preflight_v1",
            "heldout_protocol_version": "heldout_aware_eval_protocol_v1",
        },
        "generation_config": {
            "max_new_tokens": 0,
            "temperature": 0.0,
            "top_p": 1.0,
            "do_sample": False,
            "num_return_sequences": 0,
            "seed": 2916,
        },
        "eval_scope": {
            "train_rows_observed": 0,
            "public_eval_task_count": 0,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_aggregate_only": True,
            "private_heldout_task_ids_exposed": False,
            "candidate_outputs_contain_private_material": False,
            "private_heldout_evaluated": False,
            "remote_inference_executed": False,
        },
        "aggregate_metrics": {
            "raw_response_count": 0,
            "parsed_candidate_count": 0,
            "parse_failure_count": 0,
            "parse_validity_rate": 0.0,
            "public_eval_task_count": 0,
            "public_eval_solve_rate": 0.0,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_pass_rate": 0.0,
            "public_overfit_detection_rate": 1.0,
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
            "local_model_execution_used": False,
            "remote_inference_invoked": False,
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
        "schema_version": "forgeagent.remote_candidate_smoke_preflight_privacy_report.v1",
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

    heldout_summary = read_json(HELDOUT_PROTOCOL_DIR / "summary.json")
    contract_summary = read_json(CONTRACT_DIR / "summary.json")
    runner_summary = read_json(CANDIDATE_RUNNER_DIR / "summary.json")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if not contract_summary["candidate_contract_ready"]:
        raise RuntimeError("model candidate eval contract is not ready")
    if not runner_summary["privacy_scan_passed"]:
        raise RuntimeError("candidate eval runner dry run is not privacy-clean")
    if not heldout_summary["protocol_ready"]:
        raise RuntimeError("heldout-aware protocol is not ready")

    sts_result = run_aws(["sts", "get-caller-identity"])
    s3_result = run_aws(["s3api", "head-bucket", "--bucket", S3_BUCKET])
    sagemaker_endpoints_result = run_aws(["sagemaker", "list-endpoints", "--max-results", "10"])
    sagemaker_models_result = run_aws(["sagemaker", "list-models", "--max-results", "10"])
    bedrock_models_result = run_aws(["bedrock", "list-foundation-models"])

    sts_identity = parse_json_output(sts_result)
    sagemaker_endpoints = parse_json_output(sagemaker_endpoints_result).get("Endpoints", [])
    sagemaker_models = parse_json_output(sagemaker_models_result).get("Models", [])
    bedrock_models = parse_json_output(bedrock_models_result).get("modelSummaries", [])
    bedrock_summary = bedrock_candidate_summary(bedrock_models)

    cloud_preflight = {
        "schema_version": "forgeagent.remote_candidate_smoke_cloud_preflight.v1",
        "aws_profile": AWS_PROFILE,
        "aws_region": AWS_REGION,
        "aws_identity": redact_aws_identity(sts_identity),
        "sts_ok": sts_result["ok"],
        "s3_bucket_access_ok": s3_result["ok"],
        "sagemaker_list_endpoints_ok": sagemaker_endpoints_result["ok"],
        "sagemaker_endpoint_count": len(sagemaker_endpoints),
        "sagemaker_list_models_ok": sagemaker_models_result["ok"],
        "sagemaker_model_count": len(sagemaker_models),
        "bedrock_list_foundation_models_ok": bedrock_models_result["ok"],
        "bedrock": bedrock_summary,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "training_job_launched": False,
        "gpu_required": False,
    }

    remote_execution_plan = {
        "schema_version": "forgeagent.remote_candidate_smoke_execution_plan.v1",
        "name": "remote_candidate_smoke_execution_plan_v1",
        "status": "blocked_until_explicit_remote_inference_approval",
        "allowed_execution_surfaces": [
            "bedrock_on_demand_text_model",
            "sagemaker_endpoint",
            "sagemaker_batch_transform",
            "vllm_http_remote",
        ],
        "disallowed_execution_surfaces": [
            "local_transformers",
            "ollama_local",
            "local_gpu",
            "local_cpu_model_load",
        ],
        "required_before_execution": [
            "explicit_user_approval_for_remote_inference_cost",
            "selected_model_id_or_endpoint",
            "public_eval_task_set",
            "candidate_raw_output_retention_policy",
            "private_heldout_aggregate_only_gate_confirmation",
        ],
        "next_candidate_model_hint": bedrock_summary.get("selected_public_model_id"),
        "launches_training_job": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
    }

    package = build_blocked_preflight_package(
        heldout_summary=heldout_summary,
        bedrock_summary=bedrock_summary,
        sagemaker_endpoint_count=len(sagemaker_endpoints),
        sagemaker_model_count=len(sagemaker_models),
    )
    contract = build_contract(heldout_summary)
    validation = validate_candidate_package(package, contract, private_task_ids)

    public_report = {
        "schema_version": "forgeagent.public_safe_remote_candidate_smoke_preflight_report.v1",
        "report_name": "remote_candidate_smoke_preflight_v1_public_safe",
        "aws_region": AWS_REGION,
        "sts_ok": cloud_preflight["sts_ok"],
        "s3_bucket_access_ok": cloud_preflight["s3_bucket_access_ok"],
        "sagemaker_endpoint_count": cloud_preflight["sagemaker_endpoint_count"],
        "sagemaker_model_count": cloud_preflight["sagemaker_model_count"],
        "bedrock_list_foundation_models_ok": cloud_preflight["bedrock_list_foundation_models_ok"],
        "bedrock_text_model_count": bedrock_summary["text_model_count"],
        "bedrock_on_demand_text_model_count": bedrock_summary["on_demand_text_model_count"],
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "contract_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "aws_account_id_included": False,
            "private_task_ids_included": False,
            "private_patch_content_included": False,
            "private_hidden_test_content_included": False,
            "candidate_raw_outputs_included": False,
        },
    }

    cloud_preflight_path = OUT_DIR / "cloud_preflight.json"
    remote_execution_plan_path = OUT_DIR / "remote_execution_plan.json"
    package_path = OUT_DIR / "candidate_packages/remote_candidate_smoke_preflight.json"
    validation_path = OUT_DIR / "candidate_validation_result.json"
    public_report_path = OUT_DIR / "public_safe_remote_candidate_smoke_preflight_report.json"
    gate_path = OUT_DIR / "remote_candidate_smoke_preflight_gate_decision.json"

    write_json(cloud_preflight_path, cloud_preflight)
    write_json(remote_execution_plan_path, remote_execution_plan)
    write_json(package_path, package)
    write_json(validation_path, validation)
    write_json(public_report_path, public_report)

    gate = {
        "schema_version": "forgeagent.remote_candidate_smoke_preflight_gate_decision.v1",
        "runner_name": "remote_candidate_smoke_preflight_v1",
        "candidate_contract_ready": contract_summary["candidate_contract_ready"],
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "aws_preflight_ready": all(
            [
                cloud_preflight["sts_ok"],
                cloud_preflight["s3_bucket_access_ok"],
                cloud_preflight["bedrock_list_foundation_models_ok"],
            ]
        ),
        "sagemaker_endpoint_available": len(sagemaker_endpoints) > 0,
        "sagemaker_model_available": len(sagemaker_models) > 0,
        "bedrock_text_models_available": bedrock_summary["text_model_count"] > 0,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_training_blocked": "preflight does not authorize training",
        "reason_release_blocked": "no remote model inference executed and no candidate quality evidence exists",
        "next_required_authorization": "explicit approval before paid remote inference or endpoint launch",
    }
    write_json(gate_path, gate)

    privacy = scan_outputs(
        output_paths=[
            cloud_preflight_path,
            remote_execution_plan_path,
            package_path,
            validation_path,
            public_report_path,
            gate_path,
        ],
        public_report_paths=[public_report_path],
        private_task_ids=private_task_ids,
    )
    privacy_path = OUT_DIR / "remote_candidate_smoke_preflight_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.remote_candidate_smoke_preflight_summary.v1",
        "runner_name": "remote_candidate_smoke_preflight_v1",
        "source_step": "step29_15_candidate_eval_runner_dry_run_v1",
        "candidate_contract_ready": contract_summary["candidate_contract_ready"],
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "aws_preflight_ready": gate["aws_preflight_ready"],
        "sts_ok": cloud_preflight["sts_ok"],
        "s3_bucket_access_ok": cloud_preflight["s3_bucket_access_ok"],
        "sagemaker_endpoint_count": len(sagemaker_endpoints),
        "sagemaker_model_count": len(sagemaker_models),
        "bedrock_text_model_count": bedrock_summary["text_model_count"],
        "bedrock_on_demand_text_model_count": bedrock_summary["on_demand_text_model_count"],
        "candidate_package_count": 1,
        "candidate_package_valid_count": 1 if validation["contract_valid"] else 0,
        "real_model_candidate_evaluated": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "release_gate_passed_count": 1 if validation["release_gate_passed"] else 0,
        "remote_candidate_release_blocked": True,
        "public_safe_report_ready": True,
        "public_safe_private_task_id_leak_count": privacy["public_safe_private_task_id_leak_count"],
        "public_safe_private_content_leak_count": privacy["public_safe_private_content_leak_count"],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_17_remote_code_model_candidate_smoke_eval",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "cloud_preflight": str(cloud_preflight_path),
            "remote_execution_plan": str(remote_execution_plan_path),
            "candidate_package": str(package_path),
            "candidate_validation_result": str(validation_path),
            "public_safe_remote_candidate_smoke_preflight_report": str(public_report_path),
            "remote_candidate_smoke_preflight_gate_decision": str(gate_path),
            "remote_candidate_smoke_preflight_privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("REMOTE_CANDIDATE_SMOKE_PREFLIGHT_V1_OK")


if __name__ == "__main__":
    main()

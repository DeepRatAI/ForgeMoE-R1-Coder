from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STEP27_DIR = PROJECT_ROOT / "results/local/local_adapter_training_plan_v0"
STEP28_DIR = PROJECT_ROOT / "results/local/local_lora_sft_dry_run_v0"
OUT_DIR = PROJECT_ROOT / "reports/local/step29_0_gpu_training_preflight"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def shell_json(command: list[str]) -> Any:
    output = subprocess.check_output(command, text=True)
    return json.loads(output)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bucket = os.environ["S3_BUCKET"]
    region = os.environ["AWS_REGION"]
    role_arn = os.environ["SAGEMAKER_ROLE_ARN"]

    training_manifest = read_json(STEP27_DIR / "training_manifest.json")
    dry_run_report = read_json(STEP28_DIR / "dry_run_report.json")
    architecture_report = read_json(STEP28_DIR / "architecture_report.json")
    training_job_spec = read_json(STEP28_DIR / "training_job_spec_sagemaker.json")

    identity = shell_json(["aws", "sts", "get-caller-identity"])
    training_jobs = shell_json(["aws", "sagemaker", "list-training-jobs", "--max-results", "1"])

    launch_plan = {
        "schema_version": "forgeagent.gpu_lora_sft_launch_plan.v0",
        "plan_name": "gpu_lora_sft_preflight_v0",
        "launch_training_job": False,
        "requires_explicit_approval_before_launch": True,
        "reason_training_not_launched": "cost_gate_active",
        "aws": {
            "region": region,
            "account": identity.get("Account"),
            "caller_arn": identity.get("Arn"),
            "sagemaker_role_arn": role_arn,
            "sagemaker_api_probe_ok": "TrainingJobSummaries" in training_jobs,
        },
        "model": {
            "base_model_id": dry_run_report["model_id"],
            "real_config_model_type": architecture_report["real_config_model_type"],
            "adapter_type": "LoRA",
            "target_modules": dry_run_report["target_modules"],
            "trainable_parameters_in_tiny_probe": dry_run_report["parameter_counts"]["trainable_parameters"],
        },
        "dataset": {
            "train_rows": training_manifest["train_rows"],
            "eval_rows": training_manifest["eval_rows"],
            "train_s3": f"s3://{bucket}/results/27_local_adapter_training_plan/v0/train.jsonl",
            "eval_s3": f"s3://{bucket}/results/27_local_adapter_training_plan/v0/eval.jsonl",
            "source_training_manifest_s3": f"s3://{bucket}/results/27_local_adapter_training_plan/v0/training_manifest.json",
        },
        "recommended_training_job": {
            "job_name_prefix": "forgemoe-step29-qwen-0-5b-lora-sft",
            "instance_candidates": [
                {
                    "instance_type": "ml.g5.xlarge",
                    "gpu": "A10G",
                    "note": "preferred first managed GPU target for 0.5B LoRA SFT"
                },
                {
                    "instance_type": "ml.g4dn.xlarge",
                    "gpu": "T4",
                    "note": "possible fallback if available and quota permits"
                }
            ],
            "hyperparameters": training_job_spec["hyperparameters"],
            "input_s3": training_job_spec["dataset_s3"],
            "output_s3_prefix": f"s3://{bucket}/models/step29_qwen_0_5b_structured_intent_lora_sft/",
        },
        "promotion_gate": {
            "after_training": [
                "download_or_attach_adapter",
                "run_structured_intent_eval",
                "compare_against_step24_and_step25",
                "only_promote_if_valid_repaired_intent_rate_improves"
            ],
            "not_enough_to_pass": [
                "training_job_completed",
                "loss_decreased_without_eval",
                "adapter_artifact_exists_without_benchmark"
            ]
        }
    }

    risk_register = {
        "schema_version": "forgeagent.gpu_training_risk_register.v0",
        "risks": [
            {
                "risk": "insufficient_gpu_quota",
                "impact": "training job cannot start in AWS",
                "mitigation": "use EC2 GPU, AWS Batch GPU, alternate region, or external portable GPU runner"
            },
            {
                "risk": "dataset_too_small_for_real_improvement",
                "impact": "adapter may overfit or show no useful gain",
                "mitigation": "treat first run as plumbing validation, then scale dataset"
            },
            {
                "risk": "training_completes_but_agentic_quality_does_not_improve",
                "impact": "no promotion",
                "mitigation": "strict promotion gate against structured-intent and patch-generation benchmarks"
            },
            {
                "risk": "cloudshell_runtime_limit",
                "impact": "cannot run heavy model work locally",
                "mitigation": "CloudShell remains control plane only"
            }
        ]
    }

    write_json(OUT_DIR / "launch_plan.json", launch_plan)
    write_json(OUT_DIR / "risk_register.json", risk_register)

    print(json.dumps(
        {
            "schema_version": launch_plan["schema_version"],
            "plan_name": launch_plan["plan_name"],
            "launch_training_job": launch_plan["launch_training_job"],
            "requires_explicit_approval_before_launch": launch_plan["requires_explicit_approval_before_launch"],
            "region": launch_plan["aws"]["region"],
            "account": launch_plan["aws"]["account"],
            "model": launch_plan["model"]["base_model_id"],
            "train_rows": launch_plan["dataset"]["train_rows"],
            "eval_rows": launch_plan["dataset"]["eval_rows"],
            "target_modules": launch_plan["model"]["target_modules"],
            "sagemaker_api_probe_ok": launch_plan["aws"]["sagemaker_api_probe_ok"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print("GPU_LORA_SFT_LAUNCH_PLAN_OK")


if __name__ == "__main__":
    main()

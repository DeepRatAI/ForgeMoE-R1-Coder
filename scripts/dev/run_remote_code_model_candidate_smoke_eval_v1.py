from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
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


CONTRACT_DIR = PROJECT_ROOT / "results/local/model_candidate_eval_contract_v1"
HELDOUT_PROTOCOL_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
REMOTE_PREFLIGHT_DIR = PROJECT_ROOT / "results/local/remote_candidate_smoke_preflight_v1"
OUT_DIR = PROJECT_ROOT / "results/local/remote_code_model_candidate_smoke_eval_v1"

AWS_PROFILE = os.environ.get("AWS_PROFILE", "forgemoe")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def run_aws(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        ["aws", "--profile", AWS_PROFILE, "--region", AWS_REGION, *args],
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


def build_public_smoke_task(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    repo = root / "repo"
    task_dir = root / "task"

    write_text(repo / "app" / "__init__.py", "")
    write_text(
        repo / "app" / "math_utils.py",
        """def clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return low
    return value
""",
    )
    write_text(
        repo / "tests" / "test_math_utils.py",
        """import unittest

from app.math_utils import clamp


class TestClamp(unittest.TestCase):
    def test_inside_range(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_low_boundary(self):
        self.assertEqual(clamp(-3, 0, 10), 0)

    def test_high_boundary(self):
        self.assertEqual(clamp(13, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
""",
    )
    task = {
        "schema_version": "forgeagent.task.v0",
        "task_id": "public-remote-smoke-clamp-high-boundary",
        "task_type": "unit_bugfix",
        "title": "Fix clamp high-boundary behavior",
        "description": "The clamp function should return high when value is greater than high.",
        "repo_dir": "../repo",
        "test_command": "python3 -B -m unittest discover -s tests",
        "timeout_seconds": 30,
    }
    write_json(task_dir / "task.json", task)
    return task_dir / "task.json"


def select_remote_code_model(models: list[dict[str, Any]]) -> dict[str, Any]:
    text_on_demand = [
        model
        for model in models
        if "TEXT" in model.get("inputModalities", [])
        and "TEXT" in model.get("outputModalities", [])
        and "ON_DEMAND" in model.get("inferenceTypesSupported", [])
        and model.get("modelLifecycle", {}).get("status") in {"ACTIVE", "LEGACY"}
    ]
    preferred_ids = [
        "mistral.mistral-7b-instruct-v0:2",
        "qwen.qwen3-30b-a3b",
        "qwen.qwen3-next-80b-a3b",
        "deepseek.v3.2",
        "openai.gpt-oss-120b-1:0",
    ]
    by_id = {model.get("modelId"): model for model in text_on_demand}
    for model_id in preferred_ids:
        if model_id in by_id:
            return by_id[model_id]
    if text_on_demand:
        return text_on_demand[0]
    raise RuntimeError("No Bedrock on-demand text model is available for remote smoke planning")


def model_size_class(model: dict[str, Any]) -> str:
    text = f"{model.get('modelId', '')} {model.get('modelName', '')}".lower()
    if "7b" in text:
        return "7b"
    if "9b" in text:
        return "9b"
    if "14b" in text:
        return "14b"
    if "12b" in text:
        return "14b"
    return "tiny_smoke"


def build_bedrock_converse_request(
    *,
    model_id: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
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
            "maxTokens": 1024,
            "temperature": 0.0,
            "topP": 1.0,
        },
        "requestMetadata": {
            "forge_step": "step29_17_remote_code_model_candidate_smoke_eval",
            "execution_mode": "prepared_not_invoked",
        },
    }


def build_blocked_candidate_package(
    *,
    selected_model: dict[str, Any],
    heldout_summary: dict[str, Any],
    prompt_hash: str,
    task_id: str,
) -> dict[str, Any]:
    return {
        "candidate_identity": {
            "candidate_id": "remote-code-model-candidate-smoke-eval-prepared",
            "candidate_kind": "remote_code_model_smoke_eval_prepared",
            "created_by_step": "step29_17_remote_code_model_candidate_smoke_eval",
            "is_real_model_candidate": False,
        },
        "model_metadata": {
            "model_id": selected_model["modelId"],
            "model_size_class": model_size_class(selected_model),
            "adapter_name": "BedrockConverseCodeCandidateAdapter",
            "runtime": "bedrock_on_demand",
            "base_or_tuned": "base",
            "revision": selected_model.get("modelLifecycle", {}).get("status", "unknown"),
            "provider": selected_model.get("providerName"),
            "model_name": selected_model.get("modelName"),
        },
        "run_provenance": {
            "git_commit": git_commit(),
            "prompt_contract_version": "remote_code_smoke_prompt_v1",
            "candidate_pipeline_version": "remote_code_model_candidate_smoke_eval_v1",
            "heldout_protocol_version": "heldout_aware_eval_protocol_v1",
            "prompt_sha256": prompt_hash,
            "public_task_id": task_id,
        },
        "generation_config": {
            "max_new_tokens": 1024,
            "temperature": 0.0,
            "top_p": 1.0,
            "do_sample": False,
            "num_return_sequences": 0,
            "seed": 2917,
        },
        "eval_scope": {
            "train_rows_observed": 0,
            "public_eval_task_count": 1,
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
            "public_eval_task_count": 1,
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
        "schema_version": "forgeagent.remote_code_model_smoke_eval_privacy_report.v1",
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
    remote_preflight_summary = read_json(REMOTE_PREFLIGHT_DIR / "summary.json")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if not contract_summary["candidate_contract_ready"]:
        raise RuntimeError("model candidate eval contract is not ready")
    if not heldout_summary["protocol_ready"]:
        raise RuntimeError("heldout-aware protocol is not ready")
    if not remote_preflight_summary["aws_preflight_ready"]:
        raise RuntimeError("remote candidate smoke preflight is not ready")

    task_json = build_public_smoke_task(OUT_DIR / "public_smoke_task_workspace")
    task = AgentTask.from_json_file(task_json)
    task.validate()
    pre_test = run_shell_command(
        task.test_command,
        cwd=task.repo_dir,
        timeout_seconds=task.timeout_seconds,
    )
    if pre_test.passed:
        raise RuntimeError("public smoke task must fail before candidate patch generation")

    messages = build_patch_generation_messages(
        task,
        pre_test_stderr=pre_test.stderr or pre_test.stdout,
        max_files=20,
        max_file_chars=4000,
    )
    prompt_blob = json.dumps(messages, sort_keys=True, ensure_ascii=False)
    prompt_hash = sha256_text(prompt_blob)

    bedrock_result = run_aws(["bedrock", "list-foundation-models"])
    bedrock_models = parse_json_output(bedrock_result).get("modelSummaries", [])
    selected_model = select_remote_code_model(bedrock_models)
    converse_request = build_bedrock_converse_request(
        model_id=selected_model["modelId"],
        messages=messages,
    )
    command_plan = {
        "schema_version": "forgeagent.bedrock_converse_command_plan.v1",
        "status": "prepared_not_executed",
        "command": [
            "aws",
            "--profile",
            AWS_PROFILE,
            "--region",
            AWS_REGION,
            "bedrock-runtime",
            "converse",
            "--cli-input-json",
            "file://bedrock_converse_request.json",
        ],
        "requires_permission": "bedrock:InvokeModel",
        "requires_explicit_cost_approval": True,
        "remote_inference_invoked": False,
    }
    execution_authorization = {
        "schema_version": "forgeagent.remote_code_model_execution_authorization.v1",
        "authorized": False,
        "reason": "remote inference cost approval has not been granted in this step",
        "local_model_execution_allowed": False,
        "remote_inference_invoked": False,
        "training_job_launch_allowed": False,
        "model_release_allowed": False,
    }
    package = build_blocked_candidate_package(
        selected_model=selected_model,
        heldout_summary=heldout_summary,
        prompt_hash=prompt_hash,
        task_id=task.task_id,
    )
    validation = validate_candidate_package(package, build_contract(heldout_summary), private_task_ids)

    prompt_path = OUT_DIR / "bedrock_converse_messages.json"
    request_path = OUT_DIR / "bedrock_converse_request.json"
    command_plan_path = OUT_DIR / "bedrock_converse_command_plan.json"
    execution_authorization_path = OUT_DIR / "execution_authorization.json"
    pretest_path = OUT_DIR / "public_smoke_pretest_result.json"
    package_path = OUT_DIR / "candidate_packages/remote_code_model_candidate_smoke_eval_prepared.json"
    validation_path = OUT_DIR / "candidate_validation_result.json"
    gate_path = OUT_DIR / "remote_code_model_candidate_smoke_eval_gate_decision.json"
    public_report_path = OUT_DIR / "public_safe_remote_code_model_candidate_smoke_eval_report.json"

    write_json(prompt_path, messages)
    write_json(request_path, converse_request)
    write_json(command_plan_path, command_plan)
    write_json(execution_authorization_path, execution_authorization)
    write_json(
        pretest_path,
        {
            "schema_version": "forgeagent.public_smoke_pretest_result.v1",
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
    write_json(package_path, package)
    write_json(validation_path, validation)

    gate = {
        "schema_version": "forgeagent.remote_code_model_candidate_smoke_eval_gate_decision.v1",
        "runner_name": "remote_code_model_candidate_smoke_eval_v1",
        "candidate_contract_ready": contract_summary["candidate_contract_ready"],
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "remote_preflight_ready": remote_preflight_summary["aws_preflight_ready"],
        "public_smoke_task_ready": True,
        "public_smoke_pretest_failed": not pre_test.passed,
        "bedrock_model_inventory_ok": bedrock_result["ok"],
        "selected_model_id": selected_model["modelId"],
        "selected_model_provider": selected_model.get("providerName"),
        "bedrock_converse_request_ready": True,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_execution_blocked": "explicit remote inference cost approval is required",
        "reason_release_blocked": "candidate request is prepared but no remote inference or patch verification has run",
    }
    write_json(gate_path, gate)

    public_report = {
        "schema_version": "forgeagent.public_safe_remote_code_model_smoke_eval_report.v1",
        "report_name": "remote_code_model_candidate_smoke_eval_v1_public_safe",
        "runner_name": "remote_code_model_candidate_smoke_eval_v1",
        "public_smoke_task_count": 1,
        "public_smoke_pretest_failed": not pre_test.passed,
        "selected_model_id": selected_model["modelId"],
        "selected_model_provider": selected_model.get("providerName"),
        "selected_model_name": selected_model.get("modelName"),
        "bedrock_converse_request_ready": True,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "private_task_ids_included": False,
            "private_patch_content_included": False,
            "private_hidden_test_content_included": False,
            "prompt_content_included": False,
            "candidate_raw_outputs_included": False,
        },
    }
    write_json(public_report_path, public_report)

    privacy = scan_outputs(
        output_paths=[
            prompt_path,
            request_path,
            command_plan_path,
            execution_authorization_path,
            pretest_path,
            package_path,
            validation_path,
            gate_path,
            public_report_path,
        ],
        public_report_paths=[public_report_path],
        private_task_ids=private_task_ids,
    )
    privacy_path = OUT_DIR / "remote_code_model_candidate_smoke_eval_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.remote_code_model_candidate_smoke_eval_summary.v1",
        "runner_name": "remote_code_model_candidate_smoke_eval_v1",
        "source_step": "step29_16_remote_candidate_smoke_preflight_v1",
        "candidate_contract_ready": contract_summary["candidate_contract_ready"],
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "remote_preflight_ready": remote_preflight_summary["aws_preflight_ready"],
        "public_smoke_task_count": 1,
        "public_smoke_pretest_failed_count": 1 if not pre_test.passed else 0,
        "bedrock_model_inventory_ok": bedrock_result["ok"],
        "selected_model_id": selected_model["modelId"],
        "selected_model_provider": selected_model.get("providerName"),
        "bedrock_converse_request_ready": True,
        "execution_authorized": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "candidate_package_count": 1,
        "candidate_package_valid_count": 1 if validation["contract_valid"] else 0,
        "release_gate_passed_count": 1 if validation["release_gate_passed"] else 0,
        "remote_code_candidate_release_blocked": True,
        "public_safe_report_ready": True,
        "public_safe_private_task_id_leak_count": privacy["public_safe_private_task_id_leak_count"],
        "public_safe_private_content_leak_count": privacy["public_safe_private_content_leak_count"],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_18_remote_inference_cost_approval_and_candidate_eval",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "bedrock_converse_messages": str(prompt_path),
            "bedrock_converse_request": str(request_path),
            "bedrock_converse_command_plan": str(command_plan_path),
            "execution_authorization": str(execution_authorization_path),
            "public_smoke_pretest_result": str(pretest_path),
            "candidate_package": str(package_path),
            "candidate_validation_result": str(validation_path),
            "gate_decision": str(gate_path),
            "public_safe_report": str(public_report_path),
            "privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("REMOTE_CODE_MODEL_CANDIDATE_SMOKE_EVAL_V1_OK")


if __name__ == "__main__":
    main()

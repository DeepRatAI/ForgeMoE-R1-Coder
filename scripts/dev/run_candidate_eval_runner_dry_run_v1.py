from __future__ import annotations

from pathlib import Path
import json
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
TRAJECTORY_DIR = PROJECT_ROOT / "results/local/agentic_trajectory_recorder_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
OUT_DIR = PROJECT_ROOT / "results/local/candidate_eval_runner_dry_run_v1"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def build_dry_run_candidate_package(
    heldout_summary: dict[str, Any],
    trajectory_summary: dict[str, Any],
) -> dict[str, Any]:
    public_eval_task_count = trajectory_summary["eval_trajectory_rows"]
    private_task_count = heldout_summary["private_heldout_task_count"]

    return {
        "candidate_identity": {
            "candidate_id": "candidate-eval-runner-dry-run-reference",
            "candidate_kind": "dry_run_reference",
            "created_by_step": "step29_15_candidate_eval_runner_dry_run",
            "is_real_model_candidate": False,
        },
        "model_metadata": {
            "model_id": "dry-run/reference-candidate",
            "model_size_class": "tiny_smoke",
            "adapter_name": "DryRunReferenceCandidateAdapter",
            "runtime": "local_transformers",
            "base_or_tuned": "base",
            "revision": "dry-run",
        },
        "run_provenance": {
            "git_commit": git_commit(),
            "prompt_contract_version": "prompt_contract_v1",
            "candidate_pipeline_version": "candidate_generation_pipeline_v0",
            "heldout_protocol_version": "heldout_aware_eval_protocol_v1",
        },
        "generation_config": {
            "max_new_tokens": 1024,
            "temperature": 0.0,
            "top_p": 1.0,
            "do_sample": False,
            "num_return_sequences": 1,
            "seed": 2915,
        },
        "eval_scope": {
            "train_rows_observed": 0,
            "public_eval_task_count": public_eval_task_count,
            "private_heldout_task_count": private_task_count,
            "private_heldout_aggregate_only": True,
            "private_heldout_task_ids_exposed": False,
            "candidate_outputs_contain_private_material": False,
        },
        "aggregate_metrics": {
            "raw_response_count": public_eval_task_count + private_task_count,
            "parsed_candidate_count": public_eval_task_count + private_task_count,
            "parse_failure_count": 0,
            "parse_validity_rate": 1.0,
            "public_eval_task_count": public_eval_task_count,
            "public_eval_solve_rate": 1.0,
            "private_heldout_task_count": private_task_count,
            "private_heldout_pass_rate": 1.0,
            "public_overfit_detection_rate": 1.0,
            "regression_free_patch_rate": 1.0,
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
        },
    }


def build_eval_trace(
    package: dict[str, Any],
    validation: dict[str, Any],
    heldout_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.candidate_eval_trace.v1",
        "runner_name": "candidate_eval_runner_dry_run_v1",
        "candidate_id": package["candidate_identity"]["candidate_id"],
        "events": [
            {
                "index": 1,
                "type": "load_contract",
                "payload": {"contract": "model_candidate_eval_contract_v1"},
            },
            {
                "index": 2,
                "type": "load_heldout_protocol",
                "payload": {
                    "protocol": "heldout_aware_eval_protocol_v1",
                    "protocol_ready": True,
                },
            },
            {
                "index": 3,
                "type": "build_candidate_package",
                "payload": {
                    "candidate_kind": package["candidate_identity"]["candidate_kind"],
                    "private_heldout_aggregate_only": True,
                },
            },
            {
                "index": 4,
                "type": "validate_candidate_package",
                "payload": {
                    "contract_valid": validation["contract_valid"],
                    "release_gate_passed": validation["release_gate_passed"],
                },
            },
            {
                "index": 5,
                "type": "gate_decision",
                "payload": {
                    "training_launch_allowed": False,
                    "model_release_allowed": False,
                    "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
                },
            },
        ],
    }


def build_public_safe_report(package: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    metrics = package["aggregate_metrics"]
    return {
        "schema_version": "forgeagent.public_safe_candidate_eval_dry_run_report.v1",
        "report_name": "candidate_eval_runner_dry_run_v1_public_safe",
        "candidate_id": package["candidate_identity"]["candidate_id"],
        "candidate_kind": package["candidate_identity"]["candidate_kind"],
        "is_real_model_candidate": False,
        "contract_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "public_eval_task_count": metrics["public_eval_task_count"],
        "private_heldout_task_count": metrics["private_heldout_task_count"],
        "parse_validity_rate": metrics["parse_validity_rate"],
        "public_eval_solve_rate": metrics["public_eval_solve_rate"],
        "private_heldout_pass_rate": metrics["private_heldout_pass_rate"],
        "public_overfit_detection_rate": metrics["public_overfit_detection_rate"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "private_task_ids_included": False,
            "private_patch_content_included": False,
            "private_hidden_test_content_included": False,
            "candidate_raw_outputs_included": False,
        },
    }


def scan_outputs(output_paths: list[Path], private_task_ids: set[str]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    private_id_leaks: list[dict[str, Any]] = []
    private_content_markers = ["diff --git", "assertEqual"]
    private_content_leaks: list[dict[str, Any]] = []

    for path in output_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for finding in scan_text_for_secrets(text):
            secret_findings.append({"path": str(path), **finding})
        if path.name.startswith("public_safe"):
            for task_id in private_task_ids:
                if task_id in text:
                    private_id_leaks.append({"path": str(path), "task_id": task_id})
            for marker in private_content_markers:
                if marker in text:
                    private_content_leaks.append({"path": str(path), "marker": marker})

    return {
        "schema_version": "forgeagent.candidate_eval_runner_privacy_report.v1",
        "scanned_paths": [str(path) for path in output_paths],
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
    trajectory_summary = read_json(TRAJECTORY_DIR / "summary.json")
    contract_summary = read_json(CONTRACT_DIR / "summary.json")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if not contract_summary["candidate_contract_ready"]:
        raise RuntimeError("model candidate eval contract is not ready")
    if not heldout_summary["protocol_ready"]:
        raise RuntimeError("heldout-aware protocol is not ready")

    contract = build_contract(heldout_summary)
    package = build_dry_run_candidate_package(heldout_summary, trajectory_summary)
    validation = validate_candidate_package(package, contract, private_task_ids)
    eval_trace = build_eval_trace(package, validation, heldout_summary)
    public_report = build_public_safe_report(package, validation)

    package_path = OUT_DIR / "candidate_packages/candidate_eval_runner_dry_run_reference.json"
    validation_path = OUT_DIR / "candidate_validation_result.json"
    eval_trace_path = OUT_DIR / "candidate_eval_trace.json"
    public_report_path = OUT_DIR / "public_safe_candidate_eval_report.json"
    gate_path = OUT_DIR / "candidate_eval_runner_gate_decision.json"

    write_json(package_path, package)
    write_json(validation_path, validation)
    write_json(eval_trace_path, eval_trace)
    write_json(public_report_path, public_report)

    gate_decision = {
        "schema_version": "forgeagent.candidate_eval_runner_gate_decision.v1",
        "runner_name": "candidate_eval_runner_dry_run_v1",
        "candidate_contract_ready": contract_summary["candidate_contract_ready"],
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "candidate_package_valid": validation["contract_valid"],
        "release_gate_passed": validation["release_gate_passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_training_blocked": "dry-run candidate runner does not authorize training",
        "reason_release_blocked": "dry-run reference is not a real model candidate",
    }
    write_json(gate_path, gate_decision)

    privacy = scan_outputs(
        [package_path, validation_path, eval_trace_path, public_report_path, gate_path],
        private_task_ids,
    )
    privacy_path = OUT_DIR / "runner_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.candidate_eval_runner_dry_run_summary.v1",
        "runner_name": "candidate_eval_runner_dry_run_v1",
        "source_step": "step29_14_model_candidate_eval_contract_v1",
        "candidate_contract_ready": contract_summary["candidate_contract_ready"],
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "candidate_package_count": 1,
        "candidate_package_valid_count": 1 if validation["contract_valid"] else 0,
        "release_gate_passed_count": 1 if validation["release_gate_passed"] else 0,
        "dry_run_candidate_release_blocked": validation["release_gate_passed"] is False,
        "public_safe_report_ready": True,
        "public_safe_private_task_id_leak_count": privacy["public_safe_private_task_id_leak_count"],
        "public_safe_private_content_leak_count": privacy["public_safe_private_content_leak_count"],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_16_real_candidate_smoke_package",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "candidate_package": str(package_path),
            "candidate_validation_result": str(validation_path),
            "candidate_eval_trace": str(eval_trace_path),
            "public_safe_candidate_eval_report": str(public_report_path),
            "candidate_eval_runner_gate_decision": str(gate_path),
            "runner_privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("CANDIDATE_EVAL_RUNNER_DRY_RUN_V1_OK")


if __name__ == "__main__":
    main()

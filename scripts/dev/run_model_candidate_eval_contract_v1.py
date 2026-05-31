from __future__ import annotations

from pathlib import Path
import json
import re
import shutil
import subprocess
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HELDOUT_PROTOCOL_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"
OUT_DIR = PROJECT_ROOT / "results/local/model_candidate_eval_contract_v1"

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\\s*[:=]"),
}

ALLOWED_MODEL_SIZE_CLASSES = {
    "tiny_smoke",
    "3b_smoke",
    "7b",
    "9b",
    "14b",
    "30b_a3b_reference",
}
RELEASE_ELIGIBLE_MODEL_SIZE_CLASSES = {"7b", "9b", "14b"}
ALLOWED_RUNTIMES = {
    "local_transformers",
    "bedrock_on_demand",
    "vllm_http",
    "sagemaker_batch",
    "sagemaker_endpoint",
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


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def scan_text_for_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": name, "count": len(matches)})
    return findings


def build_contract(heldout_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.model_candidate_eval_contract.v1",
        "contract_name": "model_candidate_eval_contract_v1",
        "source_protocol": "step29_13_heldout_aware_eval_protocol_v1",
        "heldout_protocol_ready_required": True,
        "heldout_protocol_ready_observed": heldout_summary["protocol_ready"],
        "candidate_package_required_sections": [
            "candidate_identity",
            "model_metadata",
            "run_provenance",
            "generation_config",
            "eval_scope",
            "aggregate_metrics",
            "privacy_attestation",
            "cost_profile",
        ],
        "required_identity_fields": [
            "candidate_id",
            "candidate_kind",
            "created_by_step",
        ],
        "required_model_metadata_fields": [
            "model_id",
            "model_size_class",
            "adapter_name",
            "runtime",
            "base_or_tuned",
        ],
        "required_provenance_fields": [
            "git_commit",
            "prompt_contract_version",
            "candidate_pipeline_version",
            "heldout_protocol_version",
        ],
        "required_metric_fields": [
            "raw_response_count",
            "parsed_candidate_count",
            "parse_failure_count",
            "parse_validity_rate",
            "public_eval_task_count",
            "public_eval_solve_rate",
            "private_heldout_task_count",
            "private_heldout_pass_rate",
            "public_overfit_detection_rate",
            "regression_free_patch_rate",
        ],
        "privacy_requirements": {
            "private_heldout_used_for_training": False,
            "private_heldout_used_for_prompt_iteration": False,
            "private_task_ids_in_public_report": False,
            "private_patch_content_in_public_report": False,
            "private_hidden_test_content_in_public_report": False,
        },
        "release_gate_thresholds": {
            "parse_validity_rate_min": 0.95,
            "public_eval_solve_rate_min": 0.80,
            "private_heldout_pass_rate_min": 0.80,
            "public_overfit_detection_rate_min": 1.0,
            "regression_free_patch_rate_min": 0.95,
        },
        "release_eligible_model_size_classes": sorted(RELEASE_ELIGIBLE_MODEL_SIZE_CLASSES),
        "cost_boundary": {
            "training_launch_allowed": False,
            "model_release_allowed": False,
            "downloads_large_dataset": False,
            "gpu_required": False,
        },
    }


def build_candidate_schema(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.model_candidate_package_schema.v1",
        "schema_name": "model_candidate_eval_package_v1",
        "required_sections": contract["candidate_package_required_sections"],
        "section_contracts": {
            "candidate_identity": contract["required_identity_fields"],
            "model_metadata": contract["required_model_metadata_fields"],
            "run_provenance": contract["required_provenance_fields"],
            "aggregate_metrics": contract["required_metric_fields"],
        },
        "allowed_model_size_classes": sorted(ALLOWED_MODEL_SIZE_CLASSES),
        "release_eligible_model_size_classes": sorted(RELEASE_ELIGIBLE_MODEL_SIZE_CLASSES),
        "allowed_runtimes": sorted(ALLOWED_RUNTIMES),
        "privacy_requirements": contract["privacy_requirements"],
        "release_gate_thresholds": contract["release_gate_thresholds"],
    }


def build_fixture_candidate_packages(heldout_summary: dict[str, Any]) -> list[dict[str, Any]]:
    base = {
        "candidate_identity": {
            "candidate_id": "contract-fixture-structural-pass",
            "candidate_kind": "contract_fixture",
            "created_by_step": "step29_14_model_candidate_eval_contract",
            "is_real_model_candidate": False,
        },
        "model_metadata": {
            "model_id": "fixture/mock-coder-7b",
            "model_size_class": "7b",
            "adapter_name": "DeterministicContractFixtureAdapter",
            "runtime": "local_transformers",
            "base_or_tuned": "base",
            "revision": "fixture",
        },
        "run_provenance": {
            "git_commit": git_commit(),
            "prompt_contract_version": "prompt_contract_v1",
            "candidate_pipeline_version": "candidate_generation_pipeline_v0",
            "heldout_protocol_version": "heldout_aware_eval_protocol_v1",
        },
        "generation_config": {
            "max_new_tokens": 1024,
            "temperature": 0.2,
            "top_p": 0.95,
            "do_sample": True,
            "num_return_sequences": 8,
            "seed": 2914,
        },
        "eval_scope": {
            "train_rows_observed": 0,
            "public_eval_task_count": 10,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_aggregate_only": True,
            "private_heldout_task_ids_exposed": False,
        },
        "aggregate_metrics": {
            "raw_response_count": 80,
            "parsed_candidate_count": 78,
            "parse_failure_count": 2,
            "parse_validity_rate": 0.975,
            "public_eval_task_count": 10,
            "public_eval_solve_rate": 0.8,
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
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

    private_leak = json.loads(json.dumps(base))
    private_leak["candidate_identity"]["candidate_id"] = "contract-fixture-private-leak-reject"
    private_leak["privacy_attestation"]["private_heldout_used_for_prompt_iteration"] = True
    private_leak["eval_scope"]["private_heldout_task_ids_exposed"] = True
    private_leak["public_report_preview"] = "debug task id forge-private-heldout-clamp-int"

    weak_metrics = json.loads(json.dumps(base))
    weak_metrics["candidate_identity"]["candidate_id"] = "contract-fixture-weak-metrics-reject"
    weak_metrics["aggregate_metrics"]["parse_validity_rate"] = 0.5
    weak_metrics["aggregate_metrics"]["public_eval_solve_rate"] = 0.2
    weak_metrics["aggregate_metrics"]["private_heldout_pass_rate"] = 0.0
    weak_metrics["aggregate_metrics"]["public_overfit_detection_rate"] = 0.0

    missing_provenance = json.loads(json.dumps(base))
    missing_provenance["candidate_identity"]["candidate_id"] = "contract-fixture-missing-provenance-reject"
    del missing_provenance["run_provenance"]["heldout_protocol_version"]

    return [base, private_leak, weak_metrics, missing_provenance]


def validate_candidate_package(
    package: dict[str, Any],
    contract: dict[str, Any],
    private_task_ids: set[str],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for section in contract["candidate_package_required_sections"]:
        if section not in package or not isinstance(package[section], dict):
            errors.append(f"missing_or_invalid_section:{section}")

    for section, required_fields in [
        ("candidate_identity", contract["required_identity_fields"]),
        ("model_metadata", contract["required_model_metadata_fields"]),
        ("run_provenance", contract["required_provenance_fields"]),
        ("aggregate_metrics", contract["required_metric_fields"]),
    ]:
        section_data = package.get(section) or {}
        for field in required_fields:
            if field not in section_data:
                errors.append(f"missing_field:{section}.{field}")

    model_metadata = package.get("model_metadata") or {}
    if model_metadata.get("model_size_class") not in ALLOWED_MODEL_SIZE_CLASSES:
        errors.append("invalid_model_size_class")
    if model_metadata.get("runtime") not in ALLOWED_RUNTIMES:
        errors.append("invalid_runtime")

    privacy = package.get("privacy_attestation") or {}
    for field, expected in contract["privacy_requirements"].items():
        if privacy.get(field) is not expected:
            errors.append(f"privacy_requirement_failed:{field}")

    aggregate_metrics = package.get("aggregate_metrics") or {}
    threshold_failures: list[str] = []
    for metric_name, min_value in {
        "parse_validity_rate": contract["release_gate_thresholds"]["parse_validity_rate_min"],
        "public_eval_solve_rate": contract["release_gate_thresholds"]["public_eval_solve_rate_min"],
        "private_heldout_pass_rate": contract["release_gate_thresholds"]["private_heldout_pass_rate_min"],
        "public_overfit_detection_rate": contract["release_gate_thresholds"][
            "public_overfit_detection_rate_min"
        ],
        "regression_free_patch_rate": contract["release_gate_thresholds"][
            "regression_free_patch_rate_min"
        ],
    }.items():
        value = aggregate_metrics.get(metric_name)
        if not isinstance(value, int | float) or value < min_value:
            threshold_failures.append(metric_name)
    for metric_name in threshold_failures:
        errors.append(f"release_threshold_failed:{metric_name}")

    if aggregate_metrics.get("private_heldout_task_count") != 3:
        errors.append("private_heldout_task_count_mismatch")

    package_blob = json.dumps(package, sort_keys=True)
    leaked_private_ids = sorted(task_id for task_id in private_task_ids if task_id in package_blob)
    if leaked_private_ids:
        errors.append("private_task_id_leak")

    for finding in scan_text_for_secrets(package_blob):
        errors.append(f"secret_pattern:{finding['pattern']}")

    is_real_model_candidate = bool((package.get("candidate_identity") or {}).get("is_real_model_candidate"))
    if not is_real_model_candidate:
        warnings.append("fixture_candidate_not_release_eligible")
    release_size_eligible = model_metadata.get("model_size_class") in RELEASE_ELIGIBLE_MODEL_SIZE_CLASSES
    if is_real_model_candidate and not release_size_eligible:
        warnings.append("model_size_class_not_release_eligible")

    contract_valid = not errors
    release_gate_passed = contract_valid and is_real_model_candidate and release_size_eligible

    return {
        "schema_version": "forgeagent.model_candidate_validation_result.v1",
        "candidate_id": (package.get("candidate_identity") or {}).get("candidate_id", "unknown"),
        "contract_valid": contract_valid,
        "release_gate_passed": release_gate_passed,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "error_count": len(errors),
        "errors": errors,
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def scan_protocol_outputs(output_paths: list[Path]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    for path in output_paths:
        if not path.exists():
            continue
        for finding in scan_text_for_secrets(path.read_text(encoding="utf-8")):
            secret_findings.append({"path": str(path), **finding})
    return {
        "schema_version": "forgeagent.model_candidate_contract_privacy_report.v1",
        "scanned_paths": [str(path) for path in output_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "passed": len(secret_findings) == 0,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    heldout_summary = read_json(HELDOUT_PROTOCOL_DIR / "summary.json")
    heldout_gate = read_json(HELDOUT_PROTOCOL_DIR / "heldout_gate_decision.json")
    private_manifest_rows = read_jsonl(
        PROJECT_ROOT
        / "results/local/private_heldout_seed_set_v1/dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    contract = build_contract(heldout_summary)
    candidate_schema = build_candidate_schema(contract)
    fixtures = build_fixture_candidate_packages(heldout_summary)

    contract_path = OUT_DIR / "model_candidate_eval_contract.json"
    schema_path = OUT_DIR / "model_candidate_package_schema.json"
    fixture_dir = OUT_DIR / "fixture_candidate_packages"
    validation_path = OUT_DIR / "fixture_validation_results.jsonl"
    gate_path = OUT_DIR / "candidate_eval_gate_decision.json"
    public_report_path = OUT_DIR / "public_safe_candidate_contract_report.json"

    write_json(contract_path, contract)
    write_json(schema_path, candidate_schema)

    validation_results: list[dict[str, Any]] = []
    for package in fixtures:
        candidate_id = package["candidate_identity"]["candidate_id"]
        write_json(fixture_dir / f"{candidate_id}.json", package)
        result = validate_candidate_package(package, contract, private_task_ids)
        append_jsonl(validation_path, result)
        validation_results.append(result)

    accepted = [row for row in validation_results if row["contract_valid"]]
    rejected = [row for row in validation_results if not row["contract_valid"]]
    release_passed = [row for row in validation_results if row["release_gate_passed"]]

    gate_decision = {
        "schema_version": "forgeagent.model_candidate_eval_gate_decision.v1",
        "gate_name": "model_candidate_eval_contract_v1",
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "heldout_gate_protocol_ready": heldout_gate["protocol_ready"],
        "contract_ready": True,
        "fixture_candidate_count": len(fixtures),
        "accepted_fixture_count": len(accepted),
        "rejected_fixture_count": len(rejected),
        "release_passed_fixture_count": len(release_passed),
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_training_blocked": "contract validates evaluation packages only; no training authorized",
        "reason_release_blocked": "only fixtures were validated; no real model candidate evaluated",
    }
    write_json(gate_path, gate_decision)

    public_report = {
        "schema_version": "forgeagent.public_safe_model_candidate_contract_report.v1",
        "report_name": "model_candidate_eval_contract_v1_public_safe",
        "contract_ready": True,
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "required_candidate_sections": contract["candidate_package_required_sections"],
        "required_metric_fields": contract["required_metric_fields"],
        "release_gate_thresholds": contract["release_gate_thresholds"],
        "fixture_candidate_count": len(fixtures),
        "accepted_fixture_count": len(accepted),
        "rejected_fixture_count": len(rejected),
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "private_task_ids_included": False,
            "private_patch_content_included": False,
            "private_hidden_test_content_included": False,
            "candidate_raw_outputs_included": False,
        },
    }
    write_json(public_report_path, public_report)

    privacy = scan_protocol_outputs([contract_path, schema_path, validation_path, gate_path, public_report_path])
    privacy_path = OUT_DIR / "contract_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.model_candidate_eval_contract_summary.v1",
        "contract_name": "model_candidate_eval_contract_v1",
        "source_step": "step29_13_heldout_aware_eval_protocol_v1",
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "candidate_contract_ready": True,
        "candidate_schema_ready": True,
        "required_section_count": len(contract["candidate_package_required_sections"]),
        "required_metric_count": len(contract["required_metric_fields"]),
        "fixture_candidate_count": len(fixtures),
        "accepted_fixture_count": len(accepted),
        "rejected_fixture_count": len(rejected),
        "release_passed_fixture_count": len(release_passed),
        "private_leak_fixture_rejected": any(
            row["candidate_id"] == "contract-fixture-private-leak-reject" and not row["contract_valid"]
            for row in validation_results
        ),
        "weak_metric_fixture_rejected": any(
            row["candidate_id"] == "contract-fixture-weak-metrics-reject" and not row["contract_valid"]
            for row in validation_results
        ),
        "missing_provenance_fixture_rejected": any(
            row["candidate_id"] == "contract-fixture-missing-provenance-reject"
            and not row["contract_valid"]
            for row in validation_results
        ),
        "public_safe_report_ready": True,
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_15_candidate_eval_runner_dry_run",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "model_candidate_eval_contract": str(contract_path),
            "model_candidate_package_schema": str(schema_path),
            "fixture_validation_results": str(validation_path),
            "candidate_eval_gate_decision": str(gate_path),
            "public_safe_candidate_contract_report": str(public_report_path),
            "contract_privacy_report": str(privacy_path),
            "fixture_candidate_packages": str(fixture_dir),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("MODEL_CANDIDATE_EVAL_CONTRACT_V1_OK")


if __name__ == "__main__":
    main()

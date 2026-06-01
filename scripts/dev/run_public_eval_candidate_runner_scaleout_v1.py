from __future__ import annotations

from pathlib import Path
import json
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
PUBLIC_SUITE_DIR = PROJECT_ROOT / "results/local/public_eval_suite_scaleout_v1"
CONTRACT_DIR = PROJECT_ROOT / "results/local/model_candidate_eval_contract_v1"
HELDOUT_PROTOCOL_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
OUT_DIR = PROJECT_ROOT / "results/local/public_eval_candidate_runner_scaleout_v1"

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


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def aggregate_reference_candidate(
    *,
    candidate_id: str,
    patch_challenge: str,
    oracle_rows: list[dict[str, Any]],
    task_count: int,
) -> dict[str, Any]:
    rows = [row for row in oracle_rows if row["challenge"] == patch_challenge]
    if len(rows) != task_count:
        raise RuntimeError(f"candidate {candidate_id} expected {task_count} rows, found {len(rows)}")

    parsed_count = sum(1 for row in rows if row["patch_check_passed"])
    public_pass_count = sum(1 for row in rows if row["post_public_passed"])
    hidden_pass_count = sum(1 for row in rows if row["post_hidden_passed"])
    regression_free_count = sum(1 for row in rows if row["solved"])
    overfit_caught_count = sum(
        1 for row in rows if row["post_public_passed"] and not row["post_hidden_passed"]
    )

    return {
        "schema_version": "forgeagent.public_eval_reference_candidate_scorecard.v1",
        "candidate_id": candidate_id,
        "candidate_kind": f"reference_{patch_challenge}_patch_suite",
        "patch_challenge": patch_challenge,
        "is_real_model_candidate": False,
        "public_eval_task_count": task_count,
        "raw_response_count": 0,
        "parsed_candidate_count": parsed_count,
        "parse_failure_count": task_count - parsed_count,
        "parse_validity_rate": parsed_count / task_count,
        "public_solved_task_count": public_pass_count,
        "public_eval_solve_rate": public_pass_count / task_count,
        "hidden_oracle_pass_count": hidden_pass_count,
        "hidden_oracle_pass_rate": hidden_pass_count / task_count,
        "public_overfit_detected_task_count": overfit_caught_count,
        "public_overfit_detection_rate": overfit_caught_count / task_count
        if patch_challenge == "public_overfit"
        else 1.0,
        "regression_free_patch_count": regression_free_count,
        "regression_free_patch_rate": regression_free_count / task_count,
        "public_eval_gate_passed": (
            patch_challenge == "golden"
            and public_pass_count == task_count
            and hidden_pass_count == task_count
            and regression_free_count == task_count
        ),
        "public_overfit_gate_failed": patch_challenge == "public_overfit"
        and public_pass_count == task_count
        and hidden_pass_count == 0
        and overfit_caught_count == task_count,
        "rejected_gate_failed": patch_challenge == "rejected" and regression_free_count == 0,
        "patch_content_included": False,
        "hidden_test_content_included": False,
        "raw_model_output_included": False,
    }


def build_candidate_package(
    *,
    scorecard: dict[str, Any],
    heldout_summary: dict[str, Any],
) -> dict[str, Any]:
    metrics = {
        "raw_response_count": scorecard["raw_response_count"],
        "parsed_candidate_count": scorecard["parsed_candidate_count"],
        "parse_failure_count": scorecard["parse_failure_count"],
        "parse_validity_rate": scorecard["parse_validity_rate"],
        "public_eval_task_count": scorecard["public_eval_task_count"],
        "public_eval_solve_rate": scorecard["public_eval_solve_rate"],
        "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
        "private_heldout_pass_rate": 0.0,
        "public_overfit_detection_rate": scorecard["public_overfit_detection_rate"],
        "regression_free_patch_rate": scorecard["regression_free_patch_rate"],
    }
    return {
        "candidate_identity": {
            "candidate_id": scorecard["candidate_id"],
            "candidate_kind": scorecard["candidate_kind"],
            "created_by_step": "step29_21_public_eval_candidate_runner_scaleout",
            "is_real_model_candidate": False,
        },
        "model_metadata": {
            "model_id": f"reference/{scorecard['patch_challenge']}",
            "model_size_class": "tiny_smoke",
            "adapter_name": "DeterministicPublicEvalReferencePatchAdapter",
            "runtime": "local_transformers",
            "base_or_tuned": "base",
            "revision": "reference",
            "local_model_execution_used": False,
        },
        "run_provenance": {
            "git_commit": git_commit(),
            "prompt_contract_version": "not_applicable_public_eval_reference_v1",
            "candidate_pipeline_version": "public_eval_candidate_runner_scaleout_v1",
            "heldout_protocol_version": "heldout_aware_eval_protocol_v1",
            "public_eval_suite_version": "public_eval_suite_scaleout_v1",
            "patch_challenge": scorecard["patch_challenge"],
        },
        "generation_config": {
            "max_new_tokens": 0,
            "temperature": 0.0,
            "top_p": 1.0,
            "do_sample": False,
            "num_return_sequences": 0,
            "seed": 2921,
        },
        "eval_scope": {
            "train_rows_observed": 0,
            "public_eval_task_count": scorecard["public_eval_task_count"],
            "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
            "private_heldout_aggregate_only": True,
            "private_heldout_task_ids_exposed": False,
            "candidate_outputs_contain_private_material": False,
            "private_heldout_evaluated": False,
            "remote_inference_executed": False,
            "local_model_execution_used": False,
        },
        "aggregate_metrics": metrics,
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
        },
    }


def build_public_safe_report(scorecards: list[dict[str, Any]], validations: list[dict[str, Any]]) -> dict[str, Any]:
    by_candidate = {row["candidate_id"]: row for row in scorecards}
    return {
        "schema_version": "forgeagent.public_safe_public_eval_candidate_runner_report.v1",
        "report_name": "public_eval_candidate_runner_scaleout_v1_public_safe",
        "reference_candidate_count": len(scorecards),
        "public_eval_task_count": scorecards[0]["public_eval_task_count"],
        "public_eval_gate_passed_candidate_count": sum(
            1 for row in scorecards if row["public_eval_gate_passed"]
        ),
        "public_overfit_candidate_detected_count": sum(
            1 for row in scorecards if row["public_overfit_gate_failed"]
        ),
        "rejected_candidate_failed_count": sum(1 for row in scorecards if row["rejected_gate_failed"]),
        "model_candidate_contract_valid_count": sum(1 for row in validations if row["contract_valid"]),
        "release_gate_passed_count": sum(1 for row in validations if row["release_gate_passed"]),
        "candidate_summaries": [
            {
                "candidate_id": validation["candidate_id"],
                "public_eval_solve_rate": by_candidate[validation["candidate_id"]][
                    "public_eval_solve_rate"
                ],
                "hidden_oracle_pass_rate": by_candidate[validation["candidate_id"]][
                    "hidden_oracle_pass_rate"
                ],
                "public_overfit_detection_rate": by_candidate[validation["candidate_id"]][
                    "public_overfit_detection_rate"
                ],
                "regression_free_patch_rate": by_candidate[validation["candidate_id"]][
                    "regression_free_patch_rate"
                ],
                "public_eval_gate_passed": by_candidate[validation["candidate_id"]][
                    "public_eval_gate_passed"
                ],
                "model_candidate_contract_valid": validation["contract_valid"],
                "release_gate_passed": validation["release_gate_passed"],
            }
            for validation in validations
        ],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "task_level_public_details_included": False,
            "patch_content_included": False,
            "hidden_test_content_included": False,
            "private_task_ids_included": False,
            "candidate_raw_outputs_included": False,
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
    patch_or_test_leaks: list[dict[str, Any]] = []
    leak_markers = ["diff --git", "assertEqual", "def "]
    for path in output_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for finding in scan_text_for_secrets(text):
            secret_findings.append({"path": str(path), **finding})
        for pattern_name, pattern in SECRET_PATTERNS.items():
            matches = list(pattern.finditer(text))
            if matches:
                secret_findings.append({"path": str(path), "pattern": pattern_name, "count": len(matches)})
    for path in public_report_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for task_id in private_task_ids:
            if task_id in text:
                private_id_leaks.append({"path": str(path), "task_id": task_id})
        for marker in leak_markers:
            if marker in text:
                patch_or_test_leaks.append({"path": str(path), "marker": marker})
    return {
        "schema_version": "forgeagent.public_eval_candidate_runner_privacy_report.v1",
        "scanned_paths": [str(path) for path in output_paths],
        "public_report_paths": [str(path) for path in public_report_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "public_safe_private_task_id_leak_count": len(private_id_leaks),
        "public_safe_private_task_id_leaks": private_id_leaks,
        "public_safe_patch_or_test_content_leak_count": len(patch_or_test_leaks),
        "public_safe_patch_or_test_content_leaks": patch_or_test_leaks,
        "passed": len(secret_findings) == 0
        and len(private_id_leaks) == 0
        and len(patch_or_test_leaks) == 0,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    public_suite_summary = read_json(PUBLIC_SUITE_DIR / "summary.json")
    contract_summary = read_json(CONTRACT_DIR / "summary.json")
    heldout_summary = read_json(HELDOUT_PROTOCOL_DIR / "summary.json")
    oracle_rows = read_jsonl(PUBLIC_SUITE_DIR / "public_eval_oracle_results.jsonl")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if public_suite_summary["verified_public_eval_task_count"] != public_suite_summary["public_eval_task_count"]:
        raise RuntimeError("public eval suite is not fully verified")
    if not contract_summary["candidate_contract_ready"]:
        raise RuntimeError("model candidate eval contract is not ready")
    if not heldout_summary["protocol_ready"]:
        raise RuntimeError("heldout-aware protocol is not ready")

    task_count = public_suite_summary["public_eval_task_count"]
    scorecards = [
        aggregate_reference_candidate(
            candidate_id="public-eval-reference-golden",
            patch_challenge="golden",
            oracle_rows=oracle_rows,
            task_count=task_count,
        ),
        aggregate_reference_candidate(
            candidate_id="public-eval-reference-rejected",
            patch_challenge="rejected",
            oracle_rows=oracle_rows,
            task_count=task_count,
        ),
        aggregate_reference_candidate(
            candidate_id="public-eval-reference-public-overfit",
            patch_challenge="public_overfit",
            oracle_rows=oracle_rows,
            task_count=task_count,
        ),
    ]

    contract = build_contract(heldout_summary)
    package_dir = OUT_DIR / "candidate_packages"
    scorecard_path = OUT_DIR / "reference_candidate_scorecards.jsonl"
    validation_path = OUT_DIR / "candidate_validation_results.jsonl"
    validations: list[dict[str, Any]] = []

    for scorecard in scorecards:
        package = build_candidate_package(scorecard=scorecard, heldout_summary=heldout_summary)
        validation = validate_candidate_package(package, contract, private_task_ids)
        validations.append(validation)
        write_json(package_dir / f"{scorecard['candidate_id']}.json", package)
        append_jsonl(scorecard_path, scorecard)
        append_jsonl(validation_path, validation)

    eval_trace = {
        "schema_version": "forgeagent.public_eval_candidate_runner_trace.v1",
        "runner_name": "public_eval_candidate_runner_scaleout_v1",
        "events": [
            {"index": 1, "type": "load_public_eval_suite", "payload": {"task_count": task_count}},
            {
                "index": 2,
                "type": "score_reference_candidates",
                "payload": {"reference_candidate_count": len(scorecards)},
            },
            {
                "index": 3,
                "type": "validate_candidate_packages",
                "payload": {
                    "contract_valid_count": sum(1 for row in validations if row["contract_valid"]),
                    "release_gate_passed_count": sum(1 for row in validations if row["release_gate_passed"]),
                },
            },
            {
                "index": 4,
                "type": "gate_decision",
                "payload": {
                    "training_launch_allowed": False,
                    "model_release_allowed": False,
                    "remote_inference_invoked": False,
                    "local_model_execution_used": False,
                },
            },
        ],
    }
    eval_trace_path = OUT_DIR / "public_eval_candidate_runner_trace.json"
    write_json(eval_trace_path, eval_trace)

    public_report = build_public_safe_report(scorecards, validations)
    public_report_path = OUT_DIR / "public_safe_public_eval_candidate_runner_report.json"
    write_json(public_report_path, public_report)

    gate = {
        "schema_version": "forgeagent.public_eval_candidate_runner_gate_decision.v1",
        "runner_name": "public_eval_candidate_runner_scaleout_v1",
        "public_eval_suite_ready": True,
        "public_eval_task_count": task_count,
        "reference_candidate_count": len(scorecards),
        "golden_reference_public_eval_gate_passed": scorecards[0]["public_eval_gate_passed"],
        "rejected_reference_failed": scorecards[1]["rejected_gate_failed"],
        "public_overfit_reference_detected": scorecards[2]["public_overfit_gate_failed"],
        "model_candidate_contract_valid_count": sum(1 for row in validations if row["contract_valid"]),
        "release_gate_passed_count": sum(1 for row in validations if row["release_gate_passed"]),
        "candidate_eval_runner_ready": True,
        "real_model_candidate_evaluated": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_release_blocked": "reference public eval candidates are not real model candidates and no private heldout aggregate candidate result exists",
    }
    gate_path = OUT_DIR / "public_eval_candidate_runner_gate_decision.json"
    write_json(gate_path, gate)

    privacy = scan_outputs(
        output_paths=[scorecard_path, validation_path, eval_trace_path, public_report_path, gate_path],
        public_report_paths=[public_report_path],
        private_task_ids=private_task_ids,
    )
    privacy_path = OUT_DIR / "public_eval_candidate_runner_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.public_eval_candidate_runner_scaleout_summary.v1",
        "runner_name": "public_eval_candidate_runner_scaleout_v1",
        "source_step": "step29_20_public_eval_suite_scaleout_v1",
        "public_eval_suite_ready": True,
        "public_eval_task_count": task_count,
        "reference_candidate_count": len(scorecards),
        "golden_reference_public_eval_gate_passed": scorecards[0]["public_eval_gate_passed"],
        "golden_reference_public_eval_solve_rate": scorecards[0]["public_eval_solve_rate"],
        "golden_reference_hidden_oracle_pass_rate": scorecards[0]["hidden_oracle_pass_rate"],
        "rejected_reference_failed": scorecards[1]["rejected_gate_failed"],
        "rejected_reference_public_eval_solve_rate": scorecards[1]["public_eval_solve_rate"],
        "rejected_reference_hidden_oracle_pass_rate": scorecards[1]["hidden_oracle_pass_rate"],
        "rejected_reference_regression_free_patch_rate": scorecards[1]["regression_free_patch_rate"],
        "public_overfit_reference_detected": scorecards[2]["public_overfit_gate_failed"],
        "public_overfit_reference_public_eval_solve_rate": scorecards[2]["public_eval_solve_rate"],
        "public_overfit_reference_hidden_oracle_pass_rate": scorecards[2]["hidden_oracle_pass_rate"],
        "model_candidate_contract_valid_count": gate["model_candidate_contract_valid_count"],
        "release_gate_passed_count": gate["release_gate_passed_count"],
        "candidate_eval_runner_ready": True,
        "real_model_candidate_evaluated": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "public_safe_report_ready": True,
        "public_safe_private_task_id_leak_count": privacy["public_safe_private_task_id_leak_count"],
        "public_safe_patch_or_test_content_leak_count": privacy[
            "public_safe_patch_or_test_content_leak_count"
        ],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "next_recommended_step": "step29_22_authorized_remote_candidate_eval_or_public_eval_batch_adapter",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "reference_candidate_scorecards": str(scorecard_path),
            "candidate_validation_results": str(validation_path),
            "candidate_packages": str(package_dir),
            "eval_trace": str(eval_trace_path),
            "gate_decision": str(gate_path),
            "public_safe_report": str(public_report_path),
            "privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("PUBLIC_EVAL_CANDIDATE_RUNNER_SCALEOUT_V1_OK")


if __name__ == "__main__":
    main()

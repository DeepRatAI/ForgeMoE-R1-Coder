from __future__ import annotations

from pathlib import Path
import hashlib
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
STEP29_23_DIR = PROJECT_ROOT / "results/local/public_eval_remote_batch_execution_v1"
HELDOUT_PROTOCOL_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"
PRIVATE_SEED_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
OUT_DIR = PROJECT_ROOT / "results/local/private_heldout_aggregate_candidate_eval_gate_v1"
EVIDENCE_PATH = PROJECT_ROOT / "configs/eval/private_heldout_aggregate_candidate_eval_evidence_v1.json"

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\\s*[:=]"),
}
DISALLOWED_EVIDENCE_KEYS = {
    "task_id",
    "task_ids",
    "task_results",
    "per_task_results",
    "patch",
    "patches",
    "patch_content",
    "hidden_tests",
    "hidden_test_content",
    "prompt",
    "prompts",
    "raw_output",
    "raw_outputs",
    "raw_model_output",
    "raw_model_outputs",
}
DISALLOWED_PUBLIC_MARKERS = [
    "diff --git",
    "assertEqual",
    "hidden_tests",
    "repo_before",
    "raw_model_output",
]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


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


def load_optional_evidence() -> tuple[dict[str, Any] | None, str | None]:
    if EVIDENCE_PATH.exists():
        return read_json(EVIDENCE_PATH), str(EVIDENCE_PATH)
    return None, None


def walk_keys(data: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            keys.add(str(key))
            keys.update(walk_keys(value))
    elif isinstance(data, list):
        for item in data:
            keys.update(walk_keys(item))
    return keys


def validate_aggregate_evidence(
    *,
    evidence: dict[str, Any] | None,
    evidence_source: str | None,
    candidate_package: dict[str, Any],
    candidate_package_sha256: str,
    step23_summary: dict[str, Any],
    heldout_summary: dict[str, Any],
    private_task_ids: set[str],
) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "schema_version": "forgeagent.private_heldout_aggregate_evidence_validation.v1",
        "evidence_present": evidence is not None,
        "evidence_source": evidence_source,
        "candidate_id_matches": False,
        "candidate_package_sha256_matches": False,
        "public_batch_request_sha256_matches": False,
        "heldout_protocol_version_matches": False,
        "private_heldout_task_count_matches": False,
        "aggregate_only_declared": False,
        "task_level_results_absent": False,
        "private_content_absent": False,
        "private_task_id_leak_count": 0,
        "secret_finding_count": 0,
        "disallowed_key_count": 0,
        "private_heldout_pass_rate_valid": False,
        "private_heldout_pass_count_valid": False,
        "private_heldout_pass_rate": 0.0,
        "private_heldout_pass_count": 0,
        "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
        "evidence_valid": False,
        "failed_checks": [],
    }
    if evidence is None:
        checks["failed_checks"] = ["evidence_present"]
        return checks

    candidate_id = candidate_package["candidate_identity"]["candidate_id"]
    checks["candidate_id_matches"] = evidence.get("candidate_id") == candidate_id
    checks["candidate_package_sha256_matches"] = (
        evidence.get("candidate_package_sha256") == candidate_package_sha256
    )
    checks["public_batch_request_sha256_matches"] = (
        evidence.get("public_batch_request_sha256") == step23_summary["batch_request_sha256"]
    )
    checks["heldout_protocol_version_matches"] = (
        evidence.get("heldout_protocol_version") == "heldout_aware_eval_protocol_v1"
    )
    task_count = evidence.get("private_heldout_task_count")
    checks["private_heldout_task_count_matches"] = task_count == heldout_summary["private_heldout_task_count"]
    checks["aggregate_only_declared"] = evidence.get("aggregate_only") is True

    disallowed_keys = sorted(walk_keys(evidence) & DISALLOWED_EVIDENCE_KEYS)
    checks["disallowed_keys"] = disallowed_keys
    checks["disallowed_key_count"] = len(disallowed_keys)
    checks["task_level_results_absent"] = len(disallowed_keys) == 0

    evidence_blob = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
    private_id_leaks = sorted(task_id for task_id in private_task_ids if task_id in evidence_blob)
    secret_findings = scan_text_for_secrets(evidence_blob)
    for pattern_name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(evidence_blob))
        if matches:
            secret_findings.append({"pattern": pattern_name, "count": len(matches)})
    checks["private_task_id_leak_count"] = len(private_id_leaks)
    checks["private_content_absent"] = len(private_id_leaks) == 0 and not any(
        marker in evidence_blob for marker in DISALLOWED_PUBLIC_MARKERS
    )
    checks["secret_finding_count"] = len(secret_findings)

    pass_count = evidence.get("private_heldout_pass_count")
    pass_rate = evidence.get("private_heldout_pass_rate")
    checks["private_heldout_pass_count_valid"] = (
        isinstance(pass_count, int) and isinstance(task_count, int) and 0 <= pass_count <= task_count
    )
    checks["private_heldout_pass_rate_valid"] = (
        isinstance(pass_rate, int | float)
        and isinstance(pass_count, int)
        and isinstance(task_count, int)
        and task_count > 0
        and abs(float(pass_rate) - (pass_count / task_count)) < 1e-9
    )
    if isinstance(pass_count, int):
        checks["private_heldout_pass_count"] = pass_count
    if isinstance(pass_rate, int | float):
        checks["private_heldout_pass_rate"] = float(pass_rate)

    required = [
        "evidence_present",
        "candidate_id_matches",
        "candidate_package_sha256_matches",
        "public_batch_request_sha256_matches",
        "heldout_protocol_version_matches",
        "private_heldout_task_count_matches",
        "aggregate_only_declared",
        "task_level_results_absent",
        "private_content_absent",
        "private_heldout_pass_count_valid",
        "private_heldout_pass_rate_valid",
    ]
    failed = [name for name in required if checks.get(name) is not True]
    if checks["secret_finding_count"] != 0:
        failed.append("secret_finding_count")
    checks["failed_checks"] = failed
    checks["evidence_valid"] = not failed
    return checks


def build_candidate_with_private_aggregate(
    *,
    candidate_package: dict[str, Any],
    evidence_validation: dict[str, Any],
) -> dict[str, Any]:
    enriched = json.loads(json.dumps(candidate_package))
    if evidence_validation["evidence_valid"]:
        enriched["eval_scope"]["private_heldout_evaluated"] = True
        enriched["eval_scope"]["private_heldout_aggregate_only"] = True
        enriched["eval_scope"]["private_heldout_task_ids_exposed"] = False
        enriched["aggregate_metrics"]["private_heldout_task_count"] = evidence_validation[
            "private_heldout_task_count"
        ]
        enriched["aggregate_metrics"]["private_heldout_pass_rate"] = evidence_validation[
            "private_heldout_pass_rate"
        ]
        enriched["aggregate_metrics"]["private_heldout_pass_count"] = evidence_validation[
            "private_heldout_pass_count"
        ]
        enriched["run_provenance"]["private_heldout_aggregate_gate_version"] = (
            "private_heldout_aggregate_candidate_eval_gate_v1"
        )
        enriched["run_provenance"]["private_heldout_aggregate_evidence_sha256"] = sha256_json(
            {
                "candidate_id": enriched["candidate_identity"]["candidate_id"],
                "candidate_package_sha256": evidence_validation["candidate_package_sha256_matches"],
                "private_heldout_pass_rate": evidence_validation["private_heldout_pass_rate"],
                "private_heldout_pass_count": evidence_validation["private_heldout_pass_count"],
            }
        )
    return enriched


def scan_outputs(*, paths: list[Path], public_report_paths: list[Path], private_task_ids: set[str]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    private_task_id_leaks: list[dict[str, Any]] = []
    public_content_leaks: list[dict[str, Any]] = []

    for path in paths:
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
                private_task_id_leaks.append({"path": str(path), "task_id": task_id})

    for path in public_report_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in DISALLOWED_PUBLIC_MARKERS:
            if marker in text:
                public_content_leaks.append({"path": str(path), "marker": marker})

    return {
        "schema_version": "forgeagent.private_heldout_aggregate_candidate_eval_privacy_report.v1",
        "scanned_paths": [str(path) for path in paths],
        "public_report_paths": [str(path) for path in public_report_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "private_task_id_leak_count": len(private_task_id_leaks),
        "private_task_id_leaks": private_task_id_leaks,
        "public_report_content_leak_count": len(public_content_leaks),
        "public_report_content_leaks": public_content_leaks,
        "passed": len(secret_findings) == 0
        and len(private_task_id_leaks) == 0
        and len(public_content_leaks) == 0,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    step23_summary = read_json(STEP29_23_DIR / "summary.json")
    candidate_package = read_json(
        STEP29_23_DIR / "candidate_packages/public_eval_remote_batch_execution_candidate.json"
    )
    step23_validation = read_json(STEP29_23_DIR / "candidate_validation_result.json")
    heldout_summary = read_json(HELDOUT_PROTOCOL_DIR / "summary.json")
    heldout_gate = read_json(HELDOUT_PROTOCOL_DIR / "heldout_gate_decision.json")
    private_summary = read_json(PRIVATE_SEED_DIR / "summary.json")
    private_isolation = read_json(PRIVATE_SEED_DIR / "isolation_report.json")
    private_manifest_rows = read_jsonl(
        PRIVATE_SEED_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    private_task_ids = {row["task_id"] for row in private_manifest_rows}

    if not step23_summary["source_step_ready"]:
        raise RuntimeError("Step 29.23 source step is not ready")
    if not heldout_summary["protocol_ready"]:
        raise RuntimeError("heldout-aware protocol is not ready")
    if not heldout_gate["protocol_ready"]:
        raise RuntimeError("heldout gate is not ready")
    if not private_summary["isolation_scan_passed"] or not private_isolation["passed"]:
        raise RuntimeError("private heldout isolation is not passing")

    candidate_package_sha256 = sha256_json(candidate_package)
    evidence, evidence_source = load_optional_evidence()
    evidence_requirement = {
        "schema_version": "forgeagent.private_heldout_aggregate_evidence_requirement.v1",
        "accepted_evidence_file": str(EVIDENCE_PATH),
        "required_candidate_id": candidate_package["candidate_identity"]["candidate_id"],
        "required_candidate_package_sha256": candidate_package_sha256,
        "required_public_batch_request_sha256": step23_summary["batch_request_sha256"],
        "required_heldout_protocol_version": "heldout_aware_eval_protocol_v1",
        "required_private_heldout_task_count": heldout_summary["private_heldout_task_count"],
        "aggregate_only_required": True,
        "task_ids_allowed": False,
        "task_level_results_allowed": False,
        "patch_content_allowed": False,
        "hidden_test_content_allowed": False,
        "raw_model_outputs_allowed": False,
    }
    evidence_validation = validate_aggregate_evidence(
        evidence=evidence,
        evidence_source=evidence_source,
        candidate_package=candidate_package,
        candidate_package_sha256=candidate_package_sha256,
        step23_summary=step23_summary,
        heldout_summary=heldout_summary,
        private_task_ids=private_task_ids,
    )
    enriched_candidate = build_candidate_with_private_aggregate(
        candidate_package=candidate_package,
        evidence_validation=evidence_validation,
    )
    enriched_validation = validate_candidate_package(
        enriched_candidate,
        build_contract(heldout_summary),
        private_task_ids,
    )

    evidence_requirement_path = OUT_DIR / "private_heldout_aggregate_evidence_requirement.json"
    evidence_observed_path = OUT_DIR / "private_heldout_aggregate_evidence_observed.json"
    evidence_validation_path = OUT_DIR / "private_heldout_aggregate_evidence_validation.json"
    candidate_package_path = OUT_DIR / "candidate_packages/private_heldout_aggregate_candidate.json"
    candidate_validation_path = OUT_DIR / "candidate_validation_result.json"
    gate_decision_path = OUT_DIR / "private_heldout_aggregate_candidate_eval_gate_decision.json"
    public_report_path = OUT_DIR / "public_safe_private_heldout_aggregate_candidate_eval_report.json"

    write_json(evidence_requirement_path, evidence_requirement)
    if evidence is not None:
        write_json(evidence_observed_path, evidence)
    else:
        write_json(
            evidence_observed_path,
            {
                "schema_version": "forgeagent.private_heldout_aggregate_evidence_observed.v1",
                "evidence_present": False,
                "reason": "aggregate evidence file is absent",
            },
        )
    write_json(evidence_validation_path, evidence_validation)
    write_json(candidate_package_path, enriched_candidate)
    write_json(candidate_validation_path, enriched_validation)

    public_gate_ready = (
        step23_summary["remote_inference_invoked_count"] > 0
        and step23_summary["patch_extracted_count"] == step23_summary["public_eval_task_count"]
        and step23_summary["public_tests_passed_count"] >= int(0.8 * step23_summary["public_eval_task_count"])
        and step23_summary["hidden_oracle_passed_count"] >= int(0.8 * step23_summary["public_eval_task_count"])
    )
    release_gate_passed = (
        public_gate_ready
        and evidence_validation["evidence_valid"]
        and enriched_validation["contract_valid"]
        and enriched_validation["release_gate_passed"]
    )

    gate_decision = {
        "schema_version": "forgeagent.private_heldout_aggregate_candidate_eval_gate_decision.v1",
        "gate_name": "private_heldout_aggregate_candidate_eval_gate_v1",
        "source_step_ready": True,
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "private_isolation_passed": private_isolation["passed"],
        "candidate_id": candidate_package["candidate_identity"]["candidate_id"],
        "candidate_package_sha256": candidate_package_sha256,
        "public_batch_request_sha256": step23_summary["batch_request_sha256"],
        "public_gate_ready": public_gate_ready,
        "candidate_contract_valid_before_private_gate": step23_validation["contract_valid"],
        "private_heldout_aggregate_evidence_present": evidence_validation["evidence_present"],
        "private_heldout_aggregate_evidence_valid": evidence_validation["evidence_valid"],
        "private_heldout_evaluated": evidence_validation["evidence_valid"],
        "private_heldout_pass_rate": evidence_validation["private_heldout_pass_rate"],
        "candidate_contract_valid_after_private_gate": enriched_validation["contract_valid"],
        "release_gate_passed": release_gate_passed,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "blocked_reasons": [
            reason
            for reason, blocked in [
                ("public_eval_candidate_not_ready", not public_gate_ready),
                ("private_aggregate_evidence_missing_or_invalid", not evidence_validation["evidence_valid"]),
                ("candidate_contract_invalid", not enriched_validation["contract_valid"]),
                ("release_gate_not_passed", not enriched_validation["release_gate_passed"]),
            ]
            if blocked
        ],
    }
    write_json(gate_decision_path, gate_decision)

    public_report = {
        "schema_version": "forgeagent.public_safe_private_heldout_aggregate_candidate_eval_report.v1",
        "report_name": "private_heldout_aggregate_candidate_eval_gate_v1_public_safe",
        "candidate_id": candidate_package["candidate_identity"]["candidate_id"],
        "candidate_package_sha256": candidate_package_sha256,
        "public_eval_task_count": step23_summary["public_eval_task_count"],
        "public_batch_request_sha256": step23_summary["batch_request_sha256"],
        "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
        "private_task_family_count": heldout_summary["private_task_family_count"],
        "private_behavioral_axis_count": heldout_summary["private_behavioral_axis_count"],
        "public_gate_ready": public_gate_ready,
        "private_heldout_aggregate_evidence_present": evidence_validation["evidence_present"],
        "private_heldout_aggregate_evidence_valid": evidence_validation["evidence_valid"],
        "private_heldout_evaluated": evidence_validation["evidence_valid"],
        "private_heldout_pass_rate": evidence_validation["private_heldout_pass_rate"],
        "candidate_contract_valid_after_private_gate": enriched_validation["contract_valid"],
        "release_gate_passed": release_gate_passed,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "redaction_policy": {
            "private_task_ids_included": False,
            "task_level_results_included": False,
            "patch_content_included": False,
            "hidden_test_content_included": False,
            "prompt_content_included": False,
            "model_outputs_included": False,
        },
    }
    write_json(public_report_path, public_report)

    output_paths = [
        evidence_requirement_path,
        evidence_observed_path,
        evidence_validation_path,
        candidate_package_path,
        candidate_validation_path,
        gate_decision_path,
        public_report_path,
    ]
    privacy = scan_outputs(
        paths=output_paths,
        public_report_paths=[public_report_path],
        private_task_ids=private_task_ids,
    )
    privacy_path = OUT_DIR / "private_heldout_aggregate_candidate_eval_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.private_heldout_aggregate_candidate_eval_gate_summary.v1",
        "gate_name": "private_heldout_aggregate_candidate_eval_gate_v1",
        "source_step": "step29_23_public_eval_remote_batch_execution_v1",
        "source_step_ready": True,
        "heldout_protocol_ready": heldout_summary["protocol_ready"],
        "private_isolation_passed": private_isolation["passed"],
        "candidate_id": candidate_package["candidate_identity"]["candidate_id"],
        "candidate_package_sha256": candidate_package_sha256,
        "public_batch_request_sha256": step23_summary["batch_request_sha256"],
        "public_eval_task_count": step23_summary["public_eval_task_count"],
        "private_heldout_task_count": heldout_summary["private_heldout_task_count"],
        "public_gate_ready": public_gate_ready,
        "private_heldout_aggregate_evidence_present": evidence_validation["evidence_present"],
        "private_heldout_aggregate_evidence_valid": evidence_validation["evidence_valid"],
        "aggregate_only_policy_passed": evidence_validation["evidence_valid"],
        "private_heldout_evaluated": evidence_validation["evidence_valid"],
        "private_heldout_pass_rate": evidence_validation["private_heldout_pass_rate"],
        "candidate_contract_valid_before_private_gate": step23_validation["contract_valid"],
        "candidate_contract_valid_after_private_gate": enriched_validation["contract_valid"],
        "release_gate_passed": release_gate_passed,
        "public_safe_report_ready": True,
        "private_task_id_leak_count": privacy["private_task_id_leak_count"],
        "public_report_content_leak_count": privacy["public_report_content_leak_count"],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_25_authorized_private_heldout_execution_or_training_data_governance_scaleout",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "evidence_requirement": str(evidence_requirement_path),
            "evidence_observed": str(evidence_observed_path),
            "evidence_validation": str(evidence_validation_path),
            "candidate_package": str(candidate_package_path),
            "candidate_validation_result": str(candidate_validation_path),
            "gate_decision": str(gate_decision_path),
            "public_safe_report": str(public_report_path),
            "privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("PRIVATE_HELDOUT_AGGREGATE_CANDIDATE_EVAL_GATE_V1_OK")


if __name__ == "__main__":
    main()

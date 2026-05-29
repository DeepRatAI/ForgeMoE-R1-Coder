from __future__ import annotations

from pathlib import Path
import json
import re
import shutil
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRIVATE_SOURCE_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
TRAJECTORY_SOURCE_DIR = PROJECT_ROOT / "results/local/agentic_trajectory_recorder_v1"
OUT_DIR = PROJECT_ROOT / "results/local/heldout_aware_eval_protocol_v1"

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


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def scan_text_for_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": name, "count": len(matches)})
    return findings


def group_private_oracle_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["task_id"], {})[row["challenge"]] = row
    return grouped


def build_split_policy(
    private_summary: dict[str, Any],
    trajectory_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.heldout_aware_split_policy.v1",
        "policy_name": "heldout_aware_eval_protocol_v1",
        "development_split": {
            "name": "train",
            "source": "step29_11_agentic_trajectory_recorder_v1",
            "row_count": trajectory_summary["trajectory_sft_train_rows"],
            "may_use_for_training": True,
            "may_use_for_prompt_iteration": True,
            "may_inspect_patch_content": True,
        },
        "model_selection_split": {
            "name": "eval",
            "source": "step29_11_agentic_trajectory_recorder_v1",
            "row_count": trajectory_summary["eval_trajectory_rows"],
            "may_use_for_training": False,
            "may_use_for_prompt_iteration": False,
            "may_inspect_patch_content": False,
        },
        "private_final_gate_split": {
            "name": "private_heldout",
            "source": "step29_12_private_heldout_seed_set_v1",
            "task_count": private_summary["private_heldout_task_count"],
            "may_use_for_training": False,
            "may_use_for_prompt_iteration": False,
            "may_inspect_patch_content": False,
            "may_report_task_level_details_publicly": False,
            "aggregate_metrics_only": True,
        },
        "anti_contamination_rules": [
            "private_task_ids_must_not_appear_in_training_exports",
            "private_patch_content_must_not_appear_in_training_exports",
            "private_hidden_test_content_must_not_appear_in_training_exports",
            "public_safe_reports_must_not_include_private_patch_or_hidden_test_content",
            "private_results_can_block_training_or_release_but_cannot_be_used_for_optimization",
        ],
    }


def build_reference_candidate_scorecards(
    grouped_oracle_rows: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    candidate_specs = [
        (
            "oracle_reference_golden",
            "upper_bound_reference",
            "golden",
            "reference_only_not_a_model_candidate",
        ),
        (
            "oracle_reference_public_overfit",
            "overfit_canary",
            "public_overfit",
            "must_be_rejected_by_private_hidden_tests",
        ),
        (
            "oracle_reference_rejected",
            "negative_canary",
            "rejected",
            "must_fail_before_any_release_gate",
        ),
    ]

    scorecards: list[dict[str, Any]] = []
    task_count = len(grouped_oracle_rows)
    for candidate_id, role, challenge, interpretation in candidate_specs:
        rows = [challenge_rows[challenge] for challenge_rows in grouped_oracle_rows.values()]
        solved_count = sum(1 for row in rows if row["solved"])
        public_pass_count = sum(1 for row in rows if row["post_public_passed"])
        hidden_pass_count = sum(1 for row in rows if row["post_hidden_passed"])
        patch_apply_count = sum(1 for row in rows if row["patch_applied"])
        edit_scope_pass_count = sum(1 for row in rows if row["edit_scope_ok"])
        public_overfit_detected_count = sum(
            1 for row in rows if row["post_public_passed"] and not row["post_hidden_passed"]
        )
        pass_rate = round(solved_count / task_count, 6) if task_count else 0.0
        scorecards.append(
            {
                "schema_version": "forgeagent.heldout_reference_candidate_scorecard.v1",
                "candidate_id": candidate_id,
                "role": role,
                "challenge_source": challenge,
                "interpretation": interpretation,
                "private_task_count": task_count,
                "patch_apply_count": patch_apply_count,
                "public_pass_count": public_pass_count,
                "hidden_pass_count": hidden_pass_count,
                "solved_count": solved_count,
                "edit_scope_pass_count": edit_scope_pass_count,
                "public_overfit_detected_count": public_overfit_detected_count,
                "private_pass_rate": pass_rate,
                "passes_private_gate": pass_rate == 1.0 and edit_scope_pass_count == task_count,
                "eligible_for_training_release": False,
            }
        )
    return scorecards


def build_gate_decision(
    private_summary: dict[str, Any],
    private_isolation: dict[str, Any],
    scorecards: list[dict[str, Any]],
) -> dict[str, Any]:
    golden = next(row for row in scorecards if row["candidate_id"] == "oracle_reference_golden")
    public_overfit = next(
        row for row in scorecards if row["candidate_id"] == "oracle_reference_public_overfit"
    )
    rejected = next(row for row in scorecards if row["candidate_id"] == "oracle_reference_rejected")

    gates = {
        "private_seed_verified": private_summary["verified_private_heldout_task_count"]
        == private_summary["private_heldout_task_count"],
        "private_isolation_passed": private_isolation["passed"],
        "golden_reference_passes": golden["passes_private_gate"],
        "public_overfit_reference_rejected": public_overfit["private_pass_rate"] == 0.0
        and public_overfit["public_overfit_detected_count"] == private_summary["private_heldout_task_count"],
        "rejected_reference_rejected": rejected["private_pass_rate"] == 0.0,
        "private_manifest_is_hash_only": private_summary["public_safe_manifest_contains_patch_content"] is False
        and private_summary["public_safe_manifest_contains_hidden_content"] is False,
    }

    return {
        "schema_version": "forgeagent.heldout_aware_gate_decision.v1",
        "gate_name": "heldout_aware_eval_protocol_v1",
        "gates": gates,
        "protocol_ready": all(gates.values()),
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "reason_training_blocked": "protocol scaffolds private heldout governance; it does not authorize training",
        "reason_release_blocked": "no real model candidate has been evaluated by this step",
    }


def build_public_safe_report(
    private_summary: dict[str, Any],
    scorecards: list[dict[str, Any]],
    gate_decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.heldout_public_safe_report.v1",
        "report_name": "heldout_aware_eval_protocol_v1_public_safe",
        "private_task_count": private_summary["private_heldout_task_count"],
        "private_task_family_count": private_summary["task_family_count"],
        "private_behavioral_axis_count": private_summary["behavioral_axis_count"],
        "reference_candidates": [
            {
                "candidate_id": row["candidate_id"],
                "role": row["role"],
                "private_task_count": row["private_task_count"],
                "solved_count": row["solved_count"],
                "private_pass_rate": row["private_pass_rate"],
                "public_overfit_detected_count": row["public_overfit_detected_count"],
                "passes_private_gate": row["passes_private_gate"],
            }
            for row in scorecards
        ],
        "protocol_ready": gate_decision["protocol_ready"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "redaction_policy": {
            "private_task_ids_included": False,
            "private_patch_content_included": False,
            "private_hidden_test_content_included": False,
            "task_level_private_results_included": False,
        },
    }


def scan_protocol_outputs(output_paths: list[Path], private_task_ids: set[str]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    private_task_id_leaks: list[dict[str, Any]] = []

    for path in output_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for finding in scan_text_for_secrets(text):
            secret_findings.append({"path": str(path), **finding})
        if path.name == "public_safe_heldout_report.json":
            for task_id in private_task_ids:
                if task_id in text:
                    private_task_id_leaks.append({"path": str(path), "task_id": task_id})

    return {
        "schema_version": "forgeagent.heldout_protocol_privacy_report.v1",
        "scanned_paths": [str(path) for path in output_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "public_safe_private_task_id_leak_count": len(private_task_id_leaks),
        "public_safe_private_task_id_leaks": private_task_id_leaks,
        "passed": len(secret_findings) == 0 and len(private_task_id_leaks) == 0,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    private_summary = read_json(PRIVATE_SOURCE_DIR / "summary.json")
    private_isolation = read_json(PRIVATE_SOURCE_DIR / "isolation_report.json")
    private_oracle_rows = read_jsonl(PRIVATE_SOURCE_DIR / "private_heldout_oracle_results.jsonl")
    private_manifest_rows = read_jsonl(
        PRIVATE_SOURCE_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"
    )
    trajectory_summary = read_json(TRAJECTORY_SOURCE_DIR / "summary.json")

    grouped_oracle_rows = group_private_oracle_rows(private_oracle_rows)
    split_policy = build_split_policy(private_summary, trajectory_summary)
    scorecards = build_reference_candidate_scorecards(grouped_oracle_rows)
    gate_decision = build_gate_decision(private_summary, private_isolation, scorecards)
    public_safe_report = build_public_safe_report(private_summary, scorecards, gate_decision)

    split_policy_path = OUT_DIR / "heldout_split_policy.json"
    gate_decision_path = OUT_DIR / "heldout_gate_decision.json"
    public_safe_report_path = OUT_DIR / "public_safe_heldout_report.json"
    scorecard_path = OUT_DIR / "reference_candidate_scorecards.jsonl"

    write_json(split_policy_path, split_policy)
    write_json(gate_decision_path, gate_decision)
    write_json(public_safe_report_path, public_safe_report)
    for row in scorecards:
        append_jsonl(scorecard_path, row)

    privacy = scan_protocol_outputs(
        [split_policy_path, gate_decision_path, public_safe_report_path, scorecard_path],
        {row["task_id"] for row in private_manifest_rows},
    )
    privacy_path = OUT_DIR / "protocol_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.heldout_aware_eval_protocol_summary.v1",
        "protocol_name": "heldout_aware_eval_protocol_v1",
        "source_step": "step29_12_private_heldout_seed_set_v1",
        "private_heldout_task_count": private_summary["private_heldout_task_count"],
        "verified_private_heldout_task_count": private_summary[
            "verified_private_heldout_task_count"
        ],
        "private_task_family_count": private_summary["task_family_count"],
        "private_behavioral_axis_count": private_summary["behavioral_axis_count"],
        "split_policy_ready": True,
        "reference_candidate_count": len(scorecards),
        "golden_reference_private_pass_rate": next(
            row for row in scorecards if row["candidate_id"] == "oracle_reference_golden"
        )["private_pass_rate"],
        "public_overfit_reference_private_pass_rate": next(
            row for row in scorecards if row["candidate_id"] == "oracle_reference_public_overfit"
        )["private_pass_rate"],
        "public_overfit_detected_count": next(
            row for row in scorecards if row["candidate_id"] == "oracle_reference_public_overfit"
        )["public_overfit_detected_count"],
        "rejected_reference_private_pass_rate": next(
            row for row in scorecards if row["candidate_id"] == "oracle_reference_rejected"
        )["private_pass_rate"],
        "protocol_ready": gate_decision["protocol_ready"],
        "private_isolation_passed": private_isolation["passed"],
        "public_safe_report_ready": True,
        "public_safe_private_task_id_leak_count": privacy[
            "public_safe_private_task_id_leak_count"
        ],
        "secret_finding_count": privacy["secret_finding_count"],
        "privacy_scan_passed": privacy["passed"],
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_14_model_candidate_eval_contract",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "heldout_split_policy": str(split_policy_path),
            "reference_candidate_scorecards": str(scorecard_path),
            "heldout_gate_decision": str(gate_decision_path),
            "public_safe_heldout_report": str(public_safe_report_path),
            "protocol_privacy_report": str(privacy_path),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("HELDOUT_AWARE_EVAL_PROTOCOL_V1_OK")


if __name__ == "__main__":
    main()

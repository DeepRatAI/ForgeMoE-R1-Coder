from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import shutil
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASK_SOURCE_DIR = PROJECT_ROOT / "results/local/internal_synthetic_micro_generator_v0"
GATE_SOURCE_DIR = PROJECT_ROOT / "results/local/oracle_hidden_test_gate_v0"
OUT_DIR = PROJECT_ROOT / "results/local/agentic_trajectory_recorder_v1"

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\\s*[:=]"),
}

TRAINING_EXPORT_NAMES = [
    "trajectory_sft_train.jsonl",
    "repair_trace_train.jsonl",
    "trajectory_preference_train.jsonl",
]


@dataclass(frozen=True)
class TaskContext:
    task_id: str
    split: str
    never_train_on: bool
    task_dir: Path
    spec: dict[str, Any]
    score: dict[str, Any]
    challenges: dict[str, dict[str, Any]]
    repo_before: Path
    hidden_test: Path
    golden_patch: Path
    public_overfit_patch: Path


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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def scan_text_for_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": name, "count": len(matches)})
    return findings


def flatten_json_text(row: object) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)


def load_task_contexts() -> list[TaskContext]:
    score_rows = read_jsonl(GATE_SOURCE_DIR / "task_oracle_scores.jsonl")
    challenge_rows = read_jsonl(GATE_SOURCE_DIR / "patch_challenge_results.jsonl")

    scores = {row["task_id"]: row for row in score_rows}
    challenges_by_task: dict[str, dict[str, dict[str, Any]]] = {}
    for row in challenge_rows:
        challenges_by_task.setdefault(row["task_id"], {})[row["challenge"]] = row

    contexts: list[TaskContext] = []
    for task_dir in sorted((TASK_SOURCE_DIR / "tasks").iterdir()):
        if not task_dir.is_dir():
            continue

        spec = read_json(task_dir / "task_spec.json")
        task_id = spec["task_id"]
        score = scores[task_id]
        if not score["gate_passed"]:
            raise RuntimeError(f"task did not pass Step 29.10 gate: {task_id}")

        contexts.append(
            TaskContext(
                task_id=task_id,
                split=spec["split"],
                never_train_on=bool(spec["never_train_on"]),
                task_dir=task_dir,
                spec=spec,
                score=score,
                challenges=challenges_by_task[task_id],
                repo_before=task_dir / "repo_before",
                hidden_test=task_dir / "hidden_tests/test_hidden.py",
                golden_patch=GATE_SOURCE_DIR / "challenge_patches" / task_id / "golden.patch",
                public_overfit_patch=GATE_SOURCE_DIR
                / "challenge_patches"
                / task_id
                / "public_overfit.patch",
            )
        )
    return contexts


def event(index: int, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.agentic_trajectory_event.v1",
        "event_id": f"event_{index:03d}_{event_type}",
        "index": index,
        "type": event_type,
        "payload": payload,
    }


def compact_command_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": result["command"],
        "exit_code": result["exit_code"],
        "passed": result["passed"],
        "timed_out": result["timed_out"],
        "stderr_sha256": sha256_text(result.get("stderr", "")),
        "stderr_excerpt": result.get("stderr", "")[:500],
    }


def patch_metadata(path: Path) -> dict[str, Any]:
    patch_text = read_text(path)
    return {
        "path": str(path),
        "sha256": sha256_text(patch_text),
        "bytes": len(patch_text.encode("utf-8")),
    }


def build_trajectory(ctx: TaskContext) -> dict[str, Any]:
    public_test = read_text(ctx.repo_before / "tests/test_public.py")
    utils_before = read_text(ctx.repo_before / "app/utils.py")
    hidden_text = read_text(ctx.hidden_test)
    public_overfit = ctx.challenges["public_overfit"]
    golden = ctx.challenges["golden"]

    events = [
        event(
            1,
            "read_task",
            {
                "task_id": ctx.task_id,
                "split": ctx.split,
                "instruction": ctx.spec["instruction"],
                "task_family": ctx.spec["task_family"],
            },
        ),
        event(
            2,
            "list_files",
            {
                "files": ["app/__init__.py", "app/utils.py", "tests/test_public.py"],
                "hidden_tests_listed": False,
            },
        ),
        event(
            3,
            "read_file",
            {
                "path": "app/utils.py",
                "sha256": sha256_text(utils_before),
                "bytes": len(utils_before.encode("utf-8")),
            },
        ),
        event(
            4,
            "inspect_public_tests",
            {
                "path": "tests/test_public.py",
                "sha256": sha256_text(public_test),
                "bytes": len(public_test.encode("utf-8")),
            },
        ),
        event(
            5,
            "run_public_tests",
            {
                "phase": "pre",
                "result": compact_command_result(public_overfit["pre_public"]),
            },
        ),
        event(
            6,
            "plan",
            {
                "strategy": "first generate a minimal patch from public evidence, then validate and repair against the oracle",
                "expected_edit_scope": ctx.spec["expected_edit_scope"],
            },
        ),
        event(
            7,
            "generate_patch",
            {
                "attempt": "public_overfit",
                "patch": patch_metadata(ctx.public_overfit_patch),
                "training_label": "negative",
            },
        ),
        event(
            8,
            "git_apply_check",
            {
                "attempt": "public_overfit",
                "result": compact_command_result(public_overfit["patch_check"]),
            },
        ),
        event(
            9,
            "apply_patch",
            {
                "attempt": "public_overfit",
                "result": compact_command_result(public_overfit["patch_apply"]),
            },
        ),
        event(
            10,
            "run_public_tests",
            {
                "attempt": "public_overfit",
                "result": compact_command_result(public_overfit["post_public"]),
            },
        ),
        event(
            11,
            "run_hidden_tests",
            {
                "attempt": "public_overfit",
                "hidden_test_sha256": sha256_text(hidden_text),
                "hidden_test_content_exported": False,
                "result": compact_command_result(public_overfit["post_hidden"]),
            },
        ),
        event(
            12,
            "observe_failure",
            {
                "attempt": "public_overfit",
                "failure_mode": "passes_public_fails_hidden",
                "repair_signal": "public tests are insufficient; generalize beyond the visible example",
            },
        ),
        event(
            13,
            "repair",
            {
                "attempt": "golden",
                "patch": patch_metadata(ctx.golden_patch),
                "training_label": "positive" if ctx.split == "train" else "heldout_or_eval_positive",
            },
        ),
        event(
            14,
            "git_apply_check",
            {
                "attempt": "golden",
                "result": compact_command_result(golden["patch_check"]),
            },
        ),
        event(
            15,
            "run_public_tests",
            {
                "attempt": "golden",
                "result": compact_command_result(golden["post_public"]),
            },
        ),
        event(
            16,
            "run_hidden_tests",
            {
                "attempt": "golden",
                "hidden_test_sha256": sha256_text(hidden_text),
                "hidden_test_content_exported": False,
                "result": compact_command_result(golden["post_hidden"]),
            },
        ),
        event(
            17,
            "final_answer",
            {
                "solved": True,
                "selected_patch_sha256": patch_metadata(ctx.golden_patch)["sha256"],
                "oracle_strength_score": ctx.score["oracle_strength_score"],
            },
        ),
    ]

    return {
        "schema_version": "forgeagent.agentic_trajectory_record.v1",
        "trajectory_id": f"{ctx.task_id}-agentic-trajectory-v1",
        "task_id": ctx.task_id,
        "split": ctx.split,
        "never_train_on": ctx.never_train_on,
        "source_gate": "step29_10_oracle_hidden_test_gate_v0",
        "instruction": ctx.spec["instruction"],
        "task_family": ctx.spec["task_family"],
        "events": events,
        "attempts": [
            {
                "attempt_id": "public_overfit",
                "patch_ref": patch_metadata(ctx.public_overfit_patch),
                "label": "negative",
                "patch_applied": public_overfit["patch_applied"],
                "public_passed": public_overfit["post_public_passed"],
                "hidden_passed": public_overfit["post_hidden_passed"],
                "reward": -0.5,
            },
            {
                "attempt_id": "golden",
                "patch_ref": patch_metadata(ctx.golden_patch),
                "label": "positive",
                "patch_applied": golden["patch_applied"],
                "public_passed": golden["post_public_passed"],
                "hidden_passed": golden["post_hidden_passed"],
                "reward": 1.0,
            },
        ],
        "metrics": {
            "event_count": len(events),
            "attempt_count": 2,
            "repair_count": 1,
            "public_overfit_caught_by_hidden": True,
            "solved": True,
            "oracle_strength_score": ctx.score["oracle_strength_score"],
            "hidden_coverage_score": ctx.score["hidden_coverage_score"],
            "anti_overfit_score": ctx.score["anti_overfit_score"],
        },
        "privacy": {
            "hidden_test_content_exported": False,
            "secret_scan_required": True,
        },
    }


def build_train_sft_row(trajectory: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
    patch_text = read_text(ctx.golden_patch)
    user_content = (
        "You are an autonomous software engineering agent.\n"
        "Inspect the repository task, use public test feedback, avoid public-test overfitting, "
        "and produce the final unified diff patch.\n\n"
        f"Task ID: {ctx.task_id}\n"
        f"Instruction: {ctx.spec['instruction']}\n"
        "Observed repair signal: a public-overfit patch passed public tests but failed hidden validation.\n"
        "Return only the final patch."
    )
    return {
        "schema_version": "forgeagent.trajectory_sft_row.v1",
        "trajectory_id": trajectory["trajectory_id"],
        "task_id": ctx.task_id,
        "split": ctx.split,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert autonomous coding agent that repairs repositories using unified diff patches.",
            },
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": patch_text},
        ],
        "metadata": {
            "source": "agentic_trajectory_recorder_v1",
            "task_family": ctx.spec["task_family"],
            "oracle_strength_score": trajectory["metrics"]["oracle_strength_score"],
            "hidden_tests_included": False,
        },
    }


def build_repair_trace_row(trajectory: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.repair_trace_row.v1",
        "trajectory_id": trajectory["trajectory_id"],
        "task_id": ctx.task_id,
        "split": ctx.split,
        "negative_attempt": {
            "attempt_id": "public_overfit",
            "patch_sha256": trajectory["attempts"][0]["patch_ref"]["sha256"],
            "public_passed": True,
            "hidden_passed": False,
            "failure_mode": "passes_public_fails_hidden",
        },
        "positive_attempt": {
            "attempt_id": "golden",
            "patch_sha256": trajectory["attempts"][1]["patch_ref"]["sha256"],
            "public_passed": True,
            "hidden_passed": True,
        },
        "repair_signal": "generalize beyond visible public tests",
    }


def build_preference_row(trajectory: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.trajectory_preference_row.v1",
        "trajectory_id": trajectory["trajectory_id"],
        "task_id": ctx.task_id,
        "split": ctx.split,
        "prompt": ctx.spec["instruction"],
        "chosen_patch": read_text(ctx.golden_patch),
        "rejected_patch": read_text(ctx.public_overfit_patch),
        "chosen_reason": "passes_public_and_hidden_tests",
        "rejected_reason": "passes_public_tests_but_fails_hidden_tests",
    }


def scan_outputs_for_privacy(output_paths: list[Path], hidden_texts: list[str]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    hidden_leaks: list[dict[str, Any]] = []

    for path in output_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for finding in scan_text_for_secrets(text):
            secret_findings.append({"path": str(path), **finding})
        for hidden_text in hidden_texts:
            if hidden_text.strip() and hidden_text.strip() in text:
                hidden_leaks.append({"path": str(path), "hidden_sha256": sha256_text(hidden_text)})

    return {
        "schema_version": "forgeagent.trajectory_privacy_report.v1",
        "scanned_paths": [str(path) for path in output_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "hidden_test_leak_count": len(hidden_leaks),
        "hidden_test_leaks": hidden_leaks,
        "passed": len(secret_findings) == 0 and len(hidden_leaks) == 0,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    contexts = load_task_contexts()
    trajectories: list[dict[str, Any]] = []
    hidden_texts = [read_text(ctx.hidden_test) for ctx in contexts]

    export_dir = OUT_DIR / "dataset_exports"
    train_sft_path = export_dir / "trajectory_sft_train.jsonl"
    repair_trace_path = export_dir / "repair_trace_train.jsonl"
    preference_path = export_dir / "trajectory_preference_train.jsonl"
    eval_path = export_dir / "eval_trajectories.jsonl"
    private_path = export_dir / "private_heldout_trajectories.jsonl"

    for ctx in contexts:
        trajectory = build_trajectory(ctx)
        trajectories.append(trajectory)
        write_json(OUT_DIR / "trajectories" / ctx.task_id / "trajectory.json", trajectory)
        append_jsonl(OUT_DIR / "trajectory_records.jsonl", trajectory)

        if ctx.split == "train":
            append_jsonl(train_sft_path, build_train_sft_row(trajectory, ctx))
            append_jsonl(repair_trace_path, build_repair_trace_row(trajectory, ctx))
            append_jsonl(preference_path, build_preference_row(trajectory, ctx))
        elif ctx.split == "eval":
            eval_record = dict(trajectory)
            eval_record["training_export_allowed"] = False
            append_jsonl(eval_path, eval_record)
        elif ctx.split == "private_heldout":
            private_record = dict(trajectory)
            private_record["training_export_allowed"] = False
            private_record["patch_content_withheld_from_training"] = True
            append_jsonl(private_path, private_record)

    output_paths = [
        OUT_DIR / "trajectory_records.jsonl",
        train_sft_path,
        repair_trace_path,
        preference_path,
        eval_path,
        private_path,
    ]
    privacy = scan_outputs_for_privacy(output_paths, hidden_texts)
    write_json(OUT_DIR / "privacy_report.json", privacy)

    split_counts: dict[str, int] = {}
    event_types: set[str] = set()
    for trajectory in trajectories:
        split_counts[trajectory["split"]] = split_counts.get(trajectory["split"], 0) + 1
        event_types.update(event["type"] for event in trajectory["events"])

    def count_jsonl(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    summary = {
        "schema_version": "forgeagent.agentic_trajectory_recorder_summary.v1",
        "recorder_name": "agentic_trajectory_recorder_v1",
        "source_step": "step29_10_oracle_hidden_test_gate_v0",
        "trajectory_count": len(trajectories),
        "solved_trajectory_count": sum(1 for row in trajectories if row["metrics"]["solved"]),
        "split_counts": split_counts,
        "event_type_count": len(event_types),
        "event_types": sorted(event_types),
        "min_event_count": min(row["metrics"]["event_count"] for row in trajectories),
        "public_overfit_caught_by_hidden_count": sum(
            1 for row in trajectories if row["metrics"]["public_overfit_caught_by_hidden"]
        ),
        "trajectory_sft_train_rows": count_jsonl(train_sft_path),
        "repair_trace_train_rows": count_jsonl(repair_trace_path),
        "trajectory_preference_train_rows": count_jsonl(preference_path),
        "eval_trajectory_rows": count_jsonl(eval_path),
        "private_heldout_trajectory_rows": count_jsonl(private_path),
        "private_heldout_exported_to_training": False,
        "privacy_scan_passed": privacy["passed"],
        "secret_finding_count": privacy["secret_finding_count"],
        "hidden_test_leak_count": privacy["hidden_test_leak_count"],
        "training_launch_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_12_private_heldout_seed_set",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "trajectory_records": str(OUT_DIR / "trajectory_records.jsonl"),
            "privacy_report": str(OUT_DIR / "privacy_report.json"),
            "dataset_exports": str(export_dir),
        },
    }

    write_json(OUT_DIR / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("AGENTIC_TRAJECTORY_RECORDER_V1_OK")


if __name__ == "__main__":
    main()

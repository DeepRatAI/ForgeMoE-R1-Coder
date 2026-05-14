from __future__ import annotations

from pathlib import Path
import json
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = PROJECT_ROOT / "results/local/qwen2_5_coder_0_5b_baseline_v0"
OUT_DIR = PROJECT_ROOT / "reports/local/step20_forensics"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


def read_text(path: Path, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def compact_command(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "command": row.get("command"),
        "exit_code": row.get("exit_code"),
        "passed": row.get("passed"),
        "timed_out": row.get("timed_out"),
        "elapsed_seconds": row.get("elapsed_seconds"),
        "stderr_tail": (row.get("stderr") or "")[-1600:],
        "stdout_tail": (row.get("stdout") or "")[-800:],
    }


def analyze_task(task_row: dict[str, Any]) -> dict[str, Any]:
    task_id = task_row["task_id"]
    task_dir = RESULT_DIR / "tasks" / task_id

    generated = read_jsonl(task_dir / "generated_responses.jsonl")
    parse_failures = read_json(task_dir / "parse_failures.json") if (task_dir / "parse_failures.json").exists() else []
    pipeline = read_json(task_dir / "candidate_pipeline_result.json") if (task_dir / "candidate_pipeline_result.json").exists() else None

    patches = []
    patch_dir = task_dir / "parsed_patches"
    if patch_dir.exists():
        for patch_path in sorted(patch_dir.glob("*.patch")):
            patches.append(
                {
                    "name": patch_path.name,
                    "path": str(patch_path),
                    "text": read_text(patch_path),
                }
            )

    ranked = []
    selected_patch_id = None
    selected_reward = None
    solved = False

    if pipeline:
        selected_patch_id = pipeline.get("selected_patch_id")
        solved = bool(pipeline.get("solved"))
        verifier = pipeline.get("verifier_result") or {}
        selected_reward = verifier.get("selected_reward")

        for candidate in verifier.get("ranked_candidates", []):
            eval_result = candidate.get("eval_result") or {}
            ranked.append(
                {
                    "patch_id": candidate.get("patch_id"),
                    "patch_applied": candidate.get("patch_applied"),
                    "post_tests_passed": candidate.get("post_tests_passed"),
                    "reward": candidate.get("reward"),
                    "pre_test": compact_command(eval_result.get("pre_test")),
                    "patch_apply_result": compact_command(eval_result.get("patch_apply_result")),
                    "post_test": compact_command(eval_result.get("post_test")),
                }
            )

    generated_preview = [
        {
            "response_id": row.get("response_id"),
            "latency_seconds": row.get("latency_seconds"),
            "token_counts": row.get("token_counts"),
            "text_preview": (row.get("text") or "")[:2500],
        }
        for row in generated
    ]

    reasons = []
    if not patches:
        reasons.append("no_parseable_patch")
    elif pipeline and not solved:
        for candidate in ranked:
            apply_result = candidate.get("patch_apply_result") or {}
            post_test = candidate.get("post_test") or {}
            if apply_result and not apply_result.get("passed"):
                reasons.append("patch_apply_failed")
            if post_test and not post_test.get("passed"):
                reasons.append("post_tests_failed")
        if not reasons:
            reasons.append("candidate_pipeline_attempted_but_unsolved_unknown")

    return {
        "task_id": task_id,
        "generated_response_count": task_row.get("generated_response_count"),
        "parsed_candidate_count": task_row.get("parsed_candidate_count"),
        "parse_failure_count": task_row.get("parse_failure_count"),
        "candidate_pipeline_attempted": task_row.get("candidate_pipeline_attempted"),
        "solved": solved,
        "selected_patch_id": selected_patch_id,
        "selected_reward": selected_reward,
        "failure_reasons": sorted(set(reasons)),
        "generated_preview": generated_preview,
        "parse_failures": parse_failures,
        "parsed_patches": patches,
        "ranked_candidates": ranked,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = read_json(RESULT_DIR / "summary.json")
    task_rows = read_jsonl(RESULT_DIR / "task_results.jsonl")
    task_reports = [analyze_task(row) for row in task_rows]

    failure_modes = []
    for report in task_reports:
        if report["failure_reasons"]:
            failure_modes.append(
                {
                    "task_id": report["task_id"],
                    "reasons": report["failure_reasons"],
                    "selected_reward": report["selected_reward"],
                }
            )

    aggregate = {
        "schema_version": "forgeagent.step20_forensics.v0",
        "source_summary": summary,
        "task_count": len(task_reports),
        "solved_tasks": sum(1 for item in task_reports if item["solved"]),
        "parsed_candidate_count": sum(int(item["parsed_candidate_count"] or 0) for item in task_reports),
        "parse_failure_count": sum(int(item["parse_failure_count"] or 0) for item in task_reports),
        "candidate_pipeline_attempted_count": sum(1 for item in task_reports if item["candidate_pipeline_attempted"]),
        "failure_mode_count": len(failure_modes),
        "failure_modes": failure_modes,
        "task_reports": task_reports,
    }

    md = []
    md.append("# Step 20.1 — Qwen Baseline Forensic Analysis")
    md.append("")
    md.append("## Aggregate")
    md.append("")
    md.append(f"- Model: `{summary['model_id']}`")
    md.append(f"- Total tasks: `{summary['total_tasks']}`")
    md.append(f"- Generated responses: `{summary['generated_response_count']}`")
    md.append(f"- Parsed candidates: `{summary['parsed_candidate_count']}`")
    md.append(f"- Parse failures: `{summary['parse_failure_count']}`")
    md.append(f"- Candidate pipeline attempted: `{summary['candidate_pipeline_attempted_count']}`")
    md.append(f"- Solved tasks: `{summary['solved_tasks']}`")
    md.append(f"- Solve rate: `{summary['solve_rate']}`")
    md.append(f"- Elapsed seconds: `{summary['elapsed_seconds']}`")
    md.append("")
    md.append("## Failure modes")
    md.append("")
    for item in failure_modes:
        md.append(f"- `{item['task_id']}`: `{', '.join(item['reasons'])}`, selected reward `{item['selected_reward']}`")
    md.append("")
    md.append("## Task findings")
    md.append("")

    for report in task_reports:
        md.append(f"### {report['task_id']}")
        md.append("")
        md.append(f"- Parsed candidates: `{report['parsed_candidate_count']}`")
        md.append(f"- Parse failures: `{report['parse_failure_count']}`")
        md.append(f"- Pipeline attempted: `{report['candidate_pipeline_attempted']}`")
        md.append(f"- Solved: `{report['solved']}`")
        md.append(f"- Selected patch: `{report['selected_patch_id']}`")
        md.append(f"- Selected reward: `{report['selected_reward']}`")
        md.append(f"- Failure reasons: `{', '.join(report['failure_reasons']) or 'none'}`")
        md.append("")

        for patch in report["parsed_patches"]:
            md.append(f"Patch: `{patch['name']}`")
            md.append("")
            md.append("```diff")
            md.append(patch["text"])
            md.append("```")
            md.append("")

        if report["ranked_candidates"]:
            md.append("Verifier outcomes:")
            md.append("")
            for candidate in report["ranked_candidates"]:
                apply_result = candidate.get("patch_apply_result") or {}
                post_test = candidate.get("post_test") or {}
                md.append(
                    f"- `{candidate['patch_id']}`: reward `{candidate['reward']}`, "
                    f"patch_applied `{candidate['patch_applied']}`, "
                    f"apply_passed `{apply_result.get('passed')}`, "
                    f"post_tests_passed `{candidate['post_tests_passed']}`, "
                    f"post_exit `{post_test.get('exit_code')}`"
                )
            md.append("")

    json_path = OUT_DIR / "step20_qwen_baseline_forensics.json"
    md_path = OUT_DIR / "step20_qwen_baseline_forensics.md"

    json_path.write_text(json.dumps(aggregate, indent=2, default=str), encoding="utf-8")
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(
        {
            "schema_version": aggregate["schema_version"],
            "task_count": aggregate["task_count"],
            "solved_tasks": aggregate["solved_tasks"],
            "parsed_candidate_count": aggregate["parsed_candidate_count"],
            "parse_failure_count": aggregate["parse_failure_count"],
            "candidate_pipeline_attempted_count": aggregate["candidate_pipeline_attempted_count"],
            "failure_mode_count": aggregate["failure_mode_count"],
            "json_path": str(json_path),
            "md_path": str(md_path),
        },
        indent=2,
    ))
    print("STEP20_FORENSICS_ANALYSIS_OK")


if __name__ == "__main__":
    main()

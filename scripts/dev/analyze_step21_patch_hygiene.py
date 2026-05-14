from __future__ import annotations

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.agent.patch_hygiene import diagnose_patch_text, summarize_reports


STEP21_DIR = PROJECT_ROOT / "results/local/qwen2_5_coder_0_5b_prompt_contract_v1"
OUT_DIR = PROJECT_ROOT / "reports/local/step22_patch_hygiene"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sanitized_dir = OUT_DIR / "sanitized"
    sanitized_dir.mkdir(parents=True, exist_ok=True)

    source_summary = read_json(STEP21_DIR / "summary.json")
    task_rows = read_jsonl(STEP21_DIR / "task_results.jsonl")

    rows = []
    hygiene_reports = []

    for task_row in task_rows:
        task_id = task_row["task_id"]
        task_dir = STEP21_DIR / "tasks" / task_id

        for idx, generated in enumerate(read_jsonl(task_dir / "generated_responses.jsonl")):
            text = generated.get("text", "")
            report = diagnose_patch_text(text)
            hygiene_reports.append(report)

            sanitized_path = sanitized_dir / f"{task_id}_{idx}.patch"
            if report.sanitized_diff:
                sanitized_path.write_text(report.sanitized_diff, encoding="utf-8")

            rows.append({
                "task_id": task_id,
                "response_index": idx,
                "response_id": generated.get("response_id"),
                "raw_text_preview": text[:1500],
                "sanitized_patch_path": str(sanitized_path) if report.sanitized_diff else None,
                "hygiene": report.to_dict(),
                "step21_patch_apply_success": task_row.get("patch_apply_success"),
                "step21_solved": task_row.get("solved"),
                "step21_selected_reward": task_row.get("selected_reward"),
            })

    hygiene_summary = summarize_reports(hygiene_reports)

    summary = {
        "schema_version": "forgeagent.patch_hygiene_report.v0",
        "source_step": 21,
        "source_experiment": "qwen2_5_coder_0_5b_prompt_contract_v1",
        "model_id": source_summary["model_id"],
        "task_count": len(task_rows),
        "generated_response_count": len(rows),
        "step21_patch_apply_success_count": source_summary["patch_apply_success_count"],
        "step21_solved_tasks": source_summary["solved_tasks"],
        **hygiene_summary,
        "interpretation": {
            "primary_failure": "diff_like_but_non_actionable",
            "needs_model_rerun": False,
            "recommended_next_step": "structured_edit_intent_contract_v0",
        },
        "artifacts": {
            "json": str(OUT_DIR / "step22_patch_hygiene_report.json"),
            "markdown": str(OUT_DIR / "step22_patch_hygiene_report.md"),
            "sanitized_dir": str(sanitized_dir),
        },
    }

    report = {"summary": summary, "rows": rows}

    (OUT_DIR / "step22_patch_hygiene_report.json").write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    md = [
        "# Step 22 — Patch Hygiene / Diff Validity Layer v0",
        "",
        "## Summary",
        "",
        f"- Model: `{summary['model_id']}`",
        f"- Generated responses: `{summary['generated_response_count']}`",
        f"- Diff header count: `{summary['diff_header_count']}`",
        f"- Markdown fence count: `{summary['markdown_fence_count']}`",
        f"- Prose after diff count: `{summary['prose_after_diff_count']}`",
        f"- Has change lines count: `{summary['has_change_lines_count']}`",
        f"- Non-actionable no-change-lines count: `{summary['non_actionable_no_change_lines_count']}`",
        f"- Actionable diff-like count: `{summary['actionable_diff_like_count']}`",
        f"- Recommended next step: `{summary['interpretation']['recommended_next_step']}`",
        "",
        "## Rows",
        "",
    ]

    for row in rows:
        h = row["hygiene"]
        md.extend([
            f"### {row['task_id']} / response {row['response_index']}",
            "",
            f"- Status: `{h['status']}`",
            f"- Markdown fence: `{h['contains_markdown_fence']}`",
            f"- Prose after diff: `{h['contains_prose_after_diff']}`",
            f"- Has change lines: `{h['has_change_lines']}`",
            f"- Added lines: `{h['added_line_count']}`",
            f"- Removed lines: `{h['removed_line_count']}`",
            "",
            "Raw preview:",
            "",
            "```text",
            row["raw_text_preview"],
            "```",
            "",
            "Sanitized diff:",
            "",
            "```diff",
            h["sanitized_diff"],
            "```",
            "",
        ])

    (OUT_DIR / "step22_patch_hygiene_report.md").write_text(
        "\n".join(md),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, default=str))
    print("STEP22_PATCH_HYGIENE_ANALYSIS_OK")


if __name__ == "__main__":
    main()

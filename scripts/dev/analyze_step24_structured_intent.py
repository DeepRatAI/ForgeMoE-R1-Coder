from __future__ import annotations

from pathlib import Path
import difflib
import json
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = PROJECT_ROOT / "results/local/qwen2_5_coder_0_5b_structured_intent_v0"
OUT_DIR = PROJECT_ROOT / "reports/local/step24_forensics"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


def safe_text(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def extract_expected_file_from_prompt(prompt_messages: list[dict[str, Any]]) -> str:
    combined = "\n\n".join(str(item.get("content", "")) for item in prompt_messages)

    marker = "Current file app/utils.py:\n```python\n"
    start = combined.find(marker)
    if start == -1:
        return ""

    start += len(marker)
    end = combined.find("```\n\nTests:", start)
    if end == -1:
        return ""

    return combined[start:end]


def classify_intent_failure(
    *,
    expected_file_text: str,
    intent: dict[str, Any] | None,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    if intent is None:
        return {
            "category": "missing_intent",
            "details": "No parsed intent was available.",
            "find_text_similarity": None,
            "replace_text_present": False,
            "file_path": None,
        }

    file_path = intent.get("file_path")
    find_text = intent.get("find_text") or ""
    replace_text = intent.get("replace_text") or ""
    validation_error = (validation or {}).get("error")

    similarity = None
    if expected_file_text or find_text:
        similarity = round(
            difflib.SequenceMatcher(None, expected_file_text, find_text).ratio(),
            6,
        )

    if validation_error == "find_text_not_found":
        if find_text.strip() == "":
            category = "empty_find_text"
        elif similarity is not None and similarity >= 0.90:
            category = "near_miss_exact_text"
        elif "```" in find_text:
            category = "markdown_contaminated_find_text"
        elif "def " not in find_text:
            category = "non_code_find_text"
        else:
            category = "wrong_or_hallucinated_find_text"
    elif validation_error == "file_missing":
        category = "wrong_file_path"
    elif validation_error == "find_text_not_unique":
        category = "ambiguous_find_text"
    elif validation_error == "empty_replace_text":
        category = "empty_replace_text"
    elif validation_error == "test_file_edit_forbidden":
        category = "attempted_test_edit"
    elif validation_error:
        category = validation_error
    elif validation and validation.get("valid"):
        category = "valid"
    else:
        category = "unknown_invalid"

    return {
        "category": category,
        "details": validation_error,
        "find_text_similarity": similarity,
        "replace_text_present": bool(replace_text.strip()),
        "file_path": file_path,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = read_json(RESULT_DIR / "summary.json")
    task_rows = read_jsonl(RESULT_DIR / "task_results.jsonl")

    task_reports = []

    for row in task_rows:
        task_id = row["task_id"]
        task_dir = RESULT_DIR / "tasks" / task_id

        prompt_messages = read_json(task_dir / "prompt_messages.json") if (task_dir / "prompt_messages.json").exists() else []
        generated = read_jsonl(task_dir / "generated_responses.jsonl")
        intent = read_json(task_dir / "intent.json") if (task_dir / "intent.json").exists() else row.get("intent")
        patch_result = read_json(task_dir / "patch_result.json") if (task_dir / "patch_result.json").exists() else None

        validation = row.get("validation")
        if patch_result and patch_result.get("validation"):
            validation = patch_result["validation"]

        expected_file_text = extract_expected_file_from_prompt(prompt_messages)

        generated_preview = []
        for item in generated:
            generated_preview.append(
                {
                    "response_id": item.get("response_id"),
                    "latency_seconds": item.get("latency_seconds"),
                    "token_counts": item.get("token_counts"),
                    "text_preview": (item.get("text") or "")[:3000],
                }
            )

        find_text = (intent or {}).get("find_text", "") if intent else ""
        replace_text = (intent or {}).get("replace_text", "") if intent else ""

        diff_expected_vs_find = "\n".join(
            difflib.unified_diff(
                expected_file_text.splitlines(),
                find_text.splitlines(),
                fromfile="expected_app_utils.py",
                tofile="model_find_text",
                lineterm="",
            )
        )

        failure = classify_intent_failure(
            expected_file_text=expected_file_text,
            intent=intent,
            validation=validation,
        )

        task_reports.append(
            {
                "task_id": task_id,
                "json_parse_success": row.get("json_parse_success"),
                "validation": validation,
                "failure_classification": failure,
                "intent": intent,
                "expected_file_text": expected_file_text,
                "find_text": find_text,
                "replace_text": replace_text,
                "diff_expected_vs_find": diff_expected_vs_find,
                "canonical_patch_created": row.get("canonical_patch_created"),
                "patch_apply_passed": row.get("patch_apply_passed"),
                "post_test_passed": row.get("post_test_passed"),
                "solved": row.get("solved"),
                "generated_preview": generated_preview,
                "task_result_path": str(task_dir / "task_result.json"),
            }
        )

    categories: dict[str, int] = {}
    validation_errors: dict[str, int] = {}

    for report in task_reports:
        category = report["failure_classification"]["category"]
        categories[category] = categories.get(category, 0) + 1

        error = (report["validation"] or {}).get("error")
        error_key = str(error)
        validation_errors[error_key] = validation_errors.get(error_key, 0) + 1

    aggregate = {
        "schema_version": "forgeagent.step24_structured_intent_forensics.v0",
        "source_summary": summary,
        "task_count": len(task_reports),
        "json_parse_success_count": sum(1 for item in task_reports if item["json_parse_success"]),
        "valid_intent_count": sum(1 for item in task_reports if item["validation"] and item["validation"].get("valid")),
        "canonical_patch_count": sum(1 for item in task_reports if item["canonical_patch_created"]),
        "patch_apply_success_count": sum(1 for item in task_reports if item["patch_apply_passed"]),
        "solved_tasks": sum(1 for item in task_reports if item["solved"]),
        "failure_categories": categories,
        "validation_errors": validation_errors,
        "recommended_next_step": "intent_repair_and_normalization_v0",
        "task_reports": task_reports,
    }

    md = []
    md.append("# Step 24.1 — Qwen Structured Intent Forensics")
    md.append("")
    md.append("## Aggregate")
    md.append("")
    md.append(f"- Model: `{summary['model_id']}`")
    md.append(f"- Total tasks: `{summary['total_tasks']}`")
    md.append(f"- Generated responses: `{summary['generated_response_count']}`")
    md.append(f"- JSON parse successes: `{summary['json_parse_success_count']}`")
    md.append(f"- Valid intents: `{summary['valid_intent_count']}`")
    md.append(f"- Canonical patches: `{summary['canonical_patch_count']}`")
    md.append(f"- Patch apply successes: `{summary['patch_apply_success_count']}`")
    md.append(f"- Solved tasks: `{summary['solved_tasks']}`")
    md.append(f"- Solve rate: `{summary['solve_rate']}`")
    md.append("")
    md.append("## Failure categories")
    md.append("")
    for key, value in sorted(categories.items()):
        md.append(f"- `{key}`: `{value}`")
    md.append("")
    md.append("## Validation errors")
    md.append("")
    for key, value in sorted(validation_errors.items()):
        md.append(f"- `{key}`: `{value}`")
    md.append("")
    md.append("## Recommendation")
    md.append("")
    md.append("Next step: `intent_repair_and_normalization_v0`.")
    md.append("")
    md.append("The model emits parseable JSON, but the semantic fields fail validation. The next layer should normalize or repair intents before canonical patch construction.")
    md.append("")
    md.append("## Task reports")
    md.append("")

    for report in task_reports:
        failure = report["failure_classification"]
        md.append(f"### {report['task_id']}")
        md.append("")
        md.append(f"- Category: `{failure['category']}`")
        md.append(f"- Validation error: `{failure['details']}`")
        md.append(f"- Find-text similarity: `{failure['find_text_similarity']}`")
        md.append(f"- File path: `{failure['file_path']}`")
        md.append(f"- Replace text present: `{failure['replace_text_present']}`")
        md.append(f"- Solved: `{report['solved']}`")
        md.append("")
        md.append("Intent:")
        md.append("")
        md.append("```json")
        md.append(json.dumps(report["intent"], indent=2, default=str))
        md.append("```")
        md.append("")
        md.append("Diff between expected file and model find_text:")
        md.append("")
        md.append("```diff")
        md.append(report["diff_expected_vs_find"] or "<empty diff>")
        md.append("```")
        md.append("")

    json_path = OUT_DIR / "step24_structured_intent_forensics.json"
    md_path = OUT_DIR / "step24_structured_intent_forensics.md"

    json_path.write_text(json.dumps(aggregate, indent=2, default=str), encoding="utf-8")
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(
        {
            "schema_version": aggregate["schema_version"],
            "task_count": aggregate["task_count"],
            "json_parse_success_count": aggregate["json_parse_success_count"],
            "valid_intent_count": aggregate["valid_intent_count"],
            "canonical_patch_count": aggregate["canonical_patch_count"],
            "patch_apply_success_count": aggregate["patch_apply_success_count"],
            "solved_tasks": aggregate["solved_tasks"],
            "failure_categories": aggregate["failure_categories"],
            "validation_errors": aggregate["validation_errors"],
            "recommended_next_step": aggregate["recommended_next_step"],
            "json_path": str(json_path),
            "md_path": str(md_path),
        },
        indent=2,
    ))
    print("STEP24_STRUCTURED_INTENT_FORENSICS_OK")


if __name__ == "__main__":
    main()

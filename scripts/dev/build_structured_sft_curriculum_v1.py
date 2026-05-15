from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "results/local/structured_sft_curriculum_expansion_v1"


SYSTEM_PROMPT = (
    "You are ForgeMoE-R1-Agent-Coder's structured code-edit planning model. "
    "Return only valid JSON. Do not include markdown, prose, or code fences. "
    "The JSON must describe the intended code edit, target files, tests, constraints, "
    "risk flags, verification strategy, and acceptance criteria."
)


CATEGORIES = [
    "localized_bugfix",
    "wrong_file_guard",
    "missing_test_addition",
    "small_multifile_edit",
    "safe_refactor",
    "import_typing_fix",
    "invalid_patch_repair",
    "semantic_patch_repair",
    "boundary_condition_fix",
    "data_validation_fix",
    "config_behavior_fix",
    "dependency_api_migration",
]


CASES = [
    {
        "name": "add_one",
        "file": "app/math_utils.py",
        "symbol": "add_one",
        "bug": "returns x instead of x + 1",
        "expected": "return x + 1",
        "test_file": "tests/test_math_utils.py",
        "test_symbol": "test_add_one",
        "edge": "negative input should increment toward zero only by arithmetic addition",
    },
    {
        "name": "square",
        "file": "app/math_utils.py",
        "symbol": "square",
        "bug": "returns x + x instead of x * x",
        "expected": "return x * x",
        "test_file": "tests/test_math_utils.py",
        "test_symbol": "test_square",
        "edge": "negative input should produce positive square",
    },
    {
        "name": "max2",
        "file": "app/math_utils.py",
        "symbol": "max2",
        "bug": "always returns the first argument",
        "expected": "return a if a >= b else b",
        "test_file": "tests/test_math_utils.py",
        "test_symbol": "test_max2",
        "edge": "equal values should return either value without changing type",
    },
    {
        "name": "safe_divide",
        "file": "app/math_utils.py",
        "symbol": "safe_divide",
        "bug": "raises ZeroDivisionError instead of returning None when denominator is zero",
        "expected": "return None for zero denominator; otherwise return numerator / denominator",
        "test_file": "tests/test_math_utils.py",
        "test_symbol": "test_safe_divide",
        "edge": "zero denominator must not raise",
    },
    {
        "name": "clamp",
        "file": "app/math_utils.py",
        "symbol": "clamp",
        "bug": "does not enforce the upper bound",
        "expected": "return min(max(value, lower), upper)",
        "test_file": "tests/test_math_utils.py",
        "test_symbol": "test_clamp",
        "edge": "value above upper should return upper",
    },
    {
        "name": "normalize_email",
        "file": "app/user_utils.py",
        "symbol": "normalize_email",
        "bug": "strips whitespace but forgets to lowercase",
        "expected": "return email.strip().lower()",
        "test_file": "tests/test_user_utils.py",
        "test_symbol": "test_normalize_email",
        "edge": "mixed case domain and local part should lowercase",
    },
    {
        "name": "redact_email",
        "file": "app/user_utils.py",
        "symbol": "redact_email",
        "bug": "leaks the full local part before @",
        "expected": "preserve first character and domain while masking the rest of the local part",
        "test_file": "tests/test_user_utils.py",
        "test_symbol": "test_redact_email",
        "edge": "short local parts should not crash",
    },
    {
        "name": "slugify",
        "file": "app/text_utils.py",
        "symbol": "slugify",
        "bug": "replaces spaces but leaves uppercase letters",
        "expected": "lowercase text before replacing spaces with hyphens",
        "test_file": "tests/test_text_utils.py",
        "test_symbol": "test_slugify",
        "edge": "multiple spaces should not create unstable output",
    },
    {
        "name": "is_palindrome",
        "file": "app/text_utils.py",
        "symbol": "is_palindrome",
        "bug": "compares raw string and fails on casing and spaces",
        "expected": "normalize case and ignore spaces before comparison",
        "test_file": "tests/test_text_utils.py",
        "test_symbol": "test_is_palindrome",
        "edge": "phrase with spaces and mixed case should pass",
    },
    {
        "name": "parse_bool",
        "file": "app/config_utils.py",
        "symbol": "parse_bool",
        "bug": "treats any non-empty string as True",
        "expected": "accept true/false yes/no 1/0 explicitly and reject unknown values",
        "test_file": "tests/test_config_utils.py",
        "test_symbol": "test_parse_bool",
        "edge": "unknown strings should raise ValueError",
    },
    {
        "name": "load_timeout",
        "file": "app/config_utils.py",
        "symbol": "load_timeout",
        "bug": "ignores configured timeout and always returns default",
        "expected": "read timeout_seconds from config when present",
        "test_file": "tests/test_config_utils.py",
        "test_symbol": "test_load_timeout",
        "edge": "missing key should preserve default",
    },
    {
        "name": "validate_payload",
        "file": "app/api_utils.py",
        "symbol": "validate_payload",
        "bug": "accepts payload without required id field",
        "expected": "return False or raise validation error when id is missing",
        "test_file": "tests/test_api_utils.py",
        "test_symbol": "test_validate_payload_requires_id",
        "edge": "empty dict should be invalid",
    },
    {
        "name": "extract_user_id",
        "file": "app/api_utils.py",
        "symbol": "extract_user_id",
        "bug": "looks for userId but upstream now sends user_id",
        "expected": "support user_id while preserving compatibility if required",
        "test_file": "tests/test_api_utils.py",
        "test_symbol": "test_extract_user_id",
        "edge": "missing id should not silently return wrong value",
    },
    {
        "name": "unique_sorted",
        "file": "app/list_utils.py",
        "symbol": "unique_sorted",
        "bug": "sorts but does not remove duplicates",
        "expected": "return sorted unique values",
        "test_file": "tests/test_list_utils.py",
        "test_symbol": "test_unique_sorted",
        "edge": "already sorted duplicates should collapse",
    },
    {
        "name": "merge_dicts",
        "file": "app/dict_utils.py",
        "symbol": "merge_dicts",
        "bug": "mutates the left input dictionary",
        "expected": "return a new merged dictionary without mutating inputs",
        "test_file": "tests/test_dict_utils.py",
        "test_symbol": "test_merge_dicts_no_mutation",
        "edge": "nested values should be preserved by reference unless explicitly copied",
    },
    {
        "name": "get_nested",
        "file": "app/dict_utils.py",
        "symbol": "get_nested",
        "bug": "raises KeyError for missing nested keys instead of returning default",
        "expected": "return default when any path segment is missing",
        "test_file": "tests/test_dict_utils.py",
        "test_symbol": "test_get_nested_default",
        "edge": "empty path should return original object or default according to existing contract",
    },
]


def stable_id(category: str, case: dict[str, str], index: int) -> str:
    raw = f"{category}:{case['name']}:{index}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"sft-v1-{category}-{case['name']}-{digest}"


def split_for_index(index: int) -> str:
    return "eval" if index % 6 == 5 else "train"


def difficulty_for(category: str) -> str:
    if category in {"small_multifile_edit", "semantic_patch_repair", "dependency_api_migration"}:
        return "medium"
    if category in {"invalid_patch_repair", "wrong_file_guard", "config_behavior_fix"}:
        return "easy_medium"
    return "easy"


def user_prompt(category: str, case: dict[str, str]) -> str:
    base = (
        f"Repository task category: {category}\n"
        f"Primary file: {case['file']}\n"
        f"Primary symbol: {case['symbol']}\n"
        f"Bug: {case['bug']}\n"
        f"Expected behavior: {case['expected']}\n"
        f"Known test file: {case['test_file']}\n"
        f"Known test symbol: {case['test_symbol']}\n"
        f"Important edge case: {case['edge']}\n"
        "Return structured JSON edit intent only. Do not return a patch."
    )

    additions = {
        "localized_bugfix": "Focus on the smallest implementation change that fixes the failing behavior.",
        "wrong_file_guard": "A previous attempt edited app/__init__.py incorrectly. Guard against touching the wrong file.",
        "missing_test_addition": "Include a focused test addition or update that would fail before the implementation fix.",
        "small_multifile_edit": "Modify more than one file only if an export, test, or integration point truly requires it.",
        "safe_refactor": "Preserve behavior while making the implementation clearer and safer.",
        "import_typing_fix": "Preserve type hints and add only the minimal necessary imports.",
        "invalid_patch_repair": "A previous patch failed to apply because it targeted a nonexistent or stale file. Plan the repair.",
        "semantic_patch_repair": "A previous patch applied but failed tests because it changed behavior in the wrong direction.",
        "boundary_condition_fix": "Pay special attention to boundary values and edge-case behavior.",
        "data_validation_fix": "Strengthen input validation without accepting invalid data silently.",
        "config_behavior_fix": "Respect explicit config values while preserving defaults for missing keys.",
        "dependency_api_migration": "Adapt to the new API shape while avoiding broad rewrites.",
    }

    return base + "\n" + additions[category]


def target_for(category: str, case: dict[str, str], task_id: str) -> dict[str, Any]:
    prohibited_files: list[str] = []
    target_files = [case["file"]]
    test_files = [case["test_file"]]

    operations: list[dict[str, Any]] = [
        {
            "type": "modify_function",
            "file": case["file"],
            "symbol": case["symbol"],
            "intent": case["expected"],
            "reason": case["bug"],
        }
    ]

    constraints = [
        "return only valid JSON",
        "prefer the smallest correct edit",
        "do not include markdown or prose",
        "do not delete or weaken tests",
        "do not hardcode only the visible test values",
        "preserve public API unless the task explicitly requires an API migration",
    ]

    risk_flags: list[str] = []

    if category == "wrong_file_guard":
        prohibited_files.append("app/__init__.py")
        constraints.append("do not modify prohibited files")
        risk_flags.append("wrong_file_target_risk")

    if category == "missing_test_addition":
        operations.append(
            {
                "type": "add_or_update_test",
                "file": case["test_file"],
                "symbol": case["test_symbol"],
                "intent": f"cover {case['expected']} and edge case: {case['edge']}",
            }
        )
        risk_flags.append("test_quality_risk")

    if category == "small_multifile_edit":
        operations.append(
            {
                "type": "maybe_update_related_file",
                "file": "app/__init__.py",
                "intent": "update export only if required by existing package contract",
            }
        )
        risk_flags.append("multifile_scope_risk")

    if category == "safe_refactor":
        operations.append(
            {
                "type": "preserve_behavior_refactor",
                "file": case["file"],
                "symbol": case["symbol"],
                "intent": "keep the externally visible behavior aligned with tests",
            }
        )
        risk_flags.append("refactor_regression_risk")

    if category == "import_typing_fix":
        operations.append(
            {
                "type": "minimal_import_or_typing_update",
                "file": case["file"],
                "intent": "add only imports or annotations needed for the fix",
            }
        )
        risk_flags.append("unnecessary_import_risk")

    if category == "invalid_patch_repair":
        prohibited_files.append("nonexistent.py")
        operations.append(
            {
                "type": "repair_patch_targeting",
                "file": case["file"],
                "intent": "retarget stale or nonexistent file path to real implementation file",
            }
        )
        risk_flags.append("patch_apply_failure_risk")

    if category == "semantic_patch_repair":
        operations.append(
            {
                "type": "repair_semantic_direction",
                "file": case["file"],
                "symbol": case["symbol"],
                "intent": "ensure behavior changes toward expected contract, not merely toward passing visible syntax checks",
            }
        )
        risk_flags.append("semantic_regression_risk")

    if category == "boundary_condition_fix":
        operations.append(
            {
                "type": "cover_boundary_condition",
                "file": case["test_file"],
                "symbol": case["test_symbol"],
                "intent": case["edge"],
            }
        )
        risk_flags.append("boundary_condition_risk")

    if category == "data_validation_fix":
        operations.append(
            {
                "type": "validate_inputs",
                "file": case["file"],
                "symbol": case["symbol"],
                "intent": "reject or safely handle invalid input according to existing contract",
            }
        )
        risk_flags.append("validation_contract_risk")

    if category == "config_behavior_fix":
        operations.append(
            {
                "type": "preserve_config_default",
                "file": case["file"],
                "symbol": case["symbol"],
                "intent": "respect explicit configuration while preserving default fallback behavior",
            }
        )
        risk_flags.append("configuration_precedence_risk")

    if category == "dependency_api_migration":
        operations.append(
            {
                "type": "api_shape_migration",
                "file": case["file"],
                "symbol": case["symbol"],
                "intent": "support the new upstream field or call shape with minimal compatibility handling",
            }
        )
        risk_flags.append("dependency_api_drift_risk")

    verification = [
        f"run {case['test_file']}::{case['test_symbol']}",
        f"run all tests in {case['test_file']}",
        "inspect diff for unrelated file changes",
        "confirm no tests were deleted or weakened",
    ]

    return {
        "schema_version": "forgeagent.structured_intent.v1",
        "task_id": task_id,
        "category": category,
        "target_files": target_files,
        "test_files": test_files,
        "operations": operations,
        "constraints": constraints,
        "prohibited_files": sorted(set(prohibited_files)),
        "verification": verification,
        "risk_flags": sorted(set(risk_flags)),
        "acceptance_criteria": [
            "patch applies cleanly",
            "the relevant failing behavior is corrected",
            "no unrelated files are modified",
            "tests are not removed or weakened",
            "implementation is general rather than hardcoded to one assertion",
        ],
        "notes": {
            "primary_symbol": case["symbol"],
            "expected_behavior": case["expected"],
            "edge_case": case["edge"],
        },
    }


def build_row(category: str, case: dict[str, str], index: int) -> dict[str, Any]:
    task_id = stable_id(category, case, index)
    target = target_for(category, case, task_id)

    return {
        "schema_version": "forgeagent.sft_row.v1",
        "task_id": task_id,
        "split": split_for_index(index),
        "category": category,
        "difficulty": difficulty_for(category),
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt(category, case),
            },
        ],
        "target_text": json.dumps(target, ensure_ascii=False, sort_keys=True),
        "metadata": {
            "source": "synthetic_structured_intent_curriculum_v1",
            "case_name": case["name"],
            "primary_file": case["file"],
            "primary_symbol": case["symbol"],
            "known_test_file": case["test_file"],
            "known_test_symbol": case["test_symbol"],
            "requires_gpu": False,
            "generated_by": "step29_5_structured_sft_curriculum_expansion_v1",
        },
    }


def validate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_ids = set()
    category_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {"train": 0, "eval": 0}
    difficulty_counts: dict[str, int] = {}

    for row in rows:
        assert row["schema_version"] == "forgeagent.sft_row.v1", row
        assert row["task_id"] not in task_ids, row["task_id"]
        task_ids.add(row["task_id"])

        assert row["split"] in {"train", "eval"}, row
        split_counts[row["split"]] += 1

        assert row["category"] in CATEGORIES, row
        category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1

        difficulty_counts[row["difficulty"]] = difficulty_counts.get(row["difficulty"], 0) + 1

        assert len(row["messages"]) == 2, row
        assert row["messages"][0]["role"] == "system", row
        assert row["messages"][1]["role"] == "user", row
        assert row["target_text"].strip(), row

        target = json.loads(row["target_text"])
        assert target["schema_version"] == "forgeagent.structured_intent.v1", target
        assert target["task_id"] == row["task_id"], target
        assert target["category"] == row["category"], target
        assert target["target_files"], target
        assert target["test_files"], target
        assert target["operations"], target
        assert target["constraints"], target
        assert target["verification"], target
        assert target["acceptance_criteria"], target

    assert len(rows) == 192, len(rows)
    assert split_counts["train"] == 160, split_counts
    assert split_counts["eval"] == 32, split_counts
    assert len(category_counts) == 12, category_counts
    assert all(count == 16 for count in category_counts.values()), category_counts

    return {
        "row_count": len(rows),
        "unique_task_ids": len(task_ids),
        "category_counts": category_counts,
        "split_counts": split_counts,
        "difficulty_counts": difficulty_counts,
    }


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    index = 0

    for category in CATEGORIES:
        for case in CASES:
            rows.append(build_row(category, case, index))
            index += 1

    validation = validate_rows(rows)

    train_rows = [row for row in rows if row["split"] == "train"]
    eval_rows = [row for row in rows if row["split"] == "eval"]

    summary = {
        "schema_version": "forgeagent.structured_sft_curriculum_expansion_summary.v1",
        "dataset_name": "structured_sft_curriculum_expansion_v1",
        "previous_dataset": "structured_sft_dataset_expansion_v0",
        "objective": "structured_edit_intent_sft",
        "target_format": "json_structured_intent",
        "row_schema_version": "forgeagent.sft_row.v1",
        "target_schema_version": "forgeagent.structured_intent.v1",
        "total_rows": len(rows),
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "case_count": len(CASES),
        "category_count": len(CATEGORIES),
        "category_counts": validation["category_counts"],
        "difficulty_counts": validation["difficulty_counts"],
        "split_counts": validation["split_counts"],
        "launches_training_job": False,
        "gpu_required": False,
        "cost_gate": {
            "requires_explicit_approval_before_training": True,
        },
        "artifacts": {
            "all_jsonl": str(OUT_DIR / "all.jsonl"),
            "train_jsonl": str(OUT_DIR / "train.jsonl"),
            "eval_jsonl": str(OUT_DIR / "eval.jsonl"),
            "summary_json": str(OUT_DIR / "summary.json"),
        },
    }

    write_jsonl(OUT_DIR / "all.jsonl", rows)
    write_jsonl(OUT_DIR / "train.jsonl", train_rows)
    write_jsonl(OUT_DIR / "eval.jsonl", eval_rows)
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("STRUCTURED_SFT_CURRICULUM_EXPANSION_V1_OK")


if __name__ == "__main__":
    main()

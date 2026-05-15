from __future__ import annotations

from pathlib import Path
import hashlib
import json
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "results/local/structured_sft_dataset_expansion_v0"


SYSTEM_PROMPT = (
    "You are ForgeMoE-R1-Agent-Coder's structured code-edit planning model. "
    "Given a repository task, return only valid JSON. "
    "Do not include markdown, prose, or code fences. "
    "The JSON must describe the intended edit, target files, tests, constraints, "
    "and verification strategy."
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
]


BUG_CASES = [
    {
        "name": "add_one",
        "file": "app/math_utils.py",
        "bug": "def add_one(x: int) -> int returns x instead of x + 1",
        "expected": "return x + 1",
        "test": "tests/test_math_utils.py::test_add_one",
    },
    {
        "name": "square",
        "file": "app/math_utils.py",
        "bug": "def square(x: int) -> int returns x + x instead of x * x",
        "expected": "return x * x",
        "test": "tests/test_math_utils.py::test_square",
    },
    {
        "name": "max2",
        "file": "app/math_utils.py",
        "bug": "def max2(a: int, b: int) -> int always returns a",
        "expected": "return a if a >= b else b",
        "test": "tests/test_math_utils.py::test_max2",
    },
    {
        "name": "normalize_email",
        "file": "app/user_utils.py",
        "bug": "normalize_email strips whitespace but forgets to lowercase the address",
        "expected": "return email.strip().lower()",
        "test": "tests/test_user_utils.py::test_normalize_email",
    },
    {
        "name": "slugify",
        "file": "app/text_utils.py",
        "bug": "slugify replaces spaces with hyphens but leaves uppercase letters",
        "expected": "lowercase before replacing spaces",
        "test": "tests/test_text_utils.py::test_slugify",
    },
    {
        "name": "safe_divide",
        "file": "app/math_utils.py",
        "bug": "safe_divide raises ZeroDivisionError instead of returning None for denominator zero",
        "expected": "return None when denominator is zero",
        "test": "tests/test_math_utils.py::test_safe_divide_zero",
    },
]


def stable_id(category: str, index: int, name: str) -> str:
    raw = f"{category}:{index}:{name}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"sft-{category}-{index:02d}-{digest}"


def make_target(
    *,
    task_id: str,
    category: str,
    case: dict[str, str],
    target_files: list[str],
    test_files: list[str],
    operations: list[dict[str, Any]],
    constraints: list[str],
    prohibited_files: list[str],
    verification: list[str],
    risk_flags: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.structured_intent.v0",
        "task_id": task_id,
        "category": category,
        "target_files": target_files,
        "test_files": test_files,
        "operations": operations,
        "constraints": constraints,
        "prohibited_files": prohibited_files,
        "verification": verification,
        "risk_flags": risk_flags,
        "acceptance_criteria": [
            "patch applies cleanly",
            "pre-existing failing test passes after edit",
            "no unrelated files are modified",
            "no tests are deleted or weakened",
        ],
        "notes": {
            "primary_symbol": case["name"],
            "expected_behavior": case["expected"],
        },
    }


def make_user_prompt(category: str, case: dict[str, str], variant: int) -> str:
    common = (
        f"Repository task category: {category}\n"
        f"Bug summary: {case['bug']}\n"
        f"Primary file: {case['file']}\n"
        f"Known failing test: {case['test']}\n"
        "Return a structured JSON edit intent. "
        "Do not return a patch yet."
    )

    if category == "wrong_file_guard":
        return (
            common
            + "\nImportant constraint: previous model attempts edited app/__init__.py, "
            "but the fix belongs in the primary implementation file."
        )

    if category == "missing_test_addition":
        return (
            common
            + "\nAdditional request: add or update a focused unit test that would fail before the fix."
        )

    if category == "small_multifile_edit":
        return (
            common
            + "\nAdditional request: update the implementation and the package export only if required."
        )

    if category == "safe_refactor":
        return (
            common
            + "\nAdditional request: perform the smallest safe refactor needed to make behavior clearer."
        )

    if category == "import_typing_fix":
        return (
            common
            + "\nAdditional request: preserve type hints and add only necessary imports."
        )

    if category == "invalid_patch_repair":
        return (
            common
            + "\nPrevious patch failed to apply because it targeted a nonexistent file. "
            "Plan a repair that targets the real file."
        )

    if category == "semantic_patch_repair":
        return (
            common
            + "\nPrevious patch applied but failed tests because it changed behavior in the wrong direction. "
            "Plan the semantic repair."
        )

    return common


def build_example(category: str, case: dict[str, str], index: int) -> dict[str, Any]:
    task_id = stable_id(category, index, case["name"])

    target_files = [case["file"]]
    test_file = case["test"].split("::", 1)[0]
    test_files = [test_file]

    prohibited_files = ["app/__init__.py"] if category in {"wrong_file_guard", "invalid_patch_repair"} else []

    operations: list[dict[str, Any]] = [
        {
            "type": "modify_function",
            "file": case["file"],
            "symbol": case["name"],
            "intent": case["expected"],
        }
    ]

    if category == "missing_test_addition":
        operations.append(
            {
                "type": "add_or_update_test",
                "file": test_file,
                "symbol": case["test"].split("::")[-1],
                "intent": "cover the corrected behavior and at least one edge case",
            }
        )

    if category == "small_multifile_edit":
        operations.append(
            {
                "type": "maybe_update_export",
                "file": "app/__init__.py",
                "intent": "only update export if the public API requires it",
            }
        )
        prohibited_files = []

    constraints = [
        "return only valid structured intent JSON",
        "prefer the smallest correct edit",
        "do not delete or weaken tests",
        "do not hardcode test values without implementing general behavior",
    ]

    if prohibited_files:
        constraints.append("do not modify prohibited files")

    verification = [
        f"run {case['test']}",
        "run the relevant unit test file",
        "inspect diff for unrelated changes",
    ]

    risk_flags = []
    if category in {"invalid_patch_repair", "semantic_patch_repair"}:
        risk_flags.append("previous_failed_attempt_available")
    if category == "wrong_file_guard":
        risk_flags.append("wrong_file_target_risk")
    if category == "missing_test_addition":
        risk_flags.append("test_quality_risk")

    target = make_target(
        task_id=task_id,
        category=category,
        case=case,
        target_files=target_files,
        test_files=test_files,
        operations=operations,
        constraints=constraints,
        prohibited_files=prohibited_files,
        verification=verification,
        risk_flags=risk_flags,
    )

    target_text = json.dumps(target, ensure_ascii=False, sort_keys=True)

    return {
        "schema_version": "forgeagent.sft_row.v0",
        "task_id": task_id,
        "split": "unset",
        "category": category,
        "difficulty": "medium" if category in {"small_multifile_edit", "semantic_patch_repair"} else "easy",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": make_user_prompt(category, case, index),
            },
        ],
        "target_text": target_text,
        "metadata": {
            "source": "synthetic_verified_intent_seed",
            "case_name": case["name"],
            "primary_file": case["file"],
            "known_test": case["test"],
            "requires_gpu": False,
            "generated_by": "step29_2_structured_sft_dataset_expansion_v0",
        },
    }


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def validate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_ids = set()
    category_counts: dict[str, int] = {}

    for row in rows:
        assert row["schema_version"] == "forgeagent.sft_row.v0", row
        assert row["task_id"] not in task_ids, row["task_id"]
        task_ids.add(row["task_id"])

        assert row["category"] in CATEGORIES, row
        category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1

        assert isinstance(row["messages"], list) and len(row["messages"]) == 2, row
        assert row["messages"][0]["role"] == "system", row
        assert row["messages"][1]["role"] == "user", row

        target = json.loads(row["target_text"])
        assert target["schema_version"] == "forgeagent.structured_intent.v0", target
        assert target["task_id"] == row["task_id"], target
        assert target["category"] == row["category"], target
        assert target["target_files"], target
        assert target["operations"], target
        assert target["verification"], target

    return {
        "row_count": len(rows),
        "unique_task_ids": len(task_ids),
        "category_counts": category_counts,
    }


def split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        item = dict(row)
        if index % 6 == 5:
            item["split"] = "eval"
            eval_rows.append(item)
        else:
            item["split"] = "train"
            train.append(item)

    return train, eval_rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []

    index = 0
    for category in CATEGORIES:
        for case in BUG_CASES:
            rows.append(build_example(category, case, index))
            index += 1

    train_rows, eval_rows = split_rows(rows)
    all_rows = train_rows + eval_rows

    validation = validate_rows(all_rows)

    assert len(all_rows) == 48, len(all_rows)
    assert len(train_rows) == 40, len(train_rows)
    assert len(eval_rows) == 8, len(eval_rows)
    assert len(validation["category_counts"]) == 8, validation

    summary = {
        "schema_version": "forgeagent.structured_sft_dataset_expansion_summary.v0",
        "dataset_name": "structured_sft_dataset_expansion_v0",
        "total_rows": len(all_rows),
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "category_counts": validation["category_counts"],
        "objective": "structured_edit_intent_sft",
        "target_format": "json_structured_intent",
        "launches_training_job": False,
        "gpu_required": False,
        "notes": [
            "Dataset expansion before first paid GPU training job.",
            "Rows target structured intent rather than raw patches.",
            "Patch generation and trajectory datasets remain separate future layers.",
        ],
        "artifacts": {
            "all_jsonl": str(OUT_DIR / "all.jsonl"),
            "train_jsonl": str(OUT_DIR / "train.jsonl"),
            "eval_jsonl": str(OUT_DIR / "eval.jsonl"),
            "summary_json": str(OUT_DIR / "summary.json"),
        },
    }

    write_jsonl(OUT_DIR / "all.jsonl", all_rows)
    write_jsonl(OUT_DIR / "train.jsonl", train_rows)
    write_jsonl(OUT_DIR / "eval.jsonl", eval_rows)
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("STRUCTURED_SFT_DATASET_EXPANSION_OK")


if __name__ == "__main__":
    main()

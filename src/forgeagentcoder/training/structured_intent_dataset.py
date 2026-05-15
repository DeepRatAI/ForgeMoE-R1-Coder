from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class DatasetValidationIssue:
    task_id: str
    field: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StructuredIntentTrainingExample:
    task_id: str
    source_model_id: str
    training_objective: str
    prompt_messages: list[dict[str, str]]
    assistant_target: str
    full_messages: list[dict[str, str]]
    metadata: dict[str, Any]

    def to_sft_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "forgeagent.structured_intent_training_example.v0",
            "task_id": self.task_id,
            "source_model_id": self.source_model_id,
            "training_objective": self.training_objective,
            "prompt_messages": self.prompt_messages,
            "assistant_target": self.assistant_target,
            "messages": self.full_messages,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class TokenizationStats:
    row_count: int
    min_tokens: int
    max_tokens: int
    mean_tokens: float
    per_task: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def validate_sft_row(row: dict[str, Any]) -> list[DatasetValidationIssue]:
    task_id = str(row.get("task_id", "<missing_task_id>"))
    issues: list[DatasetValidationIssue] = []

    if row.get("schema_version") != "forgeagent.structured_intent_sft_row.v0":
        issues.append(DatasetValidationIssue(task_id, "schema_version", "unexpected_schema_version"))

    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        issues.append(DatasetValidationIssue(task_id, "messages", "messages_must_be_non_empty_list"))
    else:
        for idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                issues.append(DatasetValidationIssue(task_id, f"messages[{idx}]", "message_must_be_dict"))
                continue
            if msg.get("role") not in {"system", "user", "assistant"}:
                issues.append(DatasetValidationIssue(task_id, f"messages[{idx}].role", "invalid_role"))
            if not isinstance(msg.get("content"), str) or not msg.get("content"):
                issues.append(DatasetValidationIssue(task_id, f"messages[{idx}].content", "content_must_be_non_empty_string"))

        if messages and messages[-1].get("role") != "assistant":
            issues.append(DatasetValidationIssue(task_id, "messages[-1].role", "last_message_must_be_assistant_target"))

    target = row.get("target")
    if not isinstance(target, str) or not target.strip():
        issues.append(DatasetValidationIssue(task_id, "target", "target_must_be_non_empty_string"))
        return issues

    try:
        target_json = json.loads(target)
    except Exception as exc:
        issues.append(DatasetValidationIssue(task_id, "target", f"target_must_parse_as_json:{type(exc).__name__}"))
        return issues

    for field in ("intent_id", "task_id", "file_path", "find_text", "replace_text"):
        if not target_json.get(field):
            issues.append(DatasetValidationIssue(task_id, f"target.{field}", "required_target_field_missing_or_empty"))

    if target_json.get("file_path") != "app/utils.py":
        issues.append(DatasetValidationIssue(task_id, "target.file_path", "expected_app_utils_py"))

    if messages and isinstance(messages, list) and messages[-1].get("content") != target:
        issues.append(DatasetValidationIssue(task_id, "messages[-1].content", "assistant_message_must_equal_target"))

    return issues


def row_to_training_example(row: dict[str, Any]) -> StructuredIntentTrainingExample:
    messages = row["messages"]
    prompt_messages = [dict(item) for item in messages[:-1]]
    assistant_target = str(row["target"])

    return StructuredIntentTrainingExample(
        task_id=str(row["task_id"]),
        source_model_id=str(row["source_model_id"]),
        training_objective=str(row["training_objective"]),
        prompt_messages=prompt_messages,
        assistant_target=assistant_target,
        full_messages=[dict(item) for item in messages],
        metadata=dict(row.get("metadata") or {}),
    )


def deterministic_train_eval_split(
    examples: list[StructuredIntentTrainingExample],
    *,
    eval_rows: int = 1,
) -> tuple[list[StructuredIntentTrainingExample], list[StructuredIntentTrainingExample]]:
    sorted_examples = sorted(examples, key=lambda item: item.task_id)

    if eval_rows <= 0:
        return sorted_examples, []

    if eval_rows >= len(sorted_examples):
        return [], sorted_examples

    train = sorted_examples[:-eval_rows]
    eval_ = sorted_examples[-eval_rows:]
    return train, eval_


def render_messages_fallback(messages: list[dict[str, str]]) -> str:
    parts = []

    for message in messages:
        role = message["role"].strip()
        content = message["content"].strip()
        parts.append(f"<|{role}|>\n{content}")

    return "\n\n".join(parts).strip() + "\n"


def render_messages(messages: list[dict[str, str]], tokenizer: Any | None = None) -> str:
    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
        except Exception:
            return render_messages_fallback(messages)

    return render_messages_fallback(messages)


def count_tokens(text: str, tokenizer: Any | None = None) -> int:
    if tokenizer is None:
        return len(text.split())

    encoded = tokenizer(text, add_special_tokens=False)
    return len(encoded["input_ids"])


def compute_tokenization_stats(
    examples: list[StructuredIntentTrainingExample],
    tokenizer: Any | None = None,
) -> TokenizationStats:
    per_task = []

    for example in examples:
        full_text = render_messages(example.full_messages, tokenizer=tokenizer)
        prompt_text = render_messages(example.prompt_messages, tokenizer=tokenizer)
        target_text = example.assistant_target

        full_tokens = count_tokens(full_text, tokenizer=tokenizer)
        prompt_tokens = count_tokens(prompt_text, tokenizer=tokenizer)
        target_tokens = count_tokens(target_text, tokenizer=tokenizer)

        per_task.append(
            {
                "task_id": example.task_id,
                "full_tokens": full_tokens,
                "prompt_tokens": prompt_tokens,
                "target_tokens": target_tokens,
                "full_chars": len(full_text),
                "target_chars": len(target_text),
            }
        )

    full_counts = [item["full_tokens"] for item in per_task]

    return TokenizationStats(
        row_count=len(per_task),
        min_tokens=min(full_counts) if full_counts else 0,
        max_tokens=max(full_counts) if full_counts else 0,
        mean_tokens=round(mean(full_counts), 6) if full_counts else 0.0,
        per_task=per_task,
    )


def load_and_validate_examples(path: str | Path) -> tuple[list[StructuredIntentTrainingExample], list[DatasetValidationIssue]]:
    rows = read_jsonl(path)

    all_issues: list[DatasetValidationIssue] = []
    examples: list[StructuredIntentTrainingExample] = []

    for row in rows:
        issues = validate_sft_row(row)
        all_issues.extend(issues)

        if not issues:
            examples.append(row_to_training_example(row))

    return examples, all_issues

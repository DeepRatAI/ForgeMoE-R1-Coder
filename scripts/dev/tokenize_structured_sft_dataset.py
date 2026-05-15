from __future__ import annotations

from pathlib import Path
import json
import os
import statistics
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "results/local/structured_sft_dataset_expansion_v0"
OUT_DIR = PROJECT_ROOT / "results/local/structured_sft_tokenization_refresh_v0"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0

    ordered = sorted(values)
    index = round((len(ordered) - 1) * q)
    return ordered[index]


def render_training_text(tokenizer: Any, messages: list[dict[str, str]], target_text: str) -> str:
    full_messages = list(messages) + [{"role": "assistant", "content": target_text}]

    try:
        rendered = tokenizer.apply_chat_template(
            full_messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        if isinstance(rendered, str) and rendered.strip():
            return rendered
    except Exception:
        pass

    parts: list[str] = []
    for message in full_messages:
        role = message["role"]
        content = message["content"]
        parts.append(f"<|{role}|>\n{content}\n")
    return "\n".join(parts)


def validate_source_row(row: dict[str, Any]) -> dict[str, Any]:
    assert row["schema_version"] == "forgeagent.sft_row.v0", row
    assert row["task_id"], row
    assert row["split"] in {"train", "eval"}, row
    assert isinstance(row["messages"], list) and len(row["messages"]) == 2, row
    assert row["messages"][0]["role"] == "system", row
    assert row["messages"][1]["role"] == "user", row
    assert row["target_text"].strip(), row

    target = json.loads(row["target_text"])
    assert target["schema_version"] == "forgeagent.structured_intent.v0", target
    assert target["task_id"] == row["task_id"], target
    assert target["target_files"], target
    assert target["operations"], target
    assert target["verification"], target

    return target


def tokenize_rows(rows: list[dict[str, Any]], tokenizer: Any, max_seq_length: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rendered_rows: list[dict[str, Any]] = []
    token_reports: list[dict[str, Any]] = []

    for row in rows:
        target = validate_source_row(row)
        text = render_training_text(tokenizer, row["messages"], row["target_text"])

        encoded = tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
        )

        token_count = len(encoded["input_ids"])

        rendered = {
            "schema_version": "forgeagent.rendered_sft_row.v0",
            "task_id": row["task_id"],
            "split": row["split"],
            "category": row["category"],
            "difficulty": row["difficulty"],
            "text": text,
            "target_text": row["target_text"],
            "metadata": row["metadata"],
        }

        report = {
            "task_id": row["task_id"],
            "split": row["split"],
            "category": row["category"],
            "difficulty": row["difficulty"],
            "char_count": len(text),
            "token_count": token_count,
            "max_seq_length": max_seq_length,
            "would_truncate": token_count > max_seq_length,
            "target_file_count": len(target["target_files"]),
            "operation_count": len(target["operations"]),
            "verification_count": len(target["verification"]),
        }

        rendered_rows.append(rendered)
        token_reports.append(report)

    return rendered_rows, token_reports


def summarize_token_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    token_counts = [int(item["token_count"]) for item in reports]
    char_counts = [int(item["char_count"]) for item in reports]

    by_category: dict[str, dict[str, Any]] = {}
    for item in reports:
        category = item["category"]
        bucket = by_category.setdefault(category, {"rows": 0, "token_counts": []})
        bucket["rows"] += 1
        bucket["token_counts"].append(int(item["token_count"]))

    for category, bucket in by_category.items():
        values = bucket["token_counts"]
        bucket["min_tokens"] = min(values)
        bucket["max_tokens"] = max(values)
        bucket["mean_tokens"] = round(statistics.mean(values), 3)
        del bucket["token_counts"]

    return {
        "row_count": len(reports),
        "min_tokens": min(token_counts) if token_counts else 0,
        "max_tokens": max(token_counts) if token_counts else 0,
        "mean_tokens": round(statistics.mean(token_counts), 3) if token_counts else 0,
        "median_tokens": percentile(token_counts, 0.50),
        "p95_tokens": percentile(token_counts, 0.95),
        "min_chars": min(char_counts) if char_counts else 0,
        "max_chars": max(char_counts) if char_counts else 0,
        "mean_chars": round(statistics.mean(char_counts), 3) if char_counts else 0,
        "would_truncate_count": sum(1 for item in reports if item["would_truncate"]),
        "by_category": by_category,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    model_id = os.environ.get("FORGEMOE_STEP29_3_MODEL_ID", "Qwen/Qwen2.5-Coder-0.5B-Instruct")
    max_seq_length = int(os.environ.get("FORGEMOE_STEP29_3_MAX_SEQ_LENGTH", "2048"))

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=False)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    all_rows = read_jsonl(SOURCE_DIR / "all.jsonl")
    train_rows = read_jsonl(SOURCE_DIR / "train.jsonl")
    eval_rows = read_jsonl(SOURCE_DIR / "eval.jsonl")
    source_summary = json.loads((SOURCE_DIR / "summary.json").read_text(encoding="utf-8"))

    assert len(all_rows) == 48, len(all_rows)
    assert len(train_rows) == 40, len(train_rows)
    assert len(eval_rows) == 8, len(eval_rows)

    rendered_all, all_reports = tokenize_rows(all_rows, tokenizer, max_seq_length)
    rendered_train, train_reports = tokenize_rows(train_rows, tokenizer, max_seq_length)
    rendered_eval, eval_reports = tokenize_rows(eval_rows, tokenizer, max_seq_length)

    all_summary = summarize_token_reports(all_reports)
    train_summary = summarize_token_reports(train_reports)
    eval_summary = summarize_token_reports(eval_reports)

    assert all_summary["would_truncate_count"] == 0, all_summary
    assert train_summary["would_truncate_count"] == 0, train_summary
    assert eval_summary["would_truncate_count"] == 0, eval_summary

    tokenization_report = {
        "schema_version": "forgeagent.structured_sft_tokenization_report.v0",
        "dataset_name": "structured_sft_tokenization_refresh_v0",
        "source_dataset": "structured_sft_dataset_expansion_v0",
        "model_id": model_id,
        "tokenizer_class": tokenizer.__class__.__name__,
        "max_seq_length": max_seq_length,
        "full_weight_load_attempted": False,
        "launches_training_job": False,
        "gpu_required": False,
        "source_summary": source_summary,
        "all": all_summary,
        "train": train_summary,
        "eval": eval_summary,
        "row_reports": all_reports,
    }

    training_manifest = {
        "schema_version": "forgeagent.structured_sft_training_manifest.v0",
        "dataset_name": "structured_sft_tokenization_refresh_v0",
        "base_model_id": model_id,
        "objective": "structured_edit_intent_sft",
        "target_format": "json_structured_intent",
        "train_rows": len(rendered_train),
        "eval_rows": len(rendered_eval),
        "total_rows": len(rendered_all),
        "max_seq_length": max_seq_length,
        "tokenization_gate": {
            "passed": True,
            "would_truncate_count": all_summary["would_truncate_count"],
            "max_tokens": all_summary["max_tokens"],
            "p95_tokens": all_summary["p95_tokens"],
        },
        "recommended_initial_hyperparameters": {
            "num_train_epochs": 3,
            "learning_rate": 0.0002,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 4,
            "max_seq_length": max_seq_length,
            "lora_r": 8,
            "lora_alpha": 16,
            "lora_dropout": 0.05,
        },
        "artifacts": {
            "rendered_all_jsonl": str(OUT_DIR / "rendered_all.jsonl"),
            "rendered_train_jsonl": str(OUT_DIR / "rendered_train.jsonl"),
            "rendered_eval_jsonl": str(OUT_DIR / "rendered_eval.jsonl"),
            "tokenization_report": str(OUT_DIR / "tokenization_report.json"),
            "training_manifest": str(OUT_DIR / "training_manifest.json"),
        },
        "cost_gate": {
            "launches_training_job": False,
            "requires_explicit_approval_before_launch": True,
        },
    }

    write_jsonl(OUT_DIR / "rendered_all.jsonl", rendered_all)
    write_jsonl(OUT_DIR / "rendered_train.jsonl", rendered_train)
    write_jsonl(OUT_DIR / "rendered_eval.jsonl", rendered_eval)
    write_json(OUT_DIR / "tokenization_report.json", tokenization_report)
    write_json(OUT_DIR / "training_manifest.json", training_manifest)

    print(json.dumps(
        {
            "schema_version": tokenization_report["schema_version"],
            "dataset_name": tokenization_report["dataset_name"],
            "model_id": model_id,
            "tokenizer_class": tokenization_report["tokenizer_class"],
            "total_rows": training_manifest["total_rows"],
            "train_rows": training_manifest["train_rows"],
            "eval_rows": training_manifest["eval_rows"],
            "max_seq_length": max_seq_length,
            "max_tokens": all_summary["max_tokens"],
            "p95_tokens": all_summary["p95_tokens"],
            "would_truncate_count": all_summary["would_truncate_count"],
            "tokenization_gate_passed": training_manifest["tokenization_gate"]["passed"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print("STRUCTURED_SFT_TOKENIZATION_REFRESH_OK")


if __name__ == "__main__":
    main()

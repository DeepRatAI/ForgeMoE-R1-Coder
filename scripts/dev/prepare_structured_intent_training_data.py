from __future__ import annotations

from pathlib import Path
import json
import os
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.training.structured_intent_dataset import (
    compute_tokenization_stats,
    deterministic_train_eval_split,
    load_and_validate_examples,
    render_messages,
    write_jsonl,
)


DATASET_PATH = PROJECT_ROOT / "results/local/structured_intent_sft_dataset_v0/sft_structured_intent.jsonl"
OUT_DIR = PROJECT_ROOT / "results/local/local_adapter_training_plan_v0"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def load_tokenizer(model_id: str) -> Any:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=False,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    return tokenizer


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    model_id = os.environ.get("FORGEMOE_STEP27_MODEL_ID", "Qwen/Qwen2.5-Coder-0.5B-Instruct")

    examples, issues = load_and_validate_examples(DATASET_PATH)

    if issues:
        write_json(OUT_DIR / "validation_issues.json", [issue.to_dict() for issue in issues])
    else:
        write_json(OUT_DIR / "validation_issues.json", [])

    tokenizer = load_tokenizer(model_id)

    train_examples, eval_examples = deterministic_train_eval_split(examples, eval_rows=1)

    train_rows = [example.to_sft_dict() for example in train_examples]
    eval_rows = [example.to_sft_dict() for example in eval_examples]
    all_rows = [example.to_sft_dict() for example in examples]

    write_jsonl(OUT_DIR / "train.jsonl", train_rows)
    write_jsonl(OUT_DIR / "eval.jsonl", eval_rows)
    write_jsonl(OUT_DIR / "all_validated_examples.jsonl", all_rows)

    token_stats = compute_tokenization_stats(examples, tokenizer=tokenizer)

    rendered_preview = []
    for example in examples:
        rendered_preview.append(
            {
                "task_id": example.task_id,
                "rendered_text_preview": render_messages(example.full_messages, tokenizer=tokenizer)[:3000],
            }
        )

    training_manifest = {
        "schema_version": "forgeagent.local_adapter_training_plan.v0",
        "plan_name": "local_adapter_training_plan_v0",
        "source_dataset": str(DATASET_PATH),
        "model_id": model_id,
        "tokenizer_class": tokenizer.__class__.__name__,
        "total_rows": len(examples),
        "validation_issue_count": len(issues),
        "train_rows": len(train_examples),
        "eval_rows": len(eval_examples),
        "training_objective": "predict_repaired_structured_edit_intent_json",
        "adapter_strategy": {
            "first_real_training_method": "lora_sft",
            "base_model_frozen": True,
            "adapter_trainable": True,
            "gpu_required_for_real_training": True,
            "this_step_trains_model": False,
        },
        "recommended_initial_hyperparameters": {
            "num_train_epochs": 3,
            "learning_rate": 0.0002,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 4,
            "max_seq_length": max(128, token_stats.max_tokens + 64),
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "target_modules_note": "select after model architecture inspection; likely q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj for Qwen-like decoder models",
        },
        "artifacts": {
            "train_jsonl": str(OUT_DIR / "train.jsonl"),
            "eval_jsonl": str(OUT_DIR / "eval.jsonl"),
            "all_validated_examples_jsonl": str(OUT_DIR / "all_validated_examples.jsonl"),
            "tokenization_report_json": str(OUT_DIR / "tokenization_report.json"),
            "training_manifest_json": str(OUT_DIR / "training_manifest.json"),
            "rendered_preview_json": str(OUT_DIR / "rendered_preview.json"),
        },
    }

    tokenization_report = {
        "schema_version": "forgeagent.tokenization_report.v0",
        "model_id": model_id,
        "tokenizer_class": tokenizer.__class__.__name__,
        "stats": token_stats.to_dict(),
    }

    write_json(OUT_DIR / "training_manifest.json", training_manifest)
    write_json(OUT_DIR / "tokenization_report.json", tokenization_report)
    write_json(OUT_DIR / "rendered_preview.json", rendered_preview)

    print(json.dumps(
        {
            "schema_version": training_manifest["schema_version"],
            "plan_name": training_manifest["plan_name"],
            "model_id": model_id,
            "total_rows": len(examples),
            "validation_issue_count": len(issues),
            "train_rows": len(train_examples),
            "eval_rows": len(eval_examples),
            "tokenizer_class": tokenizer.__class__.__name__,
            "token_min": token_stats.min_tokens,
            "token_max": token_stats.max_tokens,
            "token_mean": token_stats.mean_tokens,
            "this_step_trains_model": False,
            "training_manifest": str(OUT_DIR / "training_manifest.json"),
            "tokenization_report": str(OUT_DIR / "tokenization_report.json"),
        },
        indent=2,
        ensure_ascii=False,
    ))
    print("LOCAL_ADAPTER_TRAINING_PLAN_PREP_OK")


if __name__ == "__main__":
    main()

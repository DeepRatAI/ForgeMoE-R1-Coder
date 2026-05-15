from __future__ import annotations

from pathlib import Path
import json
import os
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.training.structured_intent_dataset import read_jsonl, render_messages

TRAINING_PLAN_DIR = PROJECT_ROOT / "results/local/local_adapter_training_plan_v0"
OUT_DIR = PROJECT_ROOT / "results/local/local_lora_sft_dry_run_v0"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def count_parameters(model: Any) -> dict[str, int | float]:
    total = 0
    trainable = 0

    for param in model.parameters():
        n = param.numel()
        total += n
        if param.requires_grad:
            trainable += n

    return {
        "total_parameters": total,
        "trainable_parameters": trainable,
        "trainable_percent": round((trainable / total) * 100, 6) if total else 0.0,
    }


def infer_lora_target_modules(model: Any) -> tuple[list[str], list[str]]:
    import torch

    candidate_suffixes = [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ]

    linear_names: list[str] = []
    matched: set[str] = set()

    for name, module in model.named_modules():
        if not isinstance(module, torch.nn.Linear):
            continue

        linear_names.append(name)

        for suffix in candidate_suffixes:
            if name.endswith(suffix):
                matched.add(suffix)

    return sorted(matched), sorted(linear_names)


def tokenize_rows(rows: list[dict[str, Any]], tokenizer: Any, max_length: int) -> list[dict[str, Any]]:
    output = []

    for row in rows:
        rendered = render_messages(row["messages"], tokenizer=tokenizer)
        encoded = tokenizer(
            rendered,
            add_special_tokens=False,
            truncation=True,
            max_length=max_length,
        )

        output.append(
            {
                "task_id": row["task_id"],
                "input_ids_len": len(encoded["input_ids"]),
                "attention_mask_len": len(encoded["attention_mask"]),
                "truncated": len(encoded["input_ids"]) >= max_length,
                "chars": len(rendered),
            }
        )

    return output


def main() -> None:
    started = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    model_id = os.environ.get("FORGEMOE_STEP28_MODEL_ID", "Qwen/Qwen2.5-Coder-0.5B-Instruct")

    training_manifest = load_json(TRAINING_PLAN_DIR / "training_manifest.json")
    tokenization_report = load_json(TRAINING_PLAN_DIR / "tokenization_report.json")

    train_rows = read_jsonl(TRAINING_PLAN_DIR / "train.jsonl")
    eval_rows = read_jsonl(TRAINING_PLAN_DIR / "eval.jsonl")
    all_rows = read_jsonl(TRAINING_PLAN_DIR / "all_validated_examples.jsonl")

    max_seq_length = int(training_manifest["recommended_initial_hyperparameters"]["max_seq_length"])

    import torch
    from transformers import AutoConfig, AutoTokenizer, Qwen2Config, Qwen2ForCausalLM
    from peft import LoraConfig, get_peft_model

    real_config = AutoConfig.from_pretrained(model_id, trust_remote_code=False)

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tiny_config = Qwen2Config(
        vocab_size=1024,
        hidden_size=64,
        intermediate_size=128,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=4,
        max_position_embeddings=1024,
        rope_theta=getattr(real_config, "rope_theta", 1000000.0),
        tie_word_embeddings=getattr(real_config, "tie_word_embeddings", False),
    )

    tiny_model = Qwen2ForCausalLM(tiny_config)
    tiny_model.eval()

    target_modules, linear_module_names = infer_lora_target_modules(tiny_model)

    required = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
    missing = sorted(required.difference(target_modules))
    if missing:
        raise RuntimeError(f"Missing expected Qwen2 LoRA target modules: {missing}")

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=target_modules,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    peft_model = get_peft_model(tiny_model, lora_config)
    peft_model.eval()

    parameter_counts = count_parameters(peft_model)

    train_tokenized = tokenize_rows(train_rows, tokenizer, max_seq_length)
    eval_tokenized = tokenize_rows(eval_rows, tokenizer, max_seq_length)
    all_tokenized = tokenize_rows(all_rows, tokenizer, max_seq_length)

    with torch.no_grad():
        sample = torch.randint(low=0, high=128, size=(1, 16))
        forward = peft_model(input_ids=sample, labels=sample)
        forward_loss = float(forward.loss.detach().cpu().item())

    architecture_report = {
        "schema_version": "forgeagent.lora_architecture_report.v0",
        "mode": "memory_safe_tiny_qwen2_architecture_probe",
        "real_model_id": model_id,
        "real_config_model_type": getattr(real_config, "model_type", None),
        "real_hidden_size": getattr(real_config, "hidden_size", None),
        "real_num_hidden_layers": getattr(real_config, "num_hidden_layers", None),
        "real_num_attention_heads": getattr(real_config, "num_attention_heads", None),
        "tiny_model_class": tiny_model.__class__.__name__,
        "peft_model_class": peft_model.__class__.__name__,
        "tokenizer_class": tokenizer.__class__.__name__,
        "target_modules": target_modules,
        "linear_module_count": len(linear_module_names),
        "linear_module_name_sample": linear_module_names[:80],
        "parameter_counts": parameter_counts,
    }

    dry_run_report = {
        "schema_version": "forgeagent.local_lora_sft_dry_run.v0",
        "dry_run_name": "local_lora_sft_dry_run_v0",
        "mode": "memory_safe_architecture_dry_run",
        "model_id": model_id,
        "device": "cpu",
        "full_weight_load_attempted": False,
        "full_weight_load_reason": "disabled_after_cloudshell_oom_kill",
        "trains_model": False,
        "lora_attached": True,
        "target_modules": target_modules,
        "parameter_counts": parameter_counts,
        "forward_pass": {
            "ran": True,
            "type": "tiny_qwen2_lora_forward",
            "loss": forward_loss,
            "input_tokens": 16,
        },
        "dataset": {
            "train_rows": len(train_rows),
            "eval_rows": len(eval_rows),
            "all_rows": len(all_rows),
            "source_training_manifest": str(TRAINING_PLAN_DIR / "training_manifest.json"),
            "source_tokenization_report": str(TRAINING_PLAN_DIR / "tokenization_report.json"),
            "previous_token_min": tokenization_report["stats"]["min_tokens"],
            "previous_token_max": tokenization_report["stats"]["max_tokens"],
            "previous_token_mean": tokenization_report["stats"]["mean_tokens"],
        },
        "tokenization": {
            "max_seq_length": max_seq_length,
            "train": train_tokenized,
            "eval": eval_tokenized,
            "all": all_tokenized,
            "any_truncated": any(item["truncated"] for item in all_tokenized),
        },
        "elapsed_seconds": round(time.time() - started, 6),
    }

    training_job_spec = {
        "schema_version": "forgeagent.lora_training_job_spec.v0",
        "job_name": "forgemoe-step29-qwen-0-5b-structured-intent-lora-sft",
        "base_model_id": model_id,
        "dataset_s3": {
            "train": "s3://${S3_BUCKET}/results/27_local_adapter_training_plan/v0/train.jsonl",
            "eval": "s3://${S3_BUCKET}/results/27_local_adapter_training_plan/v0/eval.jsonl",
        },
        "output_s3_prefix": "s3://${S3_BUCKET}/models/step29_qwen_0_5b_structured_intent_lora_sft/",
        "recommended_instance": {
            "sagemaker": "ml.g5.xlarge_or_better",
            "reason": "real full-weight load and adapter training should run outside CloudShell",
        },
        "hyperparameters": {
            "num_train_epochs": 3,
            "learning_rate": 0.0002,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 4,
            "max_seq_length": max_seq_length,
            "lora_r": 8,
            "lora_alpha": 16,
            "lora_dropout": 0.05,
            "target_modules": target_modules,
        },
        "promotion_gate": {
            "must_run_post_training_eval": True,
            "required_eval": "replay Step 24/25 structured intent benchmark with trained adapter",
            "minimum_expected_improvement": "more valid unrepaired structured intents than base model",
        },
    }

    write_json(OUT_DIR / "architecture_report.json", architecture_report)
    write_json(OUT_DIR / "dry_run_report.json", dry_run_report)
    write_json(OUT_DIR / "training_job_spec_sagemaker.json", training_job_spec)

    print(json.dumps(
        {
            "schema_version": dry_run_report["schema_version"],
            "mode": dry_run_report["mode"],
            "model_id": model_id,
            "real_config_model_type": architecture_report["real_config_model_type"],
            "lora_attached": dry_run_report["lora_attached"],
            "target_modules": target_modules,
            "trainable_parameters": parameter_counts["trainable_parameters"],
            "trainable_percent": parameter_counts["trainable_percent"],
            "train_rows": len(train_rows),
            "eval_rows": len(eval_rows),
            "max_seq_length": max_seq_length,
            "any_truncated": dry_run_report["tokenization"]["any_truncated"],
            "forward_pass_ran": dry_run_report["forward_pass"]["ran"],
            "elapsed_seconds": dry_run_report["elapsed_seconds"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print("LOCAL_LORA_SFT_DRY_RUN_OK")


if __name__ == "__main__":
    main()

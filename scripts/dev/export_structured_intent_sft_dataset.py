from __future__ import annotations

from pathlib import Path
import json
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "results/local/qwen2_5_coder_0_5b_structured_intent_v0"
REPAIR_DIR = PROJECT_ROOT / "results/local/intent_repair_normalization_v0"
OUT_DIR = PROJECT_ROOT / "results/local/structured_intent_sft_dataset_v0"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def reward_for(row: dict[str, Any]) -> float:
    if row.get("solved") is True:
        return 1.0

    if row.get("patch_apply_passed") is True:
        return -0.25

    return -1.0


def first_generated_text(task_id: str) -> str:
    path = RAW_DIR / "tasks" / task_id / "generated_responses.jsonl"
    rows = read_jsonl(path)
    if not rows:
        return ""
    return str(rows[0].get("text", ""))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_summary = read_json(RAW_DIR / "summary.json")
    repair_summary = read_json(REPAIR_DIR / "summary.json")
    repair_rows = read_jsonl(REPAIR_DIR / "task_results.jsonl")

    sft_rows: list[dict[str, Any]] = []
    trajectory_rows: list[dict[str, Any]] = []

    for repair_row in repair_rows:
        task_id = repair_row["task_id"]

        raw_task_dir = RAW_DIR / "tasks" / task_id
        repair_task_dir = REPAIR_DIR / "tasks" / task_id

        prompt_messages = read_json(raw_task_dir / "prompt_messages.json")
        patch_result = read_json(repair_task_dir / "patch_result.json")
        repair_report = repair_row["repair_report"]

        repaired_intent = repair_report["repaired_intent"]
        original_intent = repair_report["original_intent"]

        target = json.dumps(repaired_intent, indent=2, ensure_ascii=False)

        reward = reward_for(repair_row)
        raw_model_output = first_generated_text(task_id)

        trajectory = {
            "schema_version": "forgeagent.structured_intent_trajectory_record.v0",
            "task_id": task_id,
            "source_model_id": repair_summary["source_model_id"],
            "source_experiment": repair_summary["source_experiment"],
            "raw_model_output": raw_model_output,
            "original_intent": original_intent,
            "original_validation": repair_report["original_validation"],
            "repaired_intent": repaired_intent,
            "repaired_validation": repair_report["repaired_validation"],
            "repair_actions": repair_report["repair_actions"],
            "canonical_patch": patch_result["patch_text"],
            "patch_validation": patch_result["validation"],
            "patch_apply_passed": repair_row["patch_apply_passed"],
            "post_test_passed": repair_row["post_test_passed"],
            "solved": repair_row["solved"],
            "reward": reward,
            "verification": {
                "pre_test": repair_row["pre_test"],
                "patch_apply": repair_row["patch_apply"],
                "post_test": repair_row["post_test"],
            },
        }

        sft_row = {
            "schema_version": "forgeagent.structured_intent_sft_row.v0",
            "task_id": task_id,
            "source_model_id": repair_summary["source_model_id"],
            "training_objective": "predict_repaired_structured_edit_intent_json",
            "messages": [
                *prompt_messages,
                {
                    "role": "assistant",
                    "content": target,
                },
            ],
            "target": target,
            "metadata": {
                "raw_model_output": raw_model_output,
                "original_intent": original_intent,
                "original_validation": repair_report["original_validation"],
                "repaired_intent": repaired_intent,
                "repaired_validation": repair_report["repaired_validation"],
                "repair_actions": repair_report["repair_actions"],
                "canonical_patch": patch_result["patch_text"],
                "reward": reward,
                "solved": repair_row["solved"],
                "patch_apply_passed": repair_row["patch_apply_passed"],
                "post_test_passed": repair_row["post_test_passed"],
            },
        }

        trajectory_rows.append(trajectory)
        sft_rows.append(sft_row)

    positive_rows = [row for row in trajectory_rows if row["reward"] > 0]
    solved_rows = [row for row in trajectory_rows if row["solved"]]

    summary = {
        "schema_version": "forgeagent.structured_intent_sft_dataset_summary.v0",
        "dataset_name": "structured_intent_sft_dataset_v0",
        "source_raw_experiment": raw_summary["experiment_name"],
        "source_repair_experiment": repair_summary["experiment_name"],
        "source_model_id": repair_summary["source_model_id"],
        "total_sft_rows": len(sft_rows),
        "total_trajectory_rows": len(trajectory_rows),
        "positive_reward_rows": len(positive_rows),
        "solved_rows": len(solved_rows),
        "average_reward": round(sum(row["reward"] for row in trajectory_rows) / len(trajectory_rows), 6)
        if trajectory_rows
        else 0.0,
        "all_targets_are_repaired_intents": all(
            row["metadata"]["repaired_intent"] is not None for row in sft_rows
        ),
        "all_rows_have_canonical_patch": all(
            bool(row["canonical_patch"]) for row in trajectory_rows
        ),
        "artifacts": {
            "sft_jsonl": str(OUT_DIR / "sft_structured_intent.jsonl"),
            "trajectory_jsonl": str(OUT_DIR / "trajectory_records.jsonl"),
            "dataset_card": str(OUT_DIR / "dataset_card.md"),
            "summary": str(OUT_DIR / "summary.json"),
        },
    }

    dataset_card = f"""# Structured Intent SFT Dataset v0

## Purpose

This dataset exports the first supervised training rows from the ForgeMoE-R1-Agent-Coder structured-intent trajectory.

The target is repaired structured edit intent JSON, not raw unified diff text.

## Source

- Raw model experiment: `{raw_summary["experiment_name"]}`
- Repair replay experiment: `{repair_summary["experiment_name"]}`
- Source model: `{repair_summary["source_model_id"]}`

## Counts

- SFT rows: `{summary["total_sft_rows"]}`
- Trajectory rows: `{summary["total_trajectory_rows"]}`
- Positive reward rows: `{summary["positive_reward_rows"]}`
- Solved rows: `{summary["solved_rows"]}`
- Average reward: `{summary["average_reward"]}`

## Row Design

Each SFT row contains:

```text
prompt messages -> assistant target repaired structured edit intent JSON
```

Each trajectory record contains:

```text
raw_model_output
original_intent
repaired_intent
canonical_patch
verification_result
reward
```

## Intended Use

This dataset is intended for the first adapter or LoRA supervised fine-tuning pass.
"""

    write_jsonl(OUT_DIR / "sft_structured_intent.jsonl", sft_rows)
    write_jsonl(OUT_DIR / "trajectory_records.jsonl", trajectory_rows)
    write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "dataset_card.md").write_text(dataset_card, encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("STRUCTURED_INTENT_SFT_DATASET_EXPORT_OK")


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
import json

from forgeagentcoder.agent.mock_model import RawModelResponse
from forgeagentcoder.models.types import GeneratedResponse


def generated_responses_to_raw_model_responses(
    responses: list[GeneratedResponse],
) -> list[RawModelResponse]:
    """Bridge Step 18 model contract into the existing Step 15 candidate pipeline.

    The candidate pipeline currently consumes RawModelResponse. This bridge keeps
    backward compatibility while the model layer matures.
    """
    return [
        RawModelResponse(
            response_id=item.response_id,
            text=item.text,
            source=f"{item.adapter_name}:{item.model_id}",
        )
        for item in responses
    ]


def write_generated_responses_jsonl(
    path: str | Path,
    responses: list[GeneratedResponse],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for item in responses:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False, default=str) + "\n")

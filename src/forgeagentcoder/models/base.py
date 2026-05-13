from __future__ import annotations

from typing import Protocol

from forgeagentcoder.models.types import GenerationConfig, GeneratedResponse, ModelMetadata


ChatMessages = list[dict[str, str]]


class ModelAdapter(Protocol):
    """Runtime-independent generation contract.

    Implementations may wrap deterministic mocks, local Transformers models,
    SageMaker endpoints/jobs, vLLM servers, or OpenAI-compatible APIs.
    """

    def metadata(self) -> ModelMetadata:
        ...

    def generate(
        self,
        messages: ChatMessages,
        *,
        config: GenerationConfig,
    ) -> list[GeneratedResponse]:
        ...


def validate_chat_messages(messages: ChatMessages) -> None:
    if not messages:
        raise ValueError("messages must not be empty")

    for index, item in enumerate(messages):
        if not isinstance(item, dict):
            raise ValueError(f"message at index {index} must be a dict")
        if "role" not in item or "content" not in item:
            raise ValueError(f"message at index {index} must contain role and content")
        if item["role"] not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"unsupported role at index {index}: {item['role']}")
        if not isinstance(item["content"], str):
            raise ValueError(f"content at index {index} must be a string")

from __future__ import annotations

from dataclasses import dataclass
import time

from forgeagentcoder.models.base import ChatMessages, validate_chat_messages
from forgeagentcoder.models.types import GenerationConfig, GeneratedResponse, ModelMetadata


@dataclass(frozen=True)
class ScriptedModelOutput:
    response_id: str
    text: str
    finish_reason: str = "stop"


class DeterministicMockModelAdapter:
    """Deterministic ModelAdapter implementation for pipeline validation.

    This is not a model simulator. It is a contract validator that allows the
    agentic pipeline to exercise model I/O, parsing, verification, and metrics
    without downloading weights or using paid GPU resources.
    """

    def __init__(
        self,
        outputs: list[ScriptedModelOutput],
        *,
        model_id: str = "mock-scripted-patch-model",
        adapter_name: str = "deterministic_mock_adapter",
    ) -> None:
        if not outputs:
            raise ValueError("DeterministicMockModelAdapter requires at least one scripted output")

        self._outputs = outputs
        self._metadata = ModelMetadata(
            model_id=model_id,
            adapter_name=adapter_name,
            runtime="mock",
            revision="v0",
            device="none",
            dtype="none",
            context_window=None,
            supports_chat=True,
            supports_batch=True,
            extra={
                "deterministic": True,
                "downloads_weights": False,
                "gpu_required": False,
            },
        )

    def metadata(self) -> ModelMetadata:
        return self._metadata

    def generate(
        self,
        messages: ChatMessages,
        *,
        config: GenerationConfig,
    ) -> list[GeneratedResponse]:
        validate_chat_messages(messages)
        config.validate()

        started = time.time()
        selected = self._outputs[: config.num_return_sequences]
        responses: list[GeneratedResponse] = []

        for item in selected:
            responses.append(
                GeneratedResponse(
                    response_id=item.response_id,
                    text=item.text,
                    model_id=self._metadata.model_id,
                    adapter_name=self._metadata.adapter_name,
                    generation_config=config.to_dict(),
                    metadata=self._metadata.to_dict(),
                    finish_reason=item.finish_reason,
                    latency_seconds=round(time.time() - started, 6),
                    token_counts={
                        "prompt_messages": len(messages),
                        "output_chars": len(item.text),
                    },
                )
            )

        return responses

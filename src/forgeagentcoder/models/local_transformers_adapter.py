from __future__ import annotations

from typing import Any
import time

from forgeagentcoder.models.base import ChatMessages, validate_chat_messages
from forgeagentcoder.models.types import GenerationConfig, GeneratedResponse, ModelMetadata


class LocalTransformersModelAdapter:
    """Local Hugging Face Transformers adapter skeleton.

    Step 18 intentionally does not download or load a real model. This adapter
    defines the runtime boundary for Step 19+.

    Future responsibilities:
    - load tokenizer/model lazily
    - apply chat template when available
    - generate N responses
    - preserve runtime metadata
    - return GeneratedResponse objects
    """

    def __init__(
        self,
        *,
        model_id: str,
        revision: str | None = None,
        device: str = "auto",
        dtype: str = "auto",
        lazy_load: bool = True,
        adapter_name: str = "local_transformers_adapter",
    ) -> None:
        self.model_id = model_id
        self.revision = revision
        self.device = device
        self.dtype = dtype
        self.adapter_name = adapter_name
        self.lazy_load = lazy_load
        self._tokenizer: Any | None = None
        self._model: Any | None = None

        if not lazy_load:
            self.load()

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self.model_id,
            adapter_name=self.adapter_name,
            runtime="local_transformers",
            revision=self.revision,
            device=self.device,
            dtype=self.dtype,
            context_window=None,
            supports_chat=True,
            supports_batch=False,
            extra={
                "lazy_load": self.lazy_load,
                "loaded": self._model is not None,
                "step18_skeleton": True,
            },
        )

    def load(self) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "transformers is not installed or could not be imported. "
                "Install it in a controlled environment before using LocalTransformersModelAdapter."
            ) from exc

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=self.revision,
            trust_remote_code=True,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            revision=self.revision,
            trust_remote_code=True,
            device_map=self.device,
            torch_dtype=self.dtype if self.dtype != "auto" else "auto",
        )

    def generate(
        self,
        messages: ChatMessages,
        *,
        config: GenerationConfig,
    ) -> list[GeneratedResponse]:
        validate_chat_messages(messages)
        config.validate()

        if self._tokenizer is None or self._model is None:
            raise RuntimeError(
                "LocalTransformersModelAdapter is not loaded. "
                "Step 18 only validates the adapter contract. "
                "Use Step 19 to run a controlled tiny-model smoke test."
            )

        started = time.time()

        if hasattr(self._tokenizer, "apply_chat_template"):
            prompt = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

        inputs = self._tokenizer(prompt, return_tensors="pt")
        outputs = self._model.generate(
            **inputs,
            max_new_tokens=config.max_new_tokens,
            do_sample=config.do_sample,
            temperature=config.temperature if config.do_sample else None,
            top_p=config.top_p if config.do_sample else None,
            num_return_sequences=config.num_return_sequences,
        )

        decoded = self._tokenizer.batch_decode(outputs, skip_special_tokens=True)

        responses: list[GeneratedResponse] = []
        for index, text in enumerate(decoded):
            responses.append(
                GeneratedResponse(
                    response_id=f"local_transformers_{index}",
                    text=text,
                    model_id=self.model_id,
                    adapter_name=self.adapter_name,
                    generation_config=config.to_dict(),
                    metadata=self.metadata().to_dict(),
                    finish_reason="stop",
                    latency_seconds=round(time.time() - started, 6),
                    token_counts={
                        "decoded_chars": len(text),
                    },
                )
            )

        return responses

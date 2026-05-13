from __future__ import annotations

from typing import Any
import time

from forgeagentcoder.models.base import ChatMessages, validate_chat_messages
from forgeagentcoder.models.types import GenerationConfig, GeneratedResponse, ModelMetadata


class LocalTransformersModelAdapter:
    """Local Hugging Face Transformers adapter.

    This adapter is intentionally runtime-boundary focused:
    - lazy loading by default
    - explicit trust_remote_code control
    - CPU-safe path for tiny smoke tests
    - metadata preservation for reproducibility
    """

    def __init__(
        self,
        *,
        model_id: str,
        revision: str | None = None,
        device: str = "cpu",
        dtype: str = "auto",
        lazy_load: bool = True,
        trust_remote_code: bool = False,
        adapter_name: str = "local_transformers_adapter",
    ) -> None:
        self.model_id = model_id
        self.revision = revision
        self.device = device
        self.dtype = dtype
        self.adapter_name = adapter_name
        self.lazy_load = lazy_load
        self.trust_remote_code = trust_remote_code
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
                "trust_remote_code": self.trust_remote_code,
            },
        )

    def _torch_dtype(self) -> Any:
        if self.dtype == "auto":
            return "auto"

        try:
            import torch
        except Exception as exc:
            raise RuntimeError("torch is required for LocalTransformersModelAdapter") from exc

        mapping = {
            "float32": torch.float32,
            "fp32": torch.float32,
            "float16": torch.float16,
            "fp16": torch.float16,
            "bfloat16": torch.bfloat16,
            "bf16": torch.bfloat16,
        }

        if self.dtype not in mapping:
            raise ValueError(f"Unsupported dtype: {self.dtype}")

        return mapping[self.dtype]

    def load(self) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "transformers is not installed or could not be imported. "
                "Install it in a controlled environment before using LocalTransformersModelAdapter."
            ) from exc

        tokenizer_kwargs: dict[str, Any] = {
            "revision": self.revision,
            "trust_remote_code": self.trust_remote_code,
        }
        if self.revision is None:
            tokenizer_kwargs.pop("revision")

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            **tokenizer_kwargs,
        )

        model_kwargs: dict[str, Any] = {
            "revision": self.revision,
            "trust_remote_code": self.trust_remote_code,
            "torch_dtype": self._torch_dtype(),
        }
        if self.revision is None:
            model_kwargs.pop("revision")

        if self.device == "auto":
            model_kwargs["device_map"] = "auto"

        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            **model_kwargs,
        )

        if self.device == "cpu":
            self._model.to("cpu")
        elif self.device not in {"auto", "cpu"}:
            self._model.to(self.device)

        self._model.eval()

        if getattr(self._tokenizer, "pad_token_id", None) is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

    def _render_prompt(self, messages: ChatMessages) -> str:
        assert self._tokenizer is not None

        if hasattr(self._tokenizer, "apply_chat_template"):
            try:
                return self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                pass

        return "\n\n".join(f"{m['role'].upper()}:\n{m['content']}" for m in messages) + "\n\nASSISTANT:\n"

    @staticmethod
    def _apply_stop_sequences(text: str, stop_sequences: tuple[str, ...]) -> str:
        if not stop_sequences:
            return text

        cut_points = [text.find(stop) for stop in stop_sequences if stop and text.find(stop) >= 0]
        if not cut_points:
            return text

        return text[: min(cut_points)]

    def generate(
        self,
        messages: ChatMessages,
        *,
        config: GenerationConfig,
    ) -> list[GeneratedResponse]:
        validate_chat_messages(messages)
        config.validate()

        if self._tokenizer is None or self._model is None:
            self.load()

        assert self._tokenizer is not None
        assert self._model is not None

        started = time.time()
        prompt = self._render_prompt(messages)

        inputs = self._tokenizer(prompt, return_tensors="pt")

        try:
            model_device = next(self._model.parameters()).device
            inputs = inputs.to(model_device)
        except Exception:
            pass

        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": config.max_new_tokens,
            "do_sample": config.do_sample,
            "num_return_sequences": config.num_return_sequences,
            "pad_token_id": self._tokenizer.eos_token_id,
        }

        if config.do_sample:
            generation_kwargs["temperature"] = config.temperature
            generation_kwargs["top_p"] = config.top_p
            if config.top_k is not None:
                generation_kwargs["top_k"] = config.top_k
        else:
            generation_kwargs["num_beams"] = 1

        if config.repetition_penalty is not None:
            generation_kwargs["repetition_penalty"] = config.repetition_penalty

        input_len = int(inputs["input_ids"].shape[-1])
        outputs = self._model.generate(
            **inputs,
            **generation_kwargs,
        )

        responses: list[GeneratedResponse] = []

        for index, sequence in enumerate(outputs):
            generated_ids = sequence[input_len:]
            text = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
            text = self._apply_stop_sequences(text, config.stop_sequences)

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
                        "prompt_chars": len(prompt),
                        "output_chars": len(text),
                        "input_tokens": input_len,
                        "output_tokens": int(len(generated_ids)),
                    },
                )
            )

        return responses

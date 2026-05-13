from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import time


@dataclass(frozen=True)
class GenerationConfig:
    max_new_tokens: int = 512
    temperature: float = 0.2
    top_p: float = 0.95
    top_k: int | None = None
    do_sample: bool = True
    num_return_sequences: int = 1
    stop_sequences: tuple[str, ...] = ()
    seed: int | None = None
    repetition_penalty: float | None = None

    def validate(self) -> None:
        if self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive")
        if self.temperature < 0:
            raise ValueError("temperature must be >= 0")
        if not 0 < self.top_p <= 1:
            raise ValueError("top_p must be in (0, 1]")
        if self.top_k is not None and self.top_k < 0:
            raise ValueError("top_k must be >= 0 when provided")
        if self.num_return_sequences <= 0:
            raise ValueError("num_return_sequences must be positive")
        if self.repetition_penalty is not None and self.repetition_penalty <= 0:
            raise ValueError("repetition_penalty must be positive when provided")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["stop_sequences"] = list(self.stop_sequences)
        return data


@dataclass(frozen=True)
class ModelMetadata:
    model_id: str
    adapter_name: str
    runtime: str
    revision: str | None = None
    device: str | None = None
    dtype: str | None = None
    context_window: int | None = None
    supports_chat: bool = True
    supports_batch: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeneratedResponse:
    response_id: str
    text: str
    model_id: str
    adapter_name: str
    generation_config: dict[str, Any]
    metadata: dict[str, Any]
    finish_reason: str = "stop"
    latency_seconds: float = 0.0
    token_counts: dict[str, int] = field(default_factory=dict)
    created_unix_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawModelResponse:
    response_id: str
    text: str
    source: str = "mock_model"


class MockPatchModel:
    """Deterministic model adapter used to validate the agentic generation contract."""

    def __init__(self, responses: list[RawModelResponse]) -> None:
        if not responses:
            raise ValueError("MockPatchModel requires at least one response")
        self._responses = responses

    def generate(self, messages: list[dict[str, str]], *, n: int | None = None) -> list[RawModelResponse]:
        if not messages:
            raise ValueError("messages must not be empty")
        if n is None:
            return list(self._responses)
        return list(self._responses[:n])

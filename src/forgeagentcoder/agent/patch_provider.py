from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PatchCandidate:
    patch_id: str
    patch_path: Path
    source: str = "scripted"
    description: str = ""


class ScriptedPatchProvider:
    """Deterministic patch provider for model-free loop validation."""

    def __init__(self, candidates: list[PatchCandidate]) -> None:
        if not candidates:
            raise ValueError("ScriptedPatchProvider requires at least one candidate")
        self._candidates = candidates

    def get_candidate(self, iteration: int) -> PatchCandidate | None:
        if iteration < 0:
            raise ValueError("iteration must be >= 0")
        if iteration >= len(self._candidates):
            return None
        return self._candidates[iteration]

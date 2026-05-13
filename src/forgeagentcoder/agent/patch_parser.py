from __future__ import annotations

from pathlib import Path
import re


_CODE_FENCE_RE = re.compile(
    r"```(?:diff|patch)?\s*\n(.*?)```",
    flags=re.DOTALL | re.IGNORECASE,
)


def extract_unified_diff(raw_response: str) -> str:
    """Extract a unified diff from a raw model response.

    Accepts:
    - raw patch beginning with diff --git
    - fenced markdown block ```diff ... ```
    """
    candidates = _CODE_FENCE_RE.findall(raw_response)

    for candidate in candidates:
        candidate = candidate.strip()
        if "diff --git " in candidate:
            return _normalize_patch(candidate)

    idx = raw_response.find("diff --git ")
    if idx >= 0:
        return _normalize_patch(raw_response[idx:].strip())

    raise ValueError("No unified diff found in model response")


def _normalize_patch(patch: str) -> str:
    patch = patch.replace("\r\n", "\n").replace("\r", "\n").strip()
    return patch + "\n"


def validate_unified_diff_shape(patch: str) -> None:
    if not patch.startswith("diff --git "):
        raise ValueError("Patch must start with 'diff --git '")
    if "\n--- " not in patch:
        raise ValueError("Patch missing old-file marker '--- '")
    if "\n+++ " not in patch:
        raise ValueError("Patch missing new-file marker '+++ '")
    if "\n@@" not in patch:
        raise ValueError("Patch missing hunk marker '@@'")


def write_patch(path: str | Path, patch: str) -> None:
    validate_unified_diff_shape(patch)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(patch, encoding="utf-8")

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import difflib
import json
from typing import Any


@dataclass(frozen=True)
class EditIntent:
    intent_id: str
    task_id: str
    file_path: str
    find_text: str
    replace_text: str
    rationale: str = ""

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "EditIntent":
        return EditIntent(
            intent_id=str(data["intent_id"]),
            task_id=str(data["task_id"]),
            file_path=str(data["file_path"]),
            find_text=str(data["find_text"]),
            replace_text=str(data["replace_text"]),
            rationale=str(data.get("rationale", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IntentValidationResult:
    intent_id: str
    task_id: str
    valid: bool
    file_exists: bool
    find_text_occurrences: int
    edits_tests: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalPatchResult:
    intent: EditIntent
    validation: IntentValidationResult
    patch_text: str
    old_text: str
    new_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "validation": self.validation.to_dict(),
            "patch_text": self.patch_text,
            "old_text": self.old_text,
            "new_text": self.new_text,
        }


def parse_json_intent(text: str) -> EditIntent:
    stripped = text.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    return EditIntent.from_dict(json.loads(stripped))


def validate_intent(repo_dir: str | Path, intent: EditIntent) -> IntentValidationResult:
    repo = Path(repo_dir).resolve()
    target = (repo / intent.file_path).resolve()

    try:
        target.relative_to(repo)
    except ValueError:
        return IntentValidationResult(
            intent_id=intent.intent_id,
            task_id=intent.task_id,
            valid=False,
            file_exists=False,
            find_text_occurrences=0,
            edits_tests=False,
            error="file_path_escapes_repo",
        )

    edits_tests = intent.file_path.startswith("tests/") or "/tests/" in intent.file_path

    if not target.exists():
        return IntentValidationResult(
            intent_id=intent.intent_id,
            task_id=intent.task_id,
            valid=False,
            file_exists=False,
            find_text_occurrences=0,
            edits_tests=edits_tests,
            error="file_missing",
        )

    text = target.read_text(encoding="utf-8", errors="replace")
    occurrences = text.count(intent.find_text)

    if edits_tests:
        error = "test_file_edit_forbidden"
    elif occurrences == 0:
        error = "find_text_not_found"
    elif occurrences > 1:
        error = "find_text_not_unique"
    elif not intent.replace_text:
        error = "empty_replace_text"
    else:
        error = None

    return IntentValidationResult(
        intent_id=intent.intent_id,
        task_id=intent.task_id,
        valid=error is None,
        file_exists=True,
        find_text_occurrences=occurrences,
        edits_tests=edits_tests,
        error=error,
    )


def build_canonical_patch(repo_dir: str | Path, intent: EditIntent) -> CanonicalPatchResult:
    repo = Path(repo_dir).resolve()
    target = repo / intent.file_path

    validation = validate_intent(repo, intent)

    if not validation.valid:
        return CanonicalPatchResult(
            intent=intent,
            validation=validation,
            patch_text="",
            old_text="",
            new_text="",
        )

    old_text = target.read_text(encoding="utf-8", errors="replace")
    new_text = old_text.replace(intent.find_text, intent.replace_text, 1)

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{intent.file_path}",
            tofile=f"b/{intent.file_path}",
            lineterm="",
        )
    )

    body = "\n".join(diff_lines)
    if body and not body.endswith("\n"):
        body += "\n"

    patch = f"diff --git a/{intent.file_path} b/{intent.file_path}\n{body}"

    return CanonicalPatchResult(
        intent=intent,
        validation=validation,
        patch_text=patch,
        old_text=old_text,
        new_text=new_text,
    )

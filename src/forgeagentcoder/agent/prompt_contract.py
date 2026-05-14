from __future__ import annotations

from pathlib import Path
from typing import Any

from forgeagentcoder.data.task_schema import AgentTask


def _read_text(path: Path, max_chars: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def infer_patch_target_files(task: AgentTask, *, max_files: int = 8) -> list[Path]:
    repo_dir = Path(task.repo_dir).resolve()

    candidates: list[Path] = []

    for path in sorted(repo_dir.rglob("*.py")):
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        rel = path.relative_to(repo_dir)
        rel_str = str(rel)

        if rel_str.startswith("tests/"):
            continue
        if rel.name == "__init__.py":
            continue

        candidates.append(path)

    if not candidates:
        for path in sorted(repo_dir.rglob("*.py")):
            if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
                continue
            rel = path.relative_to(repo_dir)
            if str(rel).startswith("tests/"):
                continue
            candidates.append(path)

    return candidates[:max_files]


def build_strict_unified_diff_messages(
    task: AgentTask,
    *,
    pre_test_stderr: str = "",
    max_file_chars: int = 4000,
    max_files: int = 8,
) -> list[dict[str, str]]:
    repo_dir = Path(task.repo_dir).resolve()
    target_files = infer_patch_target_files(task, max_files=max_files)

    file_sections: list[str] = []
    allowed_paths: list[str] = []

    for path in target_files:
        rel = path.relative_to(repo_dir)
        allowed_paths.append(str(rel))
        file_sections.append(
            "\n".join(
                [
                    f"### FILE: {rel}",
                    "```python",
                    _read_text(path, max_chars=max_file_chars),
                    "```",
                ]
            )
        )

    allowed_paths_text = "\n".join(f"- {item}" for item in allowed_paths) or "- <none>"

    system = """You are a repository patching engine.

You must output exactly one unified diff patch.

Hard output rules:
- Output only a unified diff.
- Do not use Markdown fences.
- Do not include prose.
- Do not explain.
- Do not invent files.
- Do not edit files outside the allowed file list.
- Use existing repository paths exactly.
- Each hunk must target existing lines from the provided file content.
- Prefer the smallest possible patch.
- A valid patch must be applicable with `git apply`.

Unified diff shape:
diff --git a/<path> b/<path>
--- a/<path>
+++ b/<path>
@@
-<old existing line>
+<new replacement line>
"""

    user = f"""Task id: {task.task_id}
Title: {task.title}
Description: {task.description}

Test command:
{task.test_command}

Failing test stderr:
{pre_test_stderr[-3000:]}

Allowed files to edit:
{allowed_paths_text}

Repository files:
{chr(10).join(file_sections)}

Return one minimal unified diff patch that fixes the failing tests.
Remember:
- Edit only the allowed file paths.
- Do not edit app/__init__.py unless it appears in the allowed file list.
- Do not create new classes, example apps, or unrelated code.
- Do not add imports unless required.
- The patch must change the buggy implementation, not the tests.
"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def summarize_prompt_contract() -> dict[str, Any]:
    return {
        "name": "strict_unified_diff_patch_contract_v1",
        "output": "unified_diff_only",
        "markdown_allowed": False,
        "prose_allowed": False,
        "wrong_file_edits_allowed": False,
        "new_files_allowed_by_default": False,
        "primary_metric": "patch_apply_success_count",
    }

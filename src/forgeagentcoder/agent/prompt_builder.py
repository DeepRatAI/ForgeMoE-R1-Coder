from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

from forgeagentcoder.data.task_schema import AgentTask


DEFAULT_INCLUDE_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
}


@dataclass(frozen=True)
class RepoContextFile:
    path: str
    text: str
    truncated: bool


def _should_include_file(path: Path) -> bool:
    if path.name.startswith("."):
        return False
    if any(part in {".git", "__pycache__", "node_modules", ".venv", "venv"} for part in path.parts):
        return False
    return path.suffix in DEFAULT_INCLUDE_SUFFIXES


def collect_repo_context(
    repo_dir: str | Path,
    *,
    max_files: int = 20,
    max_file_chars: int = 4000,
) -> list[RepoContextFile]:
    repo_dir = Path(repo_dir)
    files: list[RepoContextFile] = []

    for path in sorted(repo_dir.rglob("*")):
        if not path.is_file():
            continue
        if not _should_include_file(path):
            continue

        rel = path.relative_to(repo_dir).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_file_chars
        if truncated:
            text = text[:max_file_chars] + "\n...[TRUNCATED]..."

        files.append(RepoContextFile(path=rel, text=text, truncated=truncated))

        if len(files) >= max_files:
            break

    return files


def render_repo_tree(files: list[RepoContextFile]) -> str:
    if not files:
        return "(no files included)"
    return "\n".join(f"- {item.path}" for item in files)


def render_file_context(files: list[RepoContextFile]) -> str:
    chunks: list[str] = []

    for item in files:
        chunks.append(f"### File: {item.path}\n```text\n{item.text}\n```")

    return "\n\n".join(chunks)


def build_patch_generation_messages(
    task: AgentTask,
    *,
    pre_test_stderr: str,
    previous_failure_stderr: str = "",
    max_files: int = 20,
    max_file_chars: int = 4000,
) -> list[dict[str, str]]:
    files = collect_repo_context(
        task.repo_dir,
        max_files=max_files,
        max_file_chars=max_file_chars,
    )

    system = (
        "You are an expert fullstack software engineering agent. "
        "You edit repositories by producing minimal unified diff patches. "
        "Return only a valid unified diff patch. Do not include prose."
    )

    user = f"""Task ID: {task.task_id}
Title: {task.title}
Task type: {task.task_type}

Description:
{task.description}

Test command:
{task.test_command}

Repository tree:
{render_repo_tree(files)}

Relevant file context:
{render_file_context(files)}

Current test failure:
```text
{pre_test_stderr}
```

Previous failed attempt feedback:
```text
{previous_failure_stderr}
```

Output contract:
Return only a unified diff patch beginning with diff --git.
"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def write_messages_json(path: str | Path, messages: list[dict[str, str]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(messages, indent=2, ensure_ascii=False), encoding="utf-8")


def messages_to_dict(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(item) for item in messages]


def context_files_to_dict(files: list[RepoContextFile]) -> list[dict]:
    return [asdict(item) for item in files]

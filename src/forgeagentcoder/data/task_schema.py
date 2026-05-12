from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class AgentTask:
    schema_version: str
    task_id: str
    title: str
    repo_dir: Path
    test_command: str
    timeout_seconds: int
    task_type: str = "unit_bugfix"
    description: str = ""

    @classmethod
    def from_json_file(cls, path: str | Path) -> "AgentTask":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data, base_dir=path.parent)

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, base_dir: Path | None = None) -> "AgentTask":
        required = [
            "schema_version",
            "task_id",
            "title",
            "repo_dir",
            "test_command",
            "timeout_seconds",
        ]
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"Missing required task fields: {missing}")

        repo_dir = Path(data["repo_dir"])
        if base_dir is not None and not repo_dir.is_absolute():
            repo_dir = (base_dir / repo_dir).resolve()

        return cls(
            schema_version=str(data["schema_version"]),
            task_id=str(data["task_id"]),
            title=str(data["title"]),
            repo_dir=repo_dir,
            test_command=str(data["test_command"]),
            timeout_seconds=int(data["timeout_seconds"]),
            task_type=str(data.get("task_type", "unit_bugfix")),
            description=str(data.get("description", "")),
        )

    def validate(self) -> None:
        if self.schema_version != "forgeagent.task.v0":
            raise ValueError(f"Unsupported schema_version: {self.schema_version}")
        if not self.repo_dir.exists():
            raise FileNotFoundError(f"repo_dir does not exist: {self.repo_dir}")
        if not self.repo_dir.is_dir():
            raise NotADirectoryError(f"repo_dir is not a directory: {self.repo_dir}")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

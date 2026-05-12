from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import platform
import subprocess
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None


def base_manifest(*, project: str, stage: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = {
        "project": project,
        "stage": stage,
        "created_at_utc": utc_now_iso(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "git_commit": git_commit(),
    }
    if extra:
        manifest.update(extra)
    return manifest


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

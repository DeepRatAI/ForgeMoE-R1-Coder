from __future__ import annotations

from pathlib import Path
import json
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.utils.run_registry import (
    build_run_registry,
    current_git_commit,
    write_registry_json,
    write_registry_markdown,
)


def main() -> None:
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise SystemExit("Missing S3_BUCKET env var. Run: source ~/forgemoe-aws.env")

    git_commit = current_git_commit()

    registry = build_run_registry(
        bucket=bucket,
        git_commit=git_commit,
    )

    output_dir = PROJECT_ROOT / "reports" / "local"
    json_path = output_dir / "run_registry.json"
    md_path = output_dir / "run_registry.md"

    write_registry_json(registry, json_path)
    write_registry_markdown(registry, md_path)

    summary = {
        "project": registry.project,
        "registry_version": registry.registry_version,
        "git_commit": registry.git_commit,
        "entry_count": len(registry.entries),
        "steps": [entry.step for entry in registry.entries],
        "json_path": str(json_path),
        "md_path": str(md_path),
    }

    print(json.dumps(summary, indent=2))

    if len(registry.entries) != 11:
        raise SystemExit("Expected 11 registry entries for steps 9-18 including Step 17.6")

    print("RUN_REGISTRY_BUILD_OK")


if __name__ == "__main__":
    main()

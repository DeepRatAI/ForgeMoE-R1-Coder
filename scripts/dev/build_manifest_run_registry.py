from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import subprocess
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RegistryEntry:
    display_step: str
    sort_key: int
    stage: str
    git_commit: str | None
    result: str | None
    gpu_required: bool | None
    h100_purchase_required: bool | None
    s3_artifact: str | None
    manifest_file: str
    local_test: dict[str, Any]
    components: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "display_step": self.display_step,
            "sort_key": self.sort_key,
            "stage": self.stage,
            "git_commit": self.git_commit,
            "result": self.result,
            "gpu_required": self.gpu_required,
            "h100_purchase_required": self.h100_purchase_required,
            "s3_artifact": self.s3_artifact,
            "manifest_file": self.manifest_file,
            "local_test": self.local_test,
            "components": self.components,
        }


def parse_step(stage: str, filename: str) -> tuple[str, int]:
    text = stage or filename

    match = re.search(r"step(\d+)(?:[_-](\d+))?", text)
    if not match:
        return "unknown", 999999

    major = int(match.group(1))
    minor_text = match.group(2)

    if minor_text is None:
        return str(major), major * 10

    minor = int(minor_text)
    return f"{major}.{minor}", major * 10 + minor


def load_manifest(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    if data.get("project") != "ForgeMoE-R1-Agent-Coder":
        return None

    if "stage" not in data:
        return None

    return data


def manifest_to_entry(path: Path, data: dict[str, Any]) -> RegistryEntry:
    stage = str(data.get("stage"))
    display_step, sort_key = parse_step(stage, path.name)
    local_test = data.get("local_test") or {}

    result = None
    if isinstance(local_test, dict):
        result = local_test.get("result")

    components = data.get("components") or []
    if not isinstance(components, list):
        components = []

    return RegistryEntry(
        display_step=display_step,
        sort_key=sort_key,
        stage=stage,
        git_commit=data.get("git_commit"),
        result=result,
        gpu_required=data.get("gpu_required"),
        h100_purchase_required=data.get("h100_purchase_required"),
        s3_artifact=data.get("s3_artifact"),
        manifest_file=str(path),
        local_test=local_test if isinstance(local_test, dict) else {},
        components=[str(item) for item in components],
    )


def build_registry(manifest_dir: Path, output_dir: Path) -> dict[str, Any]:
    entries: list[RegistryEntry] = []

    for path in sorted(manifest_dir.rglob("*manifest.json")):
        data = load_manifest(path)
        if data is None:
            continue
        entries.append(manifest_to_entry(path, data))

    deduped: dict[str, RegistryEntry] = {}
    for entry in entries:
        deduped[entry.stage] = entry

    entries = sorted(deduped.values(), key=lambda item: (item.sort_key, item.stage))

    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        git_commit = None

    registry = {
        "project": "ForgeMoE-R1-Agent-Coder",
        "registry_version": "manifest_derived_v1",
        "git_commit": git_commit,
        "entry_count": len(entries),
        "steps": [entry.display_step for entry in entries],
        "entries": [entry.to_dict() for entry in entries],
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "run_registry.json"
    md_path = output_dir / "run_registry.md"

    json_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    lines = [
        "# ForgeMoE-R1-Agent-Coder Run Registry",
        "",
        f"Registry version: {registry['registry_version']}",
        f"Git commit: {registry['git_commit']}",
        f"Entry count: {registry['entry_count']}",
        "",
        "## Entries",
        "",
    ]

    for entry in entries:
        lines.extend(
            [
                f"### Step {entry.display_step} - {entry.stage}",
                "",
                f"- Result: {entry.result}",
                f"- Git commit: {entry.git_commit}",
                f"- GPU required: {entry.gpu_required}",
                f"- H100 purchase required: {entry.h100_purchase_required}",
                f"- S3 artifact: {entry.s3_artifact}",
                f"- Manifest file: {entry.manifest_file}",
                "",
            ]
        )

    md_path.write_text("\n".join(lines), encoding="utf-8")

    registry["json_path"] = str(json_path)
    registry["md_path"] = str(md_path)

    return registry


def main() -> None:
    manifest_dir = PROJECT_ROOT / "reports/local/manifest_cache"
    output_dir = PROJECT_ROOT / "reports/local"

    registry = build_registry(manifest_dir, output_dir)

    print(json.dumps(
        {
            "project": registry["project"],
            "registry_version": registry["registry_version"],
            "git_commit": registry["git_commit"],
            "entry_count": registry["entry_count"],
            "steps": registry["steps"],
            "json_path": registry["json_path"],
            "md_path": registry["md_path"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print("MANIFEST_RUN_REGISTRY_BUILD_OK")


if __name__ == "__main__":
    main()

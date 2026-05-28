from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "results/local/private_heldout_seed_set_v1"
RUN_DIR = PROJECT_ROOT / "tmp/private_heldout_seed_set_v1_runs"
STEP29_9_EXPORT_DIR = PROJECT_ROOT / "results/local/internal_synthetic_micro_generator_v0/dataset_exports"
STEP29_11_EXPORT_DIR = PROJECT_ROOT / "results/local/agentic_trajectory_recorder_v1/dataset_exports"

TRAINING_EXPORT_PATHS = [
    STEP29_9_EXPORT_DIR / "patch_sft_train.jsonl",
    STEP29_9_EXPORT_DIR / "trajectory_sft_train_seed.jsonl",
    STEP29_9_EXPORT_DIR / "preference_pairs_train_seed.jsonl",
    STEP29_11_EXPORT_DIR / "trajectory_sft_train.jsonl",
    STEP29_11_EXPORT_DIR / "repair_trace_train.jsonl",
    STEP29_11_EXPORT_DIR / "trajectory_preference_train.jsonl",
]

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\\s*[:=]"),
}


@dataclass(frozen=True)
class PrivateHeldoutTaskDefinition:
    task_id: str
    task_family: str
    function_name: str
    before_body: str
    golden_body: str
    rejected_body: str
    public_overfit_body: str
    public_test_body: str
    hidden_test_body: str
    instruction: str
    difficulty_label: str
    behavioral_axes: tuple[str, ...]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_py(text: str) -> str:
    return text.strip() + "\n"


def run_command(command: list[str], cwd: Path, timeout_seconds: int = 30) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_seconds": round(time.time() - started, 6),
            "timed_out": False,
            "passed": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "elapsed_seconds": round(time.time() - started, 6),
            "timed_out": True,
            "passed": False,
        }


def ensure_passed(result: dict[str, Any], context: str) -> None:
    if result["passed"]:
        return
    raise RuntimeError(
        f"{context} failed with exit code {result['exit_code']}\n"
        f"command: {' '.join(result['command'])}\n"
        f"cwd: {result['cwd']}\n"
        f"stdout:\n{result.get('stdout') or ''}\n"
        f"stderr:\n{result.get('stderr') or ''}"
    )


def init_git_repo(work_dir: Path, actor: str) -> None:
    ensure_passed(run_command(["git", "init", "-q"], cwd=work_dir), "git init")
    ensure_passed(
        run_command(["git", "config", "user.email", "forge@example.invalid"], cwd=work_dir),
        "git config user.email",
    )
    ensure_passed(
        run_command(["git", "config", "user.name", actor], cwd=work_dir),
        "git config user.name",
    )
    ensure_passed(run_command(["git", "add", "."], cwd=work_dir), "git add baseline")
    ensure_passed(run_command(["git", "commit", "-q", "-m", "baseline"], cwd=work_dir), "git commit")


def create_repo(repo_dir: Path, task: PrivateHeldoutTaskDefinition, body: str) -> None:
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    write_text(repo_dir / "app/__init__.py", f"from .utils import {task.function_name}\n")
    write_text(repo_dir / "app/utils.py", normalize_py(body))
    write_text(repo_dir / "tests/test_public.py", task.public_test_body.strip() + "\n")


def make_patch(task: PrivateHeldoutTaskDefinition, label: str, after_body: str) -> str:
    patch_seed = hashlib.sha256(
        f"{task.task_id}\n{label}\n{normalize_py(task.before_body)}\n{normalize_py(after_body)}".encode(
            "utf-8"
        )
    ).hexdigest()[:16]
    patch_repo = RUN_DIR / "patch_build_repos" / patch_seed
    if patch_repo.exists():
        shutil.rmtree(patch_repo)

    write_text(patch_repo / "app/utils.py", normalize_py(task.before_body))
    init_git_repo(patch_repo, "Forge Private Heldout Generator")
    write_text(patch_repo / "app/utils.py", normalize_py(after_body))
    diff_result = run_command(["git", "diff", "--", "app/utils.py"], cwd=patch_repo)
    ensure_passed(diff_result, f"git diff for {task.task_id}:{label}")
    patch_text = diff_result["stdout"]
    has_real_change = any(
        (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
        for line in patch_text.splitlines()
    )
    if not patch_text.strip() or not has_real_change:
        raise RuntimeError(f"empty or non-actionable patch for {task.task_id}:{label}")
    return patch_text if patch_text.endswith("\n") else patch_text + "\n"


def changed_files_from_patch(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        parts = line.split()
        if len(parts) >= 4 and parts[3].startswith("b/"):
            files.append(parts[3][2:])
    return files


def compact_command_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": result["command"],
        "exit_code": result["exit_code"],
        "passed": result["passed"],
        "timed_out": result["timed_out"],
        "stdout_sha256": sha256_text(result.get("stdout", "")),
        "stderr_sha256": sha256_text(result.get("stderr", "")),
    }


def verify_patch(task_dir: Path, task: PrivateHeldoutTaskDefinition, label: str, patch_path: Path) -> dict[str, Any]:
    work_dir = RUN_DIR / "verification" / task.task_id / label
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(task_dir / "repo_before", work_dir)
    init_git_repo(work_dir, "Forge Private Heldout Verifier")

    pre_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)

    local_patch = work_dir / "_candidate.patch"
    shutil.copy2(patch_path, local_patch)
    patch_text = local_patch.read_text(encoding="utf-8")
    patch_check = run_command(["git", "apply", "--check", local_patch.name], cwd=work_dir)
    if patch_check["passed"]:
        patch_apply = run_command(["git", "apply", local_patch.name], cwd=work_dir)
    else:
        patch_apply = {
            "command": ["git", "apply", local_patch.name],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "git apply --check failed; apply skipped.\n" + (patch_check.get("stderr") or ""),
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }

    if patch_apply["passed"]:
        changed_files_result = run_command(["git", "diff", "--name-only"], cwd=work_dir)
        post_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
        shutil.copy2(task_dir / "hidden_tests/test_hidden.py", work_dir / "tests/test_hidden.py")
        post_hidden = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
    else:
        changed_files_result = {
            "command": ["git", "diff", "--name-only"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; changed-file listing skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }
        post_public = {
            "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; public post-test skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }
        post_hidden = {
            "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
            "cwd": str(work_dir),
            "exit_code": 1,
            "stdout": "",
            "stderr": "Patch did not apply; hidden post-test skipped.",
            "elapsed_seconds": 0.0,
            "timed_out": False,
            "passed": False,
        }

    observed_changed_files = [
        line.strip()
        for line in changed_files_result.get("stdout", "").splitlines()
        if line.strip()
    ]
    changed_files = observed_changed_files or changed_files_from_patch(patch_text)
    edit_scope_ok = bool(changed_files) and set(changed_files).issubset({"app/utils.py"})

    return {
        "schema_version": "forgeagent.private_heldout_patch_result.v1",
        "task_id": task.task_id,
        "split": "private_heldout",
        "challenge": label,
        "patch_sha256": sha256_text(patch_text),
        "patch_bytes": len(patch_text.encode("utf-8")),
        "changed_files": changed_files,
        "expected_files": ["app/utils.py"],
        "edit_scope_ok": edit_scope_ok,
        "pre_public_failed_as_expected": not pre_public["passed"],
        "patch_check_passed": patch_check["passed"],
        "patch_applied": patch_apply["passed"],
        "post_public_passed": post_public["passed"],
        "post_hidden_passed": post_hidden["passed"],
        "solved": (not pre_public["passed"])
        and patch_apply["passed"]
        and post_public["passed"]
        and post_hidden["passed"]
        and edit_scope_ok,
        "pre_public": compact_command_result(pre_public),
        "patch_check": compact_command_result(patch_check),
        "patch_apply": compact_command_result(patch_apply),
        "post_public": compact_command_result(post_public),
        "post_hidden": compact_command_result(post_hidden),
    }


def build_tasks() -> list[PrivateHeldoutTaskDefinition]:
    return [
        PrivateHeldoutTaskDefinition(
            task_id="forge-private-heldout-clamp-int",
            task_family="boundary_condition_bugfix",
            function_name="clamp_int",
            before_body="""
def clamp_int(value: int, lower: int, upper: int) -> int:
    return value
""",
            golden_body="""
def clamp_int(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))
""",
            rejected_body="""
def clamp_int(value: int, lower: int, upper: int) -> int:
    return upper
""",
            public_overfit_body="""
def clamp_int(value: int, lower: int, upper: int) -> int:
    return lower
""",
            public_test_body="""
import unittest
from app.utils import clamp_int

class TestClampIntPublic(unittest.TestCase):
    def test_below_lower_bound(self):
        self.assertEqual(clamp_int(-5, 0, 10), 0)
""",
            hidden_test_body="""
import unittest
from app.utils import clamp_int

class TestClampIntHidden(unittest.TestCase):
    def test_inside_and_above_range(self):
        self.assertEqual(clamp_int(7, 0, 10), 7)
        self.assertEqual(clamp_int(15, 0, 10), 10)
""",
            instruction="Fix clamp_int so it constrains value to the inclusive lower and upper bounds.",
            difficulty_label="micro_private",
            behavioral_axes=("boundary_values", "public_overfit_resistance"),
        ),
        PrivateHeldoutTaskDefinition(
            task_id="forge-private-heldout-normalize-spaces",
            task_family="string_normalization_bugfix",
            function_name="normalize_spaces",
            before_body="""
def normalize_spaces(text: str) -> str:
    return text
""",
            golden_body="""
def normalize_spaces(text: str) -> str:
    return " ".join(text.split())
""",
            rejected_body="""
def normalize_spaces(text: str) -> str:
    return text.strip()
""",
            public_overfit_body="""
def normalize_spaces(text: str) -> str:
    if text == "alpha  beta":
        return "alpha beta"
    return text
""",
            public_test_body="""
import unittest
from app.utils import normalize_spaces

class TestNormalizeSpacesPublic(unittest.TestCase):
    def test_double_space(self):
        self.assertEqual(normalize_spaces("alpha  beta"), "alpha beta")
""",
            hidden_test_body="""
import unittest
from app.utils import normalize_spaces

class TestNormalizeSpacesHidden(unittest.TestCase):
    def test_tabs_edges_and_repeated_spaces(self):
        self.assertEqual(normalize_spaces("  alpha\\t beta   gamma  "), "alpha beta gamma")
        self.assertEqual(normalize_spaces("\\nsolo\\n"), "solo")
""",
            instruction="Fix normalize_spaces so it collapses all whitespace runs and trims the result.",
            difficulty_label="micro_private",
            behavioral_axes=("string_whitespace", "input_generalization"),
        ),
        PrivateHeldoutTaskDefinition(
            task_id="forge-private-heldout-dedupe-order",
            task_family="collection_semantics_bugfix",
            function_name="dedupe_preserve_order",
            before_body="""
def dedupe_preserve_order(values: list[int]) -> list[int]:
    return values
""",
            golden_body="""
def dedupe_preserve_order(values: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
""",
            rejected_body="""
def dedupe_preserve_order(values: list[int]) -> list[int]:
    return []
""",
            public_overfit_body="""
def dedupe_preserve_order(values: list[int]) -> list[int]:
    if values == [1, 1, 2]:
        return [1, 2]
    return values
""",
            public_test_body="""
import unittest
from app.utils import dedupe_preserve_order

class TestDedupePreserveOrderPublic(unittest.TestCase):
    def test_adjacent_duplicate(self):
        self.assertEqual(dedupe_preserve_order([1, 1, 2]), [1, 2])
""",
            hidden_test_body="""
import unittest
from app.utils import dedupe_preserve_order

class TestDedupePreserveOrderHidden(unittest.TestCase):
    def test_non_adjacent_duplicates_and_order(self):
        self.assertEqual(dedupe_preserve_order([3, 1, 3, 2, 1]), [3, 1, 2])
        self.assertEqual(dedupe_preserve_order([]), [])
""",
            instruction="Fix dedupe_preserve_order so it removes duplicates while preserving first-seen order.",
            difficulty_label="micro_private",
            behavioral_axes=("collection_order", "edge_cases"),
        ),
    ]


def build_task_spec(
    task: PrivateHeldoutTaskDefinition,
    task_dir: Path,
    patch_hashes: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.private_heldout_seed_task.v1",
        "task_id": task.task_id,
        "split": "private_heldout",
        "never_train_on": True,
        "source_repo": {
            "type": "internal_generated_private_micro_repo",
            "license": "internal_scaffold_only",
            "provenance": "generated_by_step29_12_private_heldout_seed_set",
        },
        "repo_snapshot": {
            "path": str(task_dir / "repo_before"),
            "immutable_snapshot": True,
            "sha256": sha256_tree(task_dir / "repo_before"),
        },
        "task_family": task.task_family,
        "instruction": task.instruction,
        "pre_failure_command": "python3 -B -m unittest discover -s tests",
        "post_success_command": "python3 -B -m unittest discover -s tests",
        "hidden_tests": {
            "path": str(task_dir / "hidden_tests/test_hidden.py"),
            "sha256": sha256_text(read_text(task_dir / "hidden_tests/test_hidden.py")),
            "content_exported_to_training": False,
        },
        "expected_edit_scope": {
            "files": ["app/utils.py"],
            "max_files": 1,
        },
        "difficulty": {
            "label": task.difficulty_label,
            "single_file": True,
            "requires_hidden_generalization": True,
            "behavioral_axes": list(task.behavioral_axes),
        },
        "patch_refs": {
            "golden": {
                "path": str(task_dir / "golden.patch"),
                "sha256": patch_hashes["golden"],
                "export_to_training": False,
            },
            "rejected": {
                "path": str(task_dir / "rejected.patch"),
                "sha256": patch_hashes["rejected"],
                "export_to_training": False,
            },
            "public_overfit": {
                "path": str(task_dir / "public_overfit.patch"),
                "sha256": patch_hashes["public_overfit"],
                "export_to_training": False,
            },
        },
        "provenance": {
            "generator": "run_private_heldout_seed_set_v1.py",
            "generator_version": "v1",
            "deterministic": True,
            "patch_generation": "git_diff_from_temporary_repositories_with_committed_baselines",
        },
        "contamination_report": {
            "public_benchmark_overlap_checked": False,
            "reason": "internal generated scaffold; no external benchmark ingestion in this step",
            "allowed_for_private_seed_scaffold": True,
        },
    }


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_public_safe_manifest_row(task: PrivateHeldoutTaskDefinition, spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "forgeagent.private_heldout_manifest_row.v1",
        "task_id": task.task_id,
        "split": "private_heldout",
        "never_train_on": True,
        "task_family": task.task_family,
        "instruction_sha256": sha256_text(task.instruction),
        "repo_snapshot_sha256": spec["repo_snapshot"]["sha256"],
        "hidden_test_sha256": spec["hidden_tests"]["sha256"],
        "golden_patch_sha256": spec["patch_refs"]["golden"]["sha256"],
        "rejected_patch_sha256": spec["patch_refs"]["rejected"]["sha256"],
        "public_overfit_patch_sha256": spec["patch_refs"]["public_overfit"]["sha256"],
        "expected_edit_scope": spec["expected_edit_scope"],
        "behavioral_axes": list(task.behavioral_axes),
        "hidden_test_content_exported": False,
        "patch_content_exported": False,
        "training_export_allowed": False,
    }


def scan_text_for_secrets(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, pattern in SECRET_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({"pattern": name, "count": len(matches)})
    return findings


def read_existing_training_blob() -> str:
    chunks: list[str] = []
    for path in TRAINING_EXPORT_PATHS:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def scan_isolation(
    tasks: list[PrivateHeldoutTaskDefinition],
    task_dirs: dict[str, Path],
    public_safe_export_paths: list[Path],
) -> dict[str, Any]:
    training_blob = read_existing_training_blob()
    public_safe_blob = "\n".join(
        path.read_text(encoding="utf-8") for path in public_safe_export_paths if path.exists()
    )

    secret_findings: list[dict[str, Any]] = []
    hidden_leaks: list[dict[str, Any]] = []
    patch_leaks: list[dict[str, Any]] = []
    task_id_training_leaks: list[dict[str, Any]] = []
    public_safe_content_leaks: list[dict[str, Any]] = []

    for path in TRAINING_EXPORT_PATHS + public_safe_export_paths:
        if not path.exists():
            continue
        for finding in scan_text_for_secrets(path.read_text(encoding="utf-8")):
            secret_findings.append({"path": str(path), **finding})

    for task in tasks:
        task_dir = task_dirs[task.task_id]
        hidden_text = read_text(task_dir / "hidden_tests/test_hidden.py").strip()
        if hidden_text and hidden_text in training_blob:
            hidden_leaks.append({"task_id": task.task_id, "surface": "training_exports"})
        if hidden_text and hidden_text in public_safe_blob:
            public_safe_content_leaks.append({"task_id": task.task_id, "surface": "public_safe_exports"})

        for patch_name in ["golden.patch", "rejected.patch", "public_overfit.patch"]:
            patch_text = read_text(task_dir / patch_name).strip()
            if patch_text and patch_text in training_blob:
                patch_leaks.append(
                    {"task_id": task.task_id, "patch": patch_name, "surface": "training_exports"}
                )
            if patch_text and patch_text in public_safe_blob:
                public_safe_content_leaks.append(
                    {"task_id": task.task_id, "patch": patch_name, "surface": "public_safe_exports"}
                )

        if task.task_id in training_blob:
            task_id_training_leaks.append({"task_id": task.task_id})

    passed = (
        len(secret_findings) == 0
        and len(hidden_leaks) == 0
        and len(patch_leaks) == 0
        and len(task_id_training_leaks) == 0
        and len(public_safe_content_leaks) == 0
    )

    return {
        "schema_version": "forgeagent.private_heldout_isolation_report.v1",
        "training_export_paths": [str(path) for path in TRAINING_EXPORT_PATHS],
        "public_safe_export_paths": [str(path) for path in public_safe_export_paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "hidden_test_leak_count": len(hidden_leaks),
        "hidden_test_leaks": hidden_leaks,
        "private_patch_leak_count": len(patch_leaks),
        "private_patch_leaks": patch_leaks,
        "private_task_id_leak_count": len(task_id_training_leaks),
        "private_task_id_leaks": task_id_training_leaks,
        "public_safe_content_leak_count": len(public_safe_content_leaks),
        "public_safe_content_leaks": public_safe_content_leaks,
        "passed": passed,
    }


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    tasks = build_tasks()
    task_dirs: dict[str, Path] = {}
    result_rows: list[dict[str, Any]] = []
    manifest_path = OUT_DIR / "dataset_exports/private_heldout_seed_manifest.jsonl"

    for task in tasks:
        task_dir = OUT_DIR / "private_tasks" / task.task_id
        task_dirs[task.task_id] = task_dir
        create_repo(task_dir / "repo_before", task, task.before_body)
        write_text(task_dir / "hidden_tests/test_hidden.py", task.hidden_test_body.strip() + "\n")

        patch_texts = {
            "golden": make_patch(task, "golden", task.golden_body),
            "rejected": make_patch(task, "rejected", task.rejected_body),
            "public_overfit": make_patch(task, "public_overfit", task.public_overfit_body),
        }
        patch_hashes = {label: sha256_text(text) for label, text in patch_texts.items()}

        for label, patch_text in patch_texts.items():
            write_text(task_dir / f"{label}.patch", patch_text)

        spec = build_task_spec(task, task_dir, patch_hashes)
        write_json(task_dir / "task_spec.private.json", spec)
        append_jsonl(manifest_path, build_public_safe_manifest_row(task, spec))

        challenge_results = {
            label: verify_patch(task_dir, task, label, task_dir / f"{label}.patch")
            for label in ["golden", "rejected", "public_overfit"]
        }
        for result in challenge_results.values():
            append_jsonl(OUT_DIR / "private_heldout_oracle_results.jsonl", result)

        golden = challenge_results["golden"]
        rejected = challenge_results["rejected"]
        public_overfit = challenge_results["public_overfit"]
        row = {
            "schema_version": "forgeagent.private_heldout_seed_task_score.v1",
            "task_id": task.task_id,
            "split": "private_heldout",
            "never_train_on": True,
            "task_family": task.task_family,
            "behavioral_axes": list(task.behavioral_axes),
            "golden_patch_passed": golden["solved"],
            "rejected_patch_failed": rejected["patch_check_passed"]
            and rejected["patch_applied"]
            and not rejected["solved"],
            "public_overfit_caught_by_hidden": public_overfit["patch_check_passed"]
            and public_overfit["patch_applied"]
            and public_overfit["post_public_passed"]
            and not public_overfit["post_hidden_passed"],
            "pre_public_failed_as_expected": golden["pre_public_failed_as_expected"],
            "edit_scope_ok": golden["edit_scope_ok"],
            "verified": golden["solved"]
            and rejected["patch_check_passed"]
            and rejected["patch_applied"]
            and not rejected["solved"]
            and public_overfit["patch_check_passed"]
            and public_overfit["patch_applied"]
            and public_overfit["post_public_passed"]
            and not public_overfit["post_hidden_passed"],
        }
        append_jsonl(OUT_DIR / "private_heldout_seed_scores.jsonl", row)
        result_rows.append(row)

    isolation = scan_isolation(tasks, task_dirs, [manifest_path])
    write_json(OUT_DIR / "isolation_report.json", isolation)

    task_families = sorted({row["task_family"] for row in result_rows})
    behavioral_axes = sorted({axis for row in result_rows for axis in row["behavioral_axes"]})
    summary = {
        "schema_version": "forgeagent.private_heldout_seed_set_summary.v1",
        "seed_set_name": "private_heldout_seed_set_v1",
        "source_step": "step29_12_private_heldout_seed_set",
        "private_heldout_task_count": len(result_rows),
        "verified_private_heldout_task_count": sum(1 for row in result_rows if row["verified"]),
        "split_counts": {"private_heldout": len(result_rows)},
        "task_family_count": len(task_families),
        "task_families": task_families,
        "behavioral_axis_count": len(behavioral_axes),
        "behavioral_axes": behavioral_axes,
        "golden_patch_pass_count": sum(1 for row in result_rows if row["golden_patch_passed"]),
        "rejected_patch_fail_count": sum(1 for row in result_rows if row["rejected_patch_failed"]),
        "public_overfit_hidden_catch_count": sum(
            1 for row in result_rows if row["public_overfit_caught_by_hidden"]
        ),
        "pre_public_fail_count": sum(1 for row in result_rows if row["pre_public_failed_as_expected"]),
        "edit_scope_pass_count": sum(1 for row in result_rows if row["edit_scope_ok"]),
        "manifest_rows": count_jsonl(manifest_path),
        "training_export_rows": 0,
        "private_seed_exported_to_training": False,
        "hidden_test_content_exported_to_training": False,
        "patch_content_exported_to_training": False,
        "public_safe_manifest_contains_patch_content": False,
        "public_safe_manifest_contains_hidden_content": False,
        "isolation_scan_passed": isolation["passed"],
        "secret_finding_count": isolation["secret_finding_count"],
        "hidden_test_leak_count": isolation["hidden_test_leak_count"],
        "private_patch_leak_count": isolation["private_patch_leak_count"],
        "private_task_id_leak_count": isolation["private_task_id_leak_count"],
        "public_safe_content_leak_count": isolation["public_safe_content_leak_count"],
        "training_launch_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_13_heldout_aware_eval_protocol",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "private_heldout_seed_scores": str(OUT_DIR / "private_heldout_seed_scores.jsonl"),
            "private_heldout_oracle_results": str(OUT_DIR / "private_heldout_oracle_results.jsonl"),
            "isolation_report": str(OUT_DIR / "isolation_report.json"),
            "public_safe_manifest": str(manifest_path),
            "private_tasks": str(OUT_DIR / "private_tasks"),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("PRIVATE_HELDOUT_SEED_SET_V1_OK")


if __name__ == "__main__":
    main()

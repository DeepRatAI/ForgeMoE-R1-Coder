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
OUT_DIR = PROJECT_ROOT / "results/local/public_eval_suite_scaleout_v1"
RUN_DIR = PROJECT_ROOT / "tmp/public_eval_suite_scaleout_v1_runs"

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\\s*[:=]"),
}


@dataclass(frozen=True)
class PublicEvalTaskDefinition:
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
            check=False,
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


def create_repo(repo_dir: Path, task: PublicEvalTaskDefinition, body: str) -> None:
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    write_text(repo_dir / "app/__init__.py", f"from .utils import {task.function_name}\n")
    write_text(repo_dir / "app/utils.py", normalize_py(body))
    write_text(repo_dir / "tests/test_public.py", task.public_test_body.strip() + "\n")


def make_patch(task: PublicEvalTaskDefinition, label: str, after_body: str) -> str:
    patch_seed = hashlib.sha256(
        f"{task.task_id}\n{label}\n{normalize_py(task.before_body)}\n{normalize_py(after_body)}".encode(
            "utf-8"
        )
    ).hexdigest()[:16]
    patch_repo = RUN_DIR / "patch_build_repos" / patch_seed
    if patch_repo.exists():
        shutil.rmtree(patch_repo)
    write_text(patch_repo / "app/utils.py", normalize_py(task.before_body))
    init_git_repo(patch_repo, "Forge Public Eval Generator")
    write_text(patch_repo / "app/utils.py", normalize_py(after_body))
    diff = run_command(["git", "diff", "--", "app/utils.py"], cwd=patch_repo)
    ensure_passed(diff, f"git diff for {task.task_id}:{label}")
    patch_text = diff["stdout"]
    has_real_change = any(
        (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
        for line in patch_text.splitlines()
    )
    if not patch_text.strip() or not has_real_change:
        raise RuntimeError(f"empty or non-actionable patch for {task.task_id}:{label}")
    return patch_text if patch_text.endswith("\n") else patch_text + "\n"


def compact_command_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": result["command"],
        "exit_code": result["exit_code"],
        "passed": result["passed"],
        "timed_out": result["timed_out"],
        "stdout_sha256": sha256_text(result.get("stdout", "")),
        "stderr_sha256": sha256_text(result.get("stderr", "")),
    }


def changed_files_from_patch(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        parts = line.split()
        if len(parts) >= 4 and parts[3].startswith("b/"):
            files.append(parts[3][2:])
    return files


def verify_patch(task_dir: Path, task: PublicEvalTaskDefinition, label: str, patch_path: Path) -> dict[str, Any]:
    work_dir = RUN_DIR / "verification" / task.task_id / label
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(task_dir / "repo_before", work_dir)
    init_git_repo(work_dir, "Forge Public Eval Verifier")

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
        changed_files = run_command(["git", "diff", "--name-only"], cwd=work_dir)
        post_public = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
        shutil.copy2(task_dir / "hidden_tests/test_hidden.py", work_dir / "tests/test_hidden.py")
        post_hidden = run_command(["python3", "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=work_dir)
    else:
        changed_files = {
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

    changed_file_list = [line for line in changed_files.get("stdout", "").splitlines() if line.strip()]
    patch_file_list = changed_files_from_patch(patch_text)
    edit_scope_passed = changed_file_list == ["app/utils.py"] and patch_file_list == ["app/utils.py"]
    solved = patch_apply["passed"] and post_public["passed"] and post_hidden["passed"] and edit_scope_passed
    return {
        "task_id": task.task_id,
        "challenge": label,
        "pre_public_failed_as_expected": not pre_public["passed"],
        "patch_check_passed": patch_check["passed"],
        "patch_applied": patch_apply["passed"],
        "changed_files": changed_file_list,
        "patch_files": patch_file_list,
        "edit_scope_passed": edit_scope_passed,
        "post_public_passed": post_public["passed"],
        "post_hidden_passed": post_hidden["passed"],
        "solved": solved,
        "pre_public": compact_command_result(pre_public),
        "patch_check": compact_command_result(patch_check),
        "post_public": compact_command_result(post_public),
        "post_hidden": compact_command_result(post_hidden),
    }


def build_tasks() -> list[PublicEvalTaskDefinition]:
    return [
        PublicEvalTaskDefinition(
            task_id="public-eval-clamp-high-generalization",
            task_family="boundary_condition_bugfix",
            function_name="clamp",
            before_body="""def clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return low
    return value
""",
            golden_body="""def clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value
""",
            rejected_body="""def clamp(value: int, low: int, high: int) -> int:
    return value
""",
            public_overfit_body="""def clamp(value: int, low: int, high: int) -> int:
    if value == 13 and low == 0 and high == 10:
        return 10
    if value < low:
        return low
    if value > high:
        return low
    return value
""",
            public_test_body="""
import unittest
from app.utils import clamp

class TestClampPublic(unittest.TestCase):
    def test_high_boundary_public(self):
        self.assertEqual(clamp(13, 0, 10), 10)
""",
            hidden_test_body="""
import unittest
from app.utils import clamp

class TestClampHidden(unittest.TestCase):
    def test_general_high_boundary(self):
        self.assertEqual(clamp(99, 10, 20), 20)

    def test_low_boundary_still_works(self):
        self.assertEqual(clamp(-4, 0, 10), 0)
""",
            instruction="Fix clamp so values above high return high for all numeric boundaries.",
            difficulty_label="easy",
            behavioral_axes=("boundary_values", "generalization", "public_overfit_resistance"),
        ),
        PublicEvalTaskDefinition(
            task_id="public-eval-normalize-inner-whitespace",
            task_family="string_normalization_bugfix",
            function_name="normalize_spaces",
            before_body="""def normalize_spaces(text: str) -> str:
    return text.strip()
""",
            golden_body="""def normalize_spaces(text: str) -> str:
    return " ".join(text.split())
""",
            rejected_body="""def normalize_spaces(text: str) -> str:
    return text.replace("  ", " ").strip()
""",
            public_overfit_body="""def normalize_spaces(text: str) -> str:
    if text == " hello   world ":
        return "hello world"
    return text.strip()
""",
            public_test_body="""
import unittest
from app.utils import normalize_spaces

class TestNormalizeSpacesPublic(unittest.TestCase):
    def test_public_phrase(self):
        self.assertEqual(normalize_spaces(" hello   world "), "hello world")
""",
            hidden_test_body="""
import unittest
from app.utils import normalize_spaces

class TestNormalizeSpacesHidden(unittest.TestCase):
    def test_tabs_and_newlines(self):
        self.assertEqual(normalize_spaces("\\talpha\\n beta   gamma"), "alpha beta gamma")
""",
            instruction="Normalize all whitespace runs to a single space after trimming.",
            difficulty_label="easy",
            behavioral_axes=("string_whitespace", "input_generalization", "public_overfit_resistance"),
        ),
        PublicEvalTaskDefinition(
            task_id="public-eval-safe-index-default",
            task_family="collection_semantics_bugfix",
            function_name="safe_get",
            before_body="""def safe_get(items: list[str], index: int, default: str) -> str:
    return items[index]
""",
            golden_body="""def safe_get(items: list[str], index: int, default: str) -> str:
    if index < 0 or index >= len(items):
        return default
    return items[index]
""",
            rejected_body="""def safe_get(items: list[str], index: int, default: str) -> str:
    if index >= len(items):
        return default
    return items[index]
""",
            public_overfit_body="""def safe_get(items: list[str], index: int, default: str) -> str:
    if index == 3:
        return default
    return items[index]
""",
            public_test_body="""
import unittest
from app.utils import safe_get

class TestSafeGetPublic(unittest.TestCase):
    def test_out_of_range_high(self):
        self.assertEqual(safe_get(["a", "b", "c"], 3, "missing"), "missing")
""",
            hidden_test_body="""
import unittest
from app.utils import safe_get

class TestSafeGetHidden(unittest.TestCase):
    def test_negative_index_is_default(self):
        self.assertEqual(safe_get(["a", "b", "c"], -1, "missing"), "missing")

    def test_valid_index_still_returns_item(self):
        self.assertEqual(safe_get(["a", "b", "c"], 1, "missing"), "b")
""",
            instruction="Return default for out-of-range indexes, including negative indexes.",
            difficulty_label="medium",
            behavioral_axes=("collection_bounds", "negative_index", "public_overfit_resistance"),
        ),
        PublicEvalTaskDefinition(
            task_id="public-eval-unique-preserve-order",
            task_family="collection_order_bugfix",
            function_name="unique_preserve_order",
            before_body="""def unique_preserve_order(items: list[str]) -> list[str]:
    return sorted(set(items))
""",
            golden_body="""def unique_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
""",
            rejected_body="""def unique_preserve_order(items: list[str]) -> list[str]:
    result = []
    for item in sorted(set(items)):
        result.append(item)
    return result
""",
            public_overfit_body="""def unique_preserve_order(items: list[str]) -> list[str]:
    if items == ["b", "a", "b"]:
        return ["b", "a"]
    return sorted(set(items))
""",
            public_test_body="""
import unittest
from app.utils import unique_preserve_order

class TestUniquePublic(unittest.TestCase):
    def test_public_order(self):
        self.assertEqual(unique_preserve_order(["b", "a", "b"]), ["b", "a"])
""",
            hidden_test_body="""
import unittest
from app.utils import unique_preserve_order

class TestUniqueHidden(unittest.TestCase):
    def test_general_order(self):
        self.assertEqual(unique_preserve_order(["c", "b", "c", "a", "b"]), ["c", "b", "a"])
""",
            instruction="Deduplicate while preserving first occurrence order.",
            difficulty_label="medium",
            behavioral_axes=("collection_order", "deduplication", "public_overfit_resistance"),
        ),
        PublicEvalTaskDefinition(
            task_id="public-eval-parse-bool-aliases",
            task_family="parsing_bugfix",
            function_name="parse_bool",
            before_body="""def parse_bool(text: str) -> bool:
    return text == "true"
""",
            golden_body="""def parse_bool(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {"true", "1", "yes", "on"}
""",
            rejected_body="""def parse_bool(text: str) -> bool:
    return bool(text)
""",
            public_overfit_body="""def parse_bool(text: str) -> bool:
    if text == " yes ":
        return True
    return text == "true"
""",
            public_test_body="""
import unittest
from app.utils import parse_bool

class TestParseBoolPublic(unittest.TestCase):
    def test_yes_with_spaces(self):
        self.assertTrue(parse_bool(" yes "))
""",
            hidden_test_body="""
import unittest
from app.utils import parse_bool

class TestParseBoolHidden(unittest.TestCase):
    def test_truthy_aliases(self):
        self.assertTrue(parse_bool("ON"))
        self.assertTrue(parse_bool("1"))

    def test_false_string_is_false(self):
        self.assertFalse(parse_bool("false"))
""",
            instruction="Parse common truthy boolean aliases case-insensitively.",
            difficulty_label="medium",
            behavioral_axes=("string_normalization", "parsing", "false_positive_resistance"),
        ),
        PublicEvalTaskDefinition(
            task_id="public-eval-chunked-step-size",
            task_family="iteration_bugfix",
            function_name="chunked",
            before_body="""def chunked(items: list[int], size: int) -> list[list[int]]:
    return [items[index:index + size] for index in range(0, len(items), size + 1)]
""",
            golden_body="""def chunked(items: list[int], size: int) -> list[list[int]]:
    return [items[index:index + size] for index in range(0, len(items), size)]
""",
            rejected_body="""def chunked(items: list[int], size: int) -> list[list[int]]:
    return [items]
""",
            public_overfit_body="""def chunked(items: list[int], size: int) -> list[list[int]]:
    if items == [1, 2, 3, 4] and size == 2:
        return [[1, 2], [3, 4]]
    return [items[index:index + size] for index in range(0, len(items), size + 1)]
""",
            public_test_body="""
import unittest
from app.utils import chunked

class TestChunkedPublic(unittest.TestCase):
    def test_public_even_chunks(self):
        self.assertEqual(chunked([1, 2, 3, 4], 2), [[1, 2], [3, 4]])
""",
            hidden_test_body="""
import unittest
from app.utils import chunked

class TestChunkedHidden(unittest.TestCase):
    def test_uneven_chunks(self):
        self.assertEqual(chunked([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_size_three(self):
        self.assertEqual(chunked([1, 2, 3, 4, 5, 6], 3), [[1, 2, 3], [4, 5, 6]])
""",
            instruction="Chunk a list using the requested chunk size as the step.",
            difficulty_label="medium",
            behavioral_axes=("iteration_step", "sequence_partitioning", "public_overfit_resistance"),
        ),
    ]


def build_task_artifacts(task: PublicEvalTaskDefinition) -> dict[str, Any]:
    task_dir = OUT_DIR / "public_eval_tasks" / task.task_id
    if task_dir.exists():
        shutil.rmtree(task_dir)
    create_repo(task_dir / "repo_before", task, task.before_body)
    write_text(task_dir / "hidden_tests/test_hidden.py", task.hidden_test_body.strip() + "\n")
    write_json(
        task_dir / "task.json",
        {
            "schema_version": "forgeagent.task.v0",
            "task_id": task.task_id,
            "task_type": "unit_bugfix",
            "title": task.instruction,
            "description": task.instruction,
            "repo_dir": "repo_before",
            "test_command": "python3 -B -m unittest discover -s tests",
            "timeout_seconds": 30,
            "task_family": task.task_family,
            "difficulty_label": task.difficulty_label,
            "behavioral_axes": list(task.behavioral_axes),
        },
    )

    patch_dir = task_dir / "patches"
    patches = {
        "golden": make_patch(task, "golden", task.golden_body),
        "rejected": make_patch(task, "rejected", task.rejected_body),
        "public_overfit": make_patch(task, "public_overfit", task.public_overfit_body),
    }
    patch_paths: dict[str, Path] = {}
    for label, patch_text in patches.items():
        path = patch_dir / f"{label}.patch"
        write_text(path, patch_text)
        patch_paths[label] = path

    oracle_rows = [
        verify_patch(task_dir, task, label, path)
        for label, path in patch_paths.items()
    ]
    by_label = {row["challenge"]: row for row in oracle_rows}
    score = {
        "schema_version": "forgeagent.public_eval_task_score.v1",
        "task_id": task.task_id,
        "split": "public_eval",
        "task_family": task.task_family,
        "difficulty_label": task.difficulty_label,
        "behavioral_axes": list(task.behavioral_axes),
        "verified": (
            by_label["golden"]["solved"]
            and not by_label["rejected"]["solved"]
            and by_label["public_overfit"]["post_public_passed"]
            and not by_label["public_overfit"]["post_hidden_passed"]
            and by_label["golden"]["pre_public_failed_as_expected"]
        ),
        "pre_public_failed": by_label["golden"]["pre_public_failed_as_expected"],
        "golden_patch_passed": by_label["golden"]["solved"],
        "rejected_patch_failed": not by_label["rejected"]["solved"],
        "public_overfit_caught_by_hidden": by_label["public_overfit"]["post_public_passed"]
        and not by_label["public_overfit"]["post_hidden_passed"],
        "edit_scope_passed": all(row["edit_scope_passed"] for row in oracle_rows),
        "public_test_sha256": sha256_text(task.public_test_body.strip() + "\n"),
        "hidden_test_sha256": sha256_text(task.hidden_test_body.strip() + "\n"),
        "golden_patch_sha256": sha256_text(patches["golden"]),
        "rejected_patch_sha256": sha256_text(patches["rejected"]),
        "public_overfit_patch_sha256": sha256_text(patches["public_overfit"]),
    }
    return {"score": score, "oracle_rows": oracle_rows, "task_dir": task_dir}


def scan_public_safe_outputs(paths: list[Path]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    hidden_content_leaks: list[dict[str, Any]] = []
    patch_content_leaks: list[dict[str, Any]] = []
    forbidden_markers = ["assertEqual", "diff --git", "def "]
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern_name, pattern in SECRET_PATTERNS.items():
            matches = list(pattern.finditer(text))
            if matches:
                secret_findings.append({"path": str(path), "pattern": pattern_name, "count": len(matches)})
        for marker in forbidden_markers:
            if marker in text:
                if marker == "diff --git":
                    patch_content_leaks.append({"path": str(path), "marker": marker})
                else:
                    hidden_content_leaks.append({"path": str(path), "marker": marker})
    return {
        "schema_version": "forgeagent.public_eval_suite_privacy_report.v1",
        "scanned_public_safe_paths": [str(path) for path in paths],
        "secret_finding_count": len(secret_findings),
        "secret_findings": secret_findings,
        "hidden_or_test_content_leak_count": len(hidden_content_leaks),
        "hidden_or_test_content_leaks": hidden_content_leaks,
        "patch_content_leak_count": len(patch_content_leaks),
        "patch_content_leaks": patch_content_leaks,
        "passed": len(secret_findings) == 0
        and len(hidden_content_leaks) == 0
        and len(patch_content_leaks) == 0,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tasks = build_tasks()
    scores: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []
    for task in tasks:
        artifacts = build_task_artifacts(task)
        scores.append(artifacts["score"])
        oracle_rows.extend(artifacts["oracle_rows"])

    score_path = OUT_DIR / "public_eval_task_scores.jsonl"
    oracle_path = OUT_DIR / "public_eval_oracle_results.jsonl"
    manifest_path = OUT_DIR / "dataset_exports/public_eval_suite_manifest.jsonl"
    for score in scores:
        append_jsonl(score_path, score)
        append_jsonl(
            manifest_path,
            {
                "schema_version": "forgeagent.public_eval_suite_manifest_row.v1",
                "task_id": score["task_id"],
                "split": "public_eval",
                "task_family": score["task_family"],
                "difficulty_label": score["difficulty_label"],
                "behavioral_axes": score["behavioral_axes"],
                "verified": score["verified"],
                "public_test_sha256": score["public_test_sha256"],
                "hidden_test_sha256": score["hidden_test_sha256"],
                "golden_patch_sha256": score["golden_patch_sha256"],
                "rejected_patch_sha256": score["rejected_patch_sha256"],
                "public_overfit_patch_sha256": score["public_overfit_patch_sha256"],
                "hidden_test_content_exported": False,
                "patch_content_exported": False,
                "training_export_allowed": False,
            },
        )
    for row in oracle_rows:
        append_jsonl(oracle_path, row)

    task_families = sorted({score["task_family"] for score in scores})
    behavioral_axes = sorted({axis for score in scores for axis in score["behavioral_axes"]})
    public_report = {
        "schema_version": "forgeagent.public_safe_public_eval_suite_report.v1",
        "report_name": "public_eval_suite_scaleout_v1_public_safe",
        "public_eval_task_count": len(scores),
        "verified_public_eval_task_count": sum(1 for score in scores if score["verified"]),
        "task_family_count": len(task_families),
        "task_families": task_families,
        "behavioral_axis_count": len(behavioral_axes),
        "behavioral_axes": behavioral_axes,
        "golden_patch_pass_count": sum(1 for score in scores if score["golden_patch_passed"]),
        "rejected_patch_fail_count": sum(1 for score in scores if score["rejected_patch_failed"]),
        "public_overfit_hidden_catch_count": sum(
            1 for score in scores if score["public_overfit_caught_by_hidden"]
        ),
        "pre_public_fail_count": sum(1 for score in scores if score["pre_public_failed"]),
        "edit_scope_pass_count": sum(1 for score in scores if score["edit_scope_passed"]),
        "redaction_policy": {
            "test_content_included": False,
            "hidden_test_content_included": False,
            "patch_content_included": False,
            "candidate_raw_outputs_included": False,
        },
    }
    public_report_path = OUT_DIR / "public_safe_public_eval_suite_report.json"
    write_json(public_report_path, public_report)

    privacy = scan_public_safe_outputs([manifest_path, public_report_path])
    privacy_path = OUT_DIR / "public_eval_suite_privacy_report.json"
    write_json(privacy_path, privacy)

    summary = {
        "schema_version": "forgeagent.public_eval_suite_scaleout_summary.v1",
        "suite_name": "public_eval_suite_scaleout_v1",
        "source_step": "step29_20_public_eval_suite_scaleout",
        "public_eval_task_count": len(scores),
        "verified_public_eval_task_count": sum(1 for score in scores if score["verified"]),
        "split_counts": {"public_eval": len(scores)},
        "task_family_count": len(task_families),
        "task_families": task_families,
        "behavioral_axis_count": len(behavioral_axes),
        "behavioral_axes": behavioral_axes,
        "golden_patch_pass_count": sum(1 for score in scores if score["golden_patch_passed"]),
        "rejected_patch_fail_count": sum(1 for score in scores if score["rejected_patch_failed"]),
        "public_overfit_hidden_catch_count": sum(
            1 for score in scores if score["public_overfit_caught_by_hidden"]
        ),
        "pre_public_fail_count": sum(1 for score in scores if score["pre_public_failed"]),
        "edit_scope_pass_count": sum(1 for score in scores if score["edit_scope_passed"]),
        "manifest_rows": len(scores),
        "public_safe_report_ready": True,
        "secret_finding_count": privacy["secret_finding_count"],
        "hidden_or_test_content_leak_count": privacy["hidden_or_test_content_leak_count"],
        "patch_content_leak_count": privacy["patch_content_leak_count"],
        "privacy_scan_passed": privacy["passed"],
        "candidate_eval_executed": False,
        "remote_inference_invoked": False,
        "local_model_execution_used": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_21_public_eval_candidate_runner_scaleout",
        "artifacts": {
            "summary": str(OUT_DIR / "summary.json"),
            "public_eval_task_scores": str(score_path),
            "public_eval_oracle_results": str(oracle_path),
            "public_eval_suite_manifest": str(manifest_path),
            "public_safe_report": str(public_report_path),
            "privacy_report": str(privacy_path),
            "public_eval_tasks": str(OUT_DIR / "public_eval_tasks"),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("PUBLIC_EVAL_SUITE_SCALEOUT_V1_OK")


if __name__ == "__main__":
    main()

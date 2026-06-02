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
STEP29_30_DIR = PROJECT_ROOT / "results/local/hardened_task_generation_public_benchmark_registry_v1"
OUT_DIR = PROJECT_ROOT / "results/local/hardened_executable_task_generator_v1"
RUN_DIR = PROJECT_ROOT / "tmp/hardened_executable_task_generator_v1_runs"

EXPECTED_SPLIT_COUNTS = {
    "train": 4,
    "eval": 3,
    "private_heldout": 3,
    "public_eval": 2,
}

SECRET_PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_secret_assignment": re.compile(r"(?i)aws_secret_access_key\s*[:=]"),
}

PUBLIC_REPORT_DISALLOWED_MARKERS = [
    "forge-hard-private-",
    "diff --git",
    "assertEqual",
    "hidden_tests",
    "raw_model_output",
    "raw_outputs",
    "golden_patch",
    "public_overfit.patch",
    "rejected.patch",
]


@dataclass(frozen=True)
class AssertionCase:
    value: str
    expected: str
    context: str = "{}"


@dataclass(frozen=True)
class HardenedTaskDefinition:
    task_id: str
    split: str
    task_family: str
    behavioral_axes: tuple[str, ...]
    difficulty_label: str
    instruction: str
    public_case: AssertionCase
    hidden_cases: tuple[AssertionCase, ...]
    before_policy_body: str
    golden_policy_body: str
    rejected_policy_body: str
    public_overfit_policy_body: str


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


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


def compact_command_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": result["command"],
        "exit_code": result["exit_code"],
        "passed": result["passed"],
        "timed_out": result["timed_out"],
        "stdout_sha256": sha256_text(result.get("stdout", "")),
        "stderr_sha256": sha256_text(result.get("stderr", "")),
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
    ensure_passed(run_command(["git", "config", "user.email", "forge@example.invalid"], cwd=work_dir), "git config email")
    ensure_passed(run_command(["git", "config", "user.name", actor], cwd=work_dir), "git config name")
    ensure_passed(run_command(["git", "add", "."], cwd=work_dir), "git add baseline")
    ensure_passed(run_command(["git", "commit", "-q", "-m", "baseline"], cwd=work_dir), "git commit baseline")


def service_text(pass_context: bool) -> str:
    if pass_context:
        return """from .policy import normalize


def solve(value, context=None):
    return normalize(value, context or {})
"""
    return """from .policy import normalize


def solve(value, context=None):
    return normalize(value)
"""


def policy_text(body: str, takes_context: bool) -> str:
    signature = "def normalize(value, context):" if takes_context else "def normalize(value):"
    return signature + "\n" + body.rstrip() + "\n"


def init_text() -> str:
    return """from .service import solve

__all__ = ["solve"]
"""


def public_test_text(task: HardenedTaskDefinition) -> str:
    return f"""import unittest
from app.service import solve


class TestPublicBehavior(unittest.TestCase):
    def test_public_contract(self):
        self.assertEqual(solve({task.public_case.value}, {task.public_case.context}), {task.public_case.expected})


if __name__ == "__main__":
    unittest.main()
"""


def hidden_test_text(task: HardenedTaskDefinition) -> str:
    lines = [
        "import unittest",
        "from app.service import solve",
        "",
        "",
        "class TestHiddenBehavior(unittest.TestCase):",
    ]
    for index, case in enumerate(task.hidden_cases, start=1):
        lines.extend(
            [
                f"    def test_hidden_case_{index}(self):",
                f"        self.assertEqual(solve({case.value}, {case.context}), {case.expected})",
                "",
            ]
        )
    lines.extend(["", 'if __name__ == "__main__":', "    unittest.main()", ""])
    return "\n".join(lines)


def base_files(task: HardenedTaskDefinition) -> dict[str, str]:
    return {
        "README.md": f"# {task.task_family}\n\nInternal hardened executable task scaffold.\n",
        "app/__init__.py": init_text(),
        "app/service.py": service_text(pass_context=False),
        "app/policy.py": policy_text(task.before_policy_body, takes_context=False),
        "tests/test_public.py": public_test_text(task),
    }


def golden_files(task: HardenedTaskDefinition) -> dict[str, str]:
    return {
        "app/service.py": service_text(pass_context=True),
        "app/policy.py": policy_text(task.golden_policy_body, takes_context=True),
    }


def rejected_files(task: HardenedTaskDefinition) -> dict[str, str]:
    return {
        "app/service.py": service_text(pass_context=True),
        "app/policy.py": policy_text(task.rejected_policy_body, takes_context=True),
    }


def public_overfit_files(task: HardenedTaskDefinition) -> dict[str, str]:
    return {
        "app/service.py": service_text(pass_context=True),
        "app/policy.py": policy_text(task.public_overfit_policy_body, takes_context=True),
    }


def wrong_file_files(task: HardenedTaskDefinition) -> dict[str, str]:
    return {
        "README.md": f"# {task.task_family}\n\nEdited the documentation instead of the behavior.\n",
    }


def semantic_noop_files(_: HardenedTaskDefinition) -> dict[str, str]:
    return {
        "app/service.py": """from .policy import normalize


def solve(value, context=None):
    # Deliberately preserves the current behavior.
    return normalize(value)
""",
    }


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative_path, text in files.items():
        write_text(root / relative_path, text.rstrip() + "\n")


def create_repo(repo_dir: Path, task: HardenedTaskDefinition) -> None:
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    write_files(repo_dir, base_files(task))


def make_patch(task: HardenedTaskDefinition, label: str, changed_files: dict[str, str]) -> str:
    seed = sha256_text(f"{task.task_id}:{label}")[:16]
    patch_repo = RUN_DIR / "patch_build_repos" / seed
    if patch_repo.exists():
        shutil.rmtree(patch_repo)
    write_files(patch_repo, base_files(task))
    init_git_repo(patch_repo, "Forge Hardened Task Generator")
    write_files(patch_repo, changed_files)
    diff = run_command(["git", "diff"], cwd=patch_repo)
    ensure_passed(diff, f"git diff for {task.task_id}:{label}")
    patch = diff["stdout"]
    has_real_change = any(
        (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
        for line in patch.splitlines()
    )
    if not patch.strip() or not has_real_change:
        raise RuntimeError(f"empty or non-actionable patch for {task.task_id}:{label}")
    return patch if patch.endswith("\n") else patch + "\n"


def changed_files_from_patch(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        parts = line.split()
        if len(parts) >= 4 and parts[3].startswith("b/"):
            files.append(parts[3][2:])
    return files


def verify_patch(
    task_dir: Path,
    task: HardenedTaskDefinition,
    label: str,
    patch_path: Path,
    expected_files: list[str],
) -> dict[str, Any]:
    work_dir = RUN_DIR / "verification" / task.task_id / label
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(task_dir / "repo_before", work_dir)
    init_git_repo(work_dir, "Forge Hardened Task Verifier")

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
        post_hidden = dict(post_public)

    changed_files = [line.strip() for line in changed_files_result.get("stdout", "").splitlines() if line.strip()]
    patch_files = changed_files_from_patch(patch_text)
    edit_scope_passed = sorted(changed_files) == sorted(expected_files) and sorted(patch_files) == sorted(expected_files)
    solved = (
        (not pre_public["passed"])
        and patch_check["passed"]
        and patch_apply["passed"]
        and post_public["passed"]
        and post_hidden["passed"]
        and edit_scope_passed
    )
    return {
        "schema_version": "forgeagent.hardened_executable_patch_verification.v1",
        "task_id": task.task_id,
        "task_id_sha256": sha256_text(task.task_id),
        "split": task.split,
        "challenge": label,
        "patch_sha256": sha256_text(patch_text),
        "patch_bytes": len(patch_text.encode("utf-8")),
        "patch_file_count": len(patch_files),
        "changed_file_count": len(changed_files),
        "patch_files": patch_files,
        "changed_files": changed_files,
        "expected_files": expected_files,
        "pre_public_failed_as_expected": not pre_public["passed"],
        "patch_check_passed": patch_check["passed"],
        "patch_applied": patch_apply["passed"],
        "edit_scope_passed": edit_scope_passed,
        "post_public_passed": post_public["passed"],
        "post_hidden_passed": post_hidden["passed"],
        "solved": solved,
        "pre_public": compact_command_result(pre_public),
        "patch_check": compact_command_result(patch_check),
        "patch_apply": compact_command_result(patch_apply),
        "post_public": compact_command_result(post_public),
        "post_hidden": compact_command_result(post_hidden),
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }


def task_definitions() -> list[HardenedTaskDefinition]:
    return [
        HardenedTaskDefinition(
            task_id="forge-hard-train-config-env-precedence",
            split="train",
            task_family="configuration_precedence_bugfix",
            behavioral_axes=("multi_file", "environment_precedence", "fallback_defaults", "schema_validation"),
            difficulty_label="medium",
            instruction="Resolve defaults, environment overrides and CLI overrides in the correct precedence order.",
            public_case=AssertionCase(
                value='{"defaults": {"timeout": 5}, "env": {}, "cli": {"timeout": 15}}',
                expected='{"timeout": 15}',
            ),
            hidden_cases=(
                AssertionCase(
                    value='{"defaults": {"timeout": 5}, "env": {"timeout": "20"}, "cli": {}}',
                    expected='{"timeout": 20}',
                ),
                AssertionCase(
                    value='{"defaults": {"timeout": 5}, "env": {"timeout": "-1"}, "cli": {}}',
                    expected='{"error": "invalid_timeout"}',
                ),
            ),
            before_policy_body="    return dict(value.get(\"defaults\", {}))",
            golden_policy_body="""    resolved = dict(value.get("defaults", {}))
    if "timeout" in value.get("env", {}):
        resolved["timeout"] = int(value["env"]["timeout"])
    if "timeout" in value.get("cli", {}):
        resolved["timeout"] = int(value["cli"]["timeout"])
    if resolved.get("timeout", 0) <= 0:
        return {"error": "invalid_timeout"}
    return resolved""",
            rejected_policy_body="""    resolved = dict(value.get("defaults", {}))
    if "timeout" in value.get("cli", {}):
        resolved["timeout"] = int(value["cli"]["timeout"])
    return resolved""",
            public_overfit_policy_body="""    if value == {"defaults": {"timeout": 5}, "env": {}, "cli": {"timeout": 15}}:
        return {"timeout": 15}
    return dict(value.get("defaults", {}))""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-train-pagination-idempotency",
            split="train",
            task_family="api_pagination_idempotency_fix",
            behavioral_axes=("multi_file", "pagination", "idempotent_retry", "stateful_boundary"),
            difficulty_label="medium",
            instruction="Collect paginated items while preserving order and ignoring duplicate retry pages.",
            public_case=AssertionCase(
                value='[{"cursor": "a", "items": [1]}, {"cursor": None, "items": [2]}]',
                expected="[1, 2]",
            ),
            hidden_cases=(
                AssertionCase(
                    value='[{"cursor": "a", "items": [1]}, {"cursor": "a", "items": [1]}, {"cursor": None, "items": [2, 1]}]',
                    expected="[1, 2]",
                ),
            ),
            before_policy_body="    return list(value[0].get(\"items\", []))",
            golden_policy_body="""    seen_items = set()
    result = []
    seen_cursors = set()
    for page in value:
        cursor = page.get("cursor")
        page_key = (cursor, tuple(page.get("items", [])))
        if page_key in seen_cursors:
            continue
        seen_cursors.add(page_key)
        for item in page.get("items", []):
            if item in seen_items:
                continue
            seen_items.add(item)
            result.append(item)
    return result""",
            rejected_policy_body="""    result = []
    for page in value:
        result.extend(page.get("items", []))
    return result""",
            public_overfit_policy_body="""    if value == [{"cursor": "a", "items": [1]}, {"cursor": None, "items": [2]}]:
        return [1, 2]
    return list(value[0].get("items", []))""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-train-path-normalization-security",
            split="train",
            task_family="path_normalization_security_fix",
            behavioral_axes=("multi_file", "path_traversal_guard", "platform_paths", "input_validation"),
            difficulty_label="hard",
            instruction="Normalize paths under the configured root and reject traversal outside that root.",
            public_case=AssertionCase(
                value='{"root": "/srv/app", "path": "reports/../data/file.txt"}',
                expected='"/srv/app/data/file.txt"',
            ),
            hidden_cases=(
                AssertionCase(value='{"root": "/srv/app", "path": "../secret.txt"}', expected='"DENY"'),
                AssertionCase(value='{"root": "/srv/app", "path": "data//x.txt"}', expected='"/srv/app/data/x.txt"'),
            ),
            before_policy_body="    return value[\"root\"] + \"/\" + value[\"path\"]",
            golden_policy_body="""    import posixpath
    root = posixpath.normpath(value["root"])
    candidate = posixpath.normpath(posixpath.join(root, value["path"]))
    if candidate != root and not candidate.startswith(root + "/"):
        return "DENY"
    return candidate""",
            rejected_policy_body="""    import posixpath
    return posixpath.normpath(posixpath.join(value["root"], value["path"]))""",
            public_overfit_policy_body="""    if value == {"root": "/srv/app", "path": "reports/../data/file.txt"}:
        return "/srv/app/data/file.txt"
    return value["root"] + "/" + value["path"]""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-train-transactional-upsert",
            split="train",
            task_family="transactional_state_update_fix",
            behavioral_axes=("multi_file", "transaction_boundary", "rollback_semantics", "concurrent_retry"),
            difficulty_label="hard",
            instruction="Apply upserts atomically and return the original state when an update is invalid.",
            public_case=AssertionCase(
                value='{"existing": {"a": 1}, "updates": [["b", 2], ["b", 3]]}',
                expected='{"data": {"a": 1, "b": 3}, "ok": True}',
            ),
            hidden_cases=(
                AssertionCase(
                    value='{"existing": {"a": 1}, "updates": [["b", 2], [None, 3]]}',
                    expected='{"data": {"a": 1}, "ok": False}',
                ),
            ),
            before_policy_body="""    data = dict(value.get("existing", {}))
    for key, item in value.get("updates", [])[:1]:
        data[key] = item
    return {"data": data, "ok": True}""",
            golden_policy_body="""    data = dict(value.get("existing", {}))
    pending = {}
    for key, item in value.get("updates", []):
        if not isinstance(key, str):
            return {"data": dict(value.get("existing", {})), "ok": False}
        pending[key] = item
    data.update(pending)
    return {"data": data, "ok": True}""",
            rejected_policy_body="""    data = dict(value.get("existing", {}))
    for key, item in value.get("updates", []):
        data[key] = item
    return {"data": data, "ok": True}""",
            public_overfit_policy_body="""    if value == {"existing": {"a": 1}, "updates": [["b", 2], ["b", 3]]}:
        return {"data": {"a": 1, "b": 3}, "ok": True}
    return {"data": dict(value.get("existing", {})), "ok": True}""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-eval-json-schema-evolution",
            split="eval",
            task_family="api_schema_migration_bugfix",
            behavioral_axes=("multi_file", "backward_compatibility", "json_schema", "typed_error_shape"),
            difficulty_label="hard",
            instruction="Accept old and new API payloads while keeping strict typed errors.",
            public_case=AssertionCase(value='{"name": "Ada"}', expected='{"active": True, "name": "Ada"}'),
            hidden_cases=(
                AssertionCase(value='{"name": "Ada", "enabled": False}', expected='{"active": False, "name": "Ada"}'),
                AssertionCase(value='{"enabled": True}', expected='{"error": "missing_name"}'),
            ),
            before_policy_body="    return {\"name\": value[\"name\"]}",
            golden_policy_body="""    if "name" not in value:
        return {"error": "missing_name"}
    active = value.get("active", value.get("enabled", True))
    return {"active": bool(active), "name": value["name"]}""",
            rejected_policy_body="""    if "name" not in value:
        return {"error": "missing_name"}
    return {"active": True, "name": value["name"]}""",
            public_overfit_policy_body="""    if value == {"name": "Ada"}:
        return {"active": True, "name": "Ada"}
    return {"name": value.get("name")}""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-eval-time-window-boundary",
            split="eval",
            task_family="time_window_boundary_bugfix",
            behavioral_axes=("multi_file", "timezone_boundary", "inclusive_exclusive_edges", "deterministic_clock"),
            difficulty_label="hard",
            instruction="Treat start and end boundaries inclusively using an injected deterministic timestamp.",
            public_case=AssertionCase(value='{"end": 10, "now": 10, "start": 5}', expected="True"),
            hidden_cases=(
                AssertionCase(value='{"end": 10, "now": 5, "start": 5}', expected="True"),
                AssertionCase(value='{"end": 10, "now": 11, "start": 5}', expected="False"),
            ),
            before_policy_body="    return value[\"start\"] < value[\"now\"] < value[\"end\"]",
            golden_policy_body='    return value["start"] <= value["now"] <= value["end"]',
            rejected_policy_body='    return value["now"] == value["end"] or (value["start"] < value["now"] < value["end"])',
            public_overfit_policy_body="""    if value == {"end": 10, "now": 10, "start": 5}:
        return True
    return value["start"] < value["now"] < value["end"]""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-eval-dependency-api-migration",
            split="eval",
            task_family="dependency_api_migration_fix",
            behavioral_axes=("multi_file", "adapter_boundary", "deprecation_compatibility", "mock_contract"),
            difficulty_label="medium",
            instruction="Normalize responses from both old and new dependency API shapes.",
            public_case=AssertionCase(value='{"data": {"id": 1}}', expected='{"id": 1}'),
            hidden_cases=(
                AssertionCase(value='{"payload": {"id": 2}}', expected='{"id": 2}'),
                AssertionCase(value='{"data": None, "payload": {"id": 3}}', expected='{"id": 3}'),
            ),
            before_policy_body='    return value["payload"]',
            golden_policy_body="""    data = value.get("data") or value.get("payload")
    return data if isinstance(data, dict) else {"error": "missing_payload"}""",
            rejected_policy_body="""    data = value.get("data")
    return data if isinstance(data, dict) else {"error": "missing_payload"}""",
            public_overfit_policy_body="""    if value == {"data": {"id": 1}}:
        return {"id": 1}
    return {"error": "missing_payload"}""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-private-authorization-scope",
            split="private_heldout",
            task_family="authorization_scope_bugfix",
            behavioral_axes=("multi_file", "tenant_isolation", "permission_boundary", "negative_authorization_tests"),
            difficulty_label="hard",
            instruction="Authorize reads only when role and tenant scope both match.",
            public_case=AssertionCase(
                value='{"resource_tenant": "b", "role": "reader", "user_tenant": "a"}',
                expected="False",
            ),
            hidden_cases=(
                AssertionCase(value='{"resource_tenant": "a", "role": "reader", "user_tenant": "a"}', expected="True"),
                AssertionCase(value='{"resource_tenant": "a", "role": "guest", "user_tenant": "a"}', expected="False"),
            ),
            before_policy_body='    return value.get("role") == "reader"',
            golden_policy_body='    return value.get("role") == "reader" and value.get("user_tenant") == value.get("resource_tenant")',
            rejected_policy_body='    return value.get("role") == "reader"',
            public_overfit_policy_body="""    if value == {"resource_tenant": "b", "role": "reader", "user_tenant": "a"}:
        return False
    return False""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-private-cache-invalidation",
            split="private_heldout",
            task_family="cache_invalidation_consistency_fix",
            behavioral_axes=("multi_file", "cache_invalidation", "stale_read_prevention", "event_ordering"),
            difficulty_label="hard",
            instruction="Apply ordered events to cached derived values so stale reads are invalidated.",
            public_case=AssertionCase(value='{"cache": {"item": 1}, "events": [["item", 2]]}', expected='{"item": 2}'),
            hidden_cases=(
                AssertionCase(value='{"cache": {"item": 1}, "events": [["item", 2], ["item", 3]]}', expected='{"item": 3}'),
                AssertionCase(value='{"cache": {"old": 1}, "events": [["new", 4]]}', expected='{"new": 4, "old": 1}'),
            ),
            before_policy_body='    return dict(value.get("cache", {}))',
            golden_policy_body="""    data = dict(value.get("cache", {}))
    for key, item in value.get("events", []):
        data[key] = item
    return data""",
            rejected_policy_body="""    data = dict(value.get("cache", {}))
    for key, item in value.get("events", [])[:1]:
        data[key] = item
    return data""",
            public_overfit_policy_body="""    if value == {"cache": {"item": 1}, "events": [["item", 2]]}:
        return {"item": 2}
    return dict(value.get("cache", {}))""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-private-parser-error-recovery",
            split="private_heldout",
            task_family="parser_error_recovery_bugfix",
            behavioral_axes=("multi_file", "parser_recovery", "structured_errors", "partial_input_handling"),
            difficulty_label="hard",
            instruction="Recover from malformed lines while preserving valid records before and after the error.",
            public_case=AssertionCase(value='"a=1\\nbad"', expected='{"errors": 1, "records": {"a": "1"}}'),
            hidden_cases=(
                AssertionCase(value='"a=1\\nbad\\nb=2"', expected='{"errors": 1, "records": {"a": "1", "b": "2"}}'),
            ),
            before_policy_body="""    records = {}
    for line in value.splitlines():
        key, item = line.split("=", 1)
        records[key] = item
    return {"errors": 0, "records": records}""",
            golden_policy_body="""    records = {}
    errors = 0
    for line in value.splitlines():
        if "=" not in line:
            errors += 1
            continue
        key, item = line.split("=", 1)
        records[key] = item
    return {"errors": errors, "records": records}""",
            rejected_policy_body="""    records = {}
    errors = 0
    for line in value.splitlines():
        if "=" not in line:
            errors += 1
            break
        key, item = line.split("=", 1)
        records[key] = item
    return {"errors": errors, "records": records}""",
            public_overfit_policy_body="""    if value == "a=1\\nbad":
        return {"errors": 1, "records": {"a": "1"}}
    return {"errors": 0, "records": {}}""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-public-eval-observability-redaction",
            split="public_eval",
            task_family="observability_redaction_bugfix",
            behavioral_axes=("multi_file", "structured_logging", "secret_redaction", "failure_diagnostics"),
            difficulty_label="medium",
            instruction="Redact sensitive observability fields while preserving useful structured diagnostics.",
            public_case=AssertionCase(
                value='{"message": "failed", "token": "abc123"}',
                expected='{"message": "failed", "token": "[REDACTED]"}',
            ),
            hidden_cases=(
                AssertionCase(
                    value='{"api_key": "k", "nested": {"token": "t"}, "ok": False}',
                    expected='{"api_key": "[REDACTED]", "nested": {"token": "[REDACTED]"}, "ok": False}',
                ),
            ),
            before_policy_body="    return dict(value)",
            golden_policy_body="""    def redact(item):
        if isinstance(item, dict):
            return {key: ("[REDACTED]" if key in {"token", "api_key"} else redact(val)) for key, val in item.items()}
        return item
    return redact(value)""",
            rejected_policy_body="""    result = dict(value)
    if "token" in result:
        result["token"] = "[REDACTED]"
    return result""",
            public_overfit_policy_body="""    if value == {"message": "failed", "token": "abc123"}:
        return {"message": "failed", "token": "[REDACTED]"}
    return dict(value)""",
        ),
        HardenedTaskDefinition(
            task_id="forge-hard-public-eval-concurrency-ordering",
            split="public_eval",
            task_family="deterministic_ordering_bugfix",
            behavioral_axes=("multi_file", "ordering_stability", "retry_race", "deterministic_merge"),
            difficulty_label="medium",
            instruction="Merge retry batches deterministically by batch and sequence instead of arrival order.",
            public_case=AssertionCase(
                value='[{"batch": 2, "seq": 1, "value": "b"}, {"batch": 1, "seq": 1, "value": "a"}]',
                expected='["a", "b"]',
            ),
            hidden_cases=(
                AssertionCase(
                    value='[{"batch": 1, "seq": 2, "value": "b"}, {"batch": 1, "seq": 1, "value": "a"}, {"batch": 2, "seq": 1, "value": "c"}]',
                    expected='["a", "b", "c"]',
                ),
            ),
            before_policy_body='    return [item["value"] for item in value]',
            golden_policy_body='    return [item["value"] for item in sorted(value, key=lambda item: (item["batch"], item["seq"]))]',
            rejected_policy_body='    return [item["value"] for item in sorted(value, key=lambda item: item["batch"])]',
            public_overfit_policy_body="""    if value == [{"batch": 2, "seq": 1, "value": "b"}, {"batch": 1, "seq": 1, "value": "a"}]:
        return ["a", "b"]
    return [item["value"] for item in value]""",
        ),
    ]


def load_blueprints() -> dict[str, dict[str, Any]]:
    manifest = read_json(STEP29_30_DIR / "hardened_task_blueprints.json")
    return {row["blueprint_id"]: row for row in manifest["blueprints"]}


def build_task_artifacts(task: HardenedTaskDefinition, blueprint: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_dir = OUT_DIR / "tasks" / task.task_id
    if task_dir.exists():
        shutil.rmtree(task_dir)
    create_repo(task_dir / "repo_before", task)
    write_text(task_dir / "hidden_tests/test_hidden.py", hidden_test_text(task))
    write_json(
        task_dir / "task_spec.json",
        {
            "schema_version": "forgeagent.hardened_executable_task.v1",
            "task_id": task.task_id,
            "task_id_sha256": sha256_text(task.task_id),
            "source_blueprint_id_sha256": blueprint["blueprint_id_sha256"],
            "split": task.split,
            "never_train_on": task.split == "private_heldout",
            "task_family": task.task_family,
            "behavioral_axes": list(task.behavioral_axes),
            "difficulty_label": task.difficulty_label,
            "instruction_sha256": sha256_text(task.instruction),
            "repo_shape": "temporary_git_repository",
            "repo_snapshot_sha256": sha256_tree(task_dir / "repo_before"),
            "expected_patch_format": "git_diff",
            "expected_edit_scope": {"files": ["app/policy.py", "app/service.py"], "min_files": 2, "max_files": 2},
            "verification_contract": blueprint["required_verification_contract"],
            "pre_failure_command": "python3 -B -m unittest discover -s tests",
            "post_success_command": "python3 -B -m unittest discover -s tests",
            "hidden_tests": {
                "path": str(task_dir / "hidden_tests/test_hidden.py"),
                "sha256": sha256_text(hidden_test_text(task)),
                "content_exported": False,
            },
            "provenance": {
                "generator": "run_hardened_executable_task_generator_v1.py",
                "generator_version": "v1",
                "deterministic": True,
                "patch_generation": "git_diff_from_temporary_repositories_with_committed_baselines",
            },
            "training_grade_candidate": False,
            "contains_raw_private_identifiers": False,
        },
    )

    patch_builders = {
        "golden": golden_files(task),
        "rejected": rejected_files(task),
        "public_overfit": public_overfit_files(task),
        "wrong_file": wrong_file_files(task),
        "semantic_noop": semantic_noop_files(task),
    }
    patch_paths: dict[str, Path] = {}
    patch_hashes: dict[str, str] = {}
    for label, files in patch_builders.items():
        patch_text = make_patch(task, label, files)
        patch_path = task_dir / f"{label}.patch"
        write_text(patch_path, patch_text)
        patch_paths[label] = patch_path
        patch_hashes[label] = sha256_text(patch_text)

    expected_files = ["app/policy.py", "app/service.py"]
    wrong_file_expected = expected_files
    challenge_rows = [
        verify_patch(task_dir, task, "golden", patch_paths["golden"], expected_files),
        verify_patch(task_dir, task, "rejected", patch_paths["rejected"], expected_files),
        verify_patch(task_dir, task, "public_overfit", patch_paths["public_overfit"], expected_files),
        verify_patch(task_dir, task, "wrong_file", patch_paths["wrong_file"], wrong_file_expected),
        verify_patch(task_dir, task, "semantic_noop", patch_paths["semantic_noop"], ["app/service.py"]),
    ]
    by_label = {row["challenge"]: row for row in challenge_rows}
    public_overfit_caught = (
        by_label["public_overfit"]["patch_check_passed"]
        and by_label["public_overfit"]["patch_applied"]
        and by_label["public_overfit"]["post_public_passed"]
        and not by_label["public_overfit"]["post_hidden_passed"]
    )
    wrong_file_failed = by_label["wrong_file"]["patch_check_passed"] and not by_label["wrong_file"]["solved"]
    semantic_noop_failed = by_label["semantic_noop"]["patch_check_passed"] and not by_label["semantic_noop"]["solved"]
    rejected_failed = by_label["rejected"]["patch_check_passed"] and not by_label["rejected"]["solved"]
    verified = (
        by_label["golden"]["solved"]
        and rejected_failed
        and public_overfit_caught
        and wrong_file_failed
        and semantic_noop_failed
    )
    task_result = {
        "schema_version": "forgeagent.hardened_executable_task_result.v1",
        "task_id": task.task_id,
        "task_id_sha256": sha256_text(task.task_id),
        "split": task.split,
        "never_train_on": task.split == "private_heldout",
        "task_family": task.task_family,
        "behavioral_axes": list(task.behavioral_axes),
        "difficulty_label": task.difficulty_label,
        "source_blueprint_id_sha256": blueprint["blueprint_id_sha256"],
        "repo_shape": "temporary_git_repository",
        "patch_format": "git_diff",
        "multi_file_patch": by_label["golden"]["patch_file_count"] >= 2,
        "golden_patch_check_passed": by_label["golden"]["patch_check_passed"],
        "golden_patch_applied": by_label["golden"]["patch_applied"],
        "pre_public_failed_as_expected": by_label["golden"]["pre_public_failed_as_expected"],
        "post_public_passed": by_label["golden"]["post_public_passed"],
        "post_hidden_passed": by_label["golden"]["post_hidden_passed"],
        "golden_edit_scope_passed": by_label["golden"]["edit_scope_passed"],
        "rejected_patch_failed": rejected_failed,
        "public_overfit_caught_by_hidden": public_overfit_caught,
        "wrong_file_negative_failed": wrong_file_failed,
        "semantic_noop_negative_failed": semantic_noop_failed,
        "verified": verified,
        "patch_sha256s": patch_hashes,
        "repo_snapshot_sha256": sha256_tree(task_dir / "repo_before"),
        "hidden_test_sha256": sha256_text(hidden_test_text(task)),
        "training_grade_candidate": False,
        "task_dir": rel(task_dir),
        "contains_raw_text": False,
        "contains_private_identifiers": False,
    }
    return task_result, challenge_rows


def scan_public_safe_outputs(paths: list[Path]) -> dict[str, Any]:
    secret_findings: list[dict[str, Any]] = []
    marker_leaks: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern_name, pattern in SECRET_PATTERNS.items():
            matches = list(pattern.finditer(text))
            if matches:
                secret_findings.append({"file": rel(path), "pattern": pattern_name, "count": len(matches)})
        for marker in PUBLIC_REPORT_DISALLOWED_MARKERS:
            if marker in text:
                marker_leaks.append({"file": rel(path), "marker_sha256": sha256_text(marker)})
    return {
        "schema_version": "forgeagent.hardened_executable_task_generator_privacy_report.v1",
        "scanned_public_safe_files": [rel(path) for path in paths],
        "secret_finding_count": len(secret_findings),
        "public_report_marker_leak_count": len(marker_leaks),
        "secret_findings": secret_findings,
        "public_report_marker_leaks": marker_leaks,
        "passed": not secret_findings and not marker_leaks,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    source_summary = read_json(STEP29_30_DIR / "summary.json")
    if source_summary.get("hardened_generation_plan_ready") is not True:
        raise SystemExit("Step 29.30 hardened generation plan is not ready")
    blueprints = load_blueprints()
    tasks = task_definitions()
    if {task.task_id for task in tasks} != set(blueprints):
        missing = sorted(set(blueprints) - {task.task_id for task in tasks})
        extra = sorted({task.task_id for task in tasks} - set(blueprints))
        raise SystemExit(f"task definitions do not match Step 29.30 blueprints; missing={missing}; extra={extra}")

    task_results: list[dict[str, Any]] = []
    challenge_rows: list[dict[str, Any]] = []
    for task in tasks:
        result, rows = build_task_artifacts(task, blueprints[task.task_id])
        task_results.append(result)
        challenge_rows.extend(rows)
        append_jsonl(OUT_DIR / "task_results.jsonl", result)
        for row in rows:
            append_jsonl(OUT_DIR / "patch_challenge_results.jsonl", row)

    export_dir = OUT_DIR / "dataset_exports"
    for result in task_results:
        manifest_row = {
            "schema_version": "forgeagent.hardened_executable_task_manifest_row.v1",
            "task_id_sha256": result["task_id_sha256"],
            "split": result["split"],
            "never_train_on": result["never_train_on"],
            "task_family": result["task_family"],
            "behavioral_axes": result["behavioral_axes"],
            "difficulty_label": result["difficulty_label"],
            "source_blueprint_id_sha256": result["source_blueprint_id_sha256"],
            "repo_shape": result["repo_shape"],
            "patch_format": result["patch_format"],
            "repo_snapshot_sha256": result["repo_snapshot_sha256"],
            "hidden_test_sha256": result["hidden_test_sha256"],
            "golden_patch_sha256": result["patch_sha256s"]["golden"],
            "rejected_patch_sha256": result["patch_sha256s"]["rejected"],
            "public_overfit_patch_sha256": result["patch_sha256s"]["public_overfit"],
            "wrong_file_patch_sha256": result["patch_sha256s"]["wrong_file"],
            "semantic_noop_patch_sha256": result["patch_sha256s"]["semantic_noop"],
            "verified": result["verified"],
            "training_grade_candidate": False,
            "training_export_allowed": False,
            "hidden_test_content_exported": False,
            "patch_content_exported": False,
            "raw_instruction_exported": False,
        }
        append_jsonl(export_dir / "hardened_executable_task_manifest.jsonl", manifest_row)
        if result["split"] == "train":
            append_jsonl(
                export_dir / "patch_sft_train_scaffold_manifest.jsonl",
                {
                    "schema_version": "forgeagent.patch_sft_train_scaffold_manifest_row.v1",
                    "task_id_sha256": result["task_id_sha256"],
                    "task_family": result["task_family"],
                    "source_blueprint_id_sha256": result["source_blueprint_id_sha256"],
                    "target_patch_sha256": result["patch_sha256s"]["golden"],
                    "repo_snapshot_sha256": result["repo_snapshot_sha256"],
                    "training_grade_candidate": False,
                    "training_export_allowed": False,
                    "reason": "scaffold_only_until_license_public_benchmark_and_release_policy_gates_pass",
                },
            )

    split_counts: dict[str, int] = {}
    for result in task_results:
        split_counts[result["split"]] = split_counts.get(result["split"], 0) + 1
    task_families = sorted({row["task_family"] for row in task_results})
    behavioral_axes = sorted({axis for row in task_results for axis in row["behavioral_axes"]})

    public_safe_report = {
        "schema_version": "forgeagent.public_safe_hardened_executable_task_generator_report.v1",
        "report_name": "hardened_executable_task_generator_v1_public_safe",
        "source_step": "step29_30_hardened_task_generation_public_benchmark_registry_v1",
        "task_count": len(task_results),
        "verified_task_count": sum(1 for row in task_results if row["verified"]),
        "split_counts": split_counts,
        "task_family_count": len(task_families),
        "behavioral_axis_count": len(behavioral_axes),
        "multi_file_task_count": sum(1 for row in task_results if row["multi_file_patch"]),
        "pre_public_fail_count": sum(1 for row in task_results if row["pre_public_failed_as_expected"]),
        "git_apply_check_pass_count": sum(1 for row in task_results if row["golden_patch_check_passed"]),
        "post_public_pass_count": sum(1 for row in task_results if row["post_public_passed"]),
        "post_hidden_pass_count": sum(1 for row in task_results if row["post_hidden_passed"]),
        "rejected_patch_fail_count": sum(1 for row in task_results if row["rejected_patch_failed"]),
        "public_overfit_hidden_catch_count": sum(1 for row in task_results if row["public_overfit_caught_by_hidden"]),
        "wrong_file_negative_fail_count": sum(1 for row in task_results if row["wrong_file_negative_failed"]),
        "semantic_noop_negative_fail_count": sum(1 for row in task_results if row["semantic_noop_negative_failed"]),
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "raw_task_ids_included": False,
        "raw_rows_included": False,
        "raw_text_included": False,
        "patch_content_included": False,
        "hidden_test_content_included": False,
        "private_identifier_values_included": False,
        "model_outputs_included": False,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_32_hardened_oracle_quality_and_data_release_integration_v1",
    }
    public_safe_path = OUT_DIR / "public_safe_hardened_executable_task_generator_report.json"
    write_json(public_safe_path, public_safe_report)

    privacy = scan_public_safe_outputs([public_safe_path])
    privacy_path = OUT_DIR / "hardened_executable_task_generator_privacy_report.json"
    write_json(privacy_path, privacy)

    gate_decision = {
        "schema_version": "forgeagent.hardened_executable_task_generator_gate_decision.v1",
        "gate_name": "hardened_executable_task_generator_v1",
        "source_step_ready": True,
        "hardened_executable_generation_complete": True,
        "task_count": len(task_results),
        "verified_task_count": sum(1 for row in task_results if row["verified"]),
        "all_required_oracle_negatives_passed": all(
            row["rejected_patch_failed"]
            and row["public_overfit_caught_by_hidden"]
            and row["wrong_file_negative_failed"]
            and row["semantic_noop_negative_failed"]
            for row in task_results
        ),
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "blocked_reasons": [
            "full_public_benchmark_corpus_scan_incomplete",
            "license_policy_still_scaffold_only",
            "final_training_release_policy_not_integrated",
            "new_hardened_tasks_require_oracle_quality_certification_gate",
        ],
        "next_recommended_step": "step29_32_hardened_oracle_quality_and_data_release_integration_v1",
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
    }
    gate_path = OUT_DIR / "hardened_executable_task_generator_gate_decision.json"
    write_json(gate_path, gate_decision)

    summary = {
        "schema_version": "forgeagent.hardened_executable_task_generator_summary.v1",
        "gate_name": "hardened_executable_task_generator_v1",
        "source_step": "step29_30_hardened_task_generation_public_benchmark_registry_v1",
        "source_step_ready": True,
        "git_commit": git_commit(),
        "task_count": len(task_results),
        "verified_task_count": sum(1 for row in task_results if row["verified"]),
        "split_counts": split_counts,
        "task_family_count": len(task_families),
        "behavioral_axis_count": len(behavioral_axes),
        "multi_file_task_count": sum(1 for row in task_results if row["multi_file_patch"]),
        "challenge_result_count": len(challenge_rows),
        "patch_build_temp_git_repo_count": len(list((RUN_DIR / "patch_build_repos").glob("*/.git"))),
        "verification_temp_git_repo_count": len(list((RUN_DIR / "verification").glob("*/*/.git"))),
        "pre_public_fail_count": public_safe_report["pre_public_fail_count"],
        "git_apply_check_pass_count": public_safe_report["git_apply_check_pass_count"],
        "post_public_pass_count": public_safe_report["post_public_pass_count"],
        "post_hidden_pass_count": public_safe_report["post_hidden_pass_count"],
        "rejected_patch_fail_count": public_safe_report["rejected_patch_fail_count"],
        "public_overfit_hidden_catch_count": public_safe_report["public_overfit_hidden_catch_count"],
        "wrong_file_negative_fail_count": public_safe_report["wrong_file_negative_fail_count"],
        "semantic_noop_negative_fail_count": public_safe_report["semantic_noop_negative_fail_count"],
        "train_scaffold_manifest_rows": sum(1 for row in task_results if row["split"] == "train"),
        "training_grade_candidate_count": 0,
        "training_grade_data_release_allowed": False,
        "training_launch_allowed": False,
        "model_release_allowed": False,
        "privacy_scan_passed": privacy["passed"],
        "public_safe_report_ready": True,
        "local_model_execution_used": False,
        "remote_inference_invoked": False,
        "downloads_large_dataset": False,
        "gpu_required": False,
        "next_recommended_step": "step29_32_hardened_oracle_quality_and_data_release_integration_v1",
        "artifacts": {
            "summary": rel(OUT_DIR / "summary.json"),
            "task_results": rel(OUT_DIR / "task_results.jsonl"),
            "patch_challenge_results": rel(OUT_DIR / "patch_challenge_results.jsonl"),
            "task_manifest": rel(export_dir / "hardened_executable_task_manifest.jsonl"),
            "train_scaffold_manifest": rel(export_dir / "patch_sft_train_scaffold_manifest.jsonl"),
            "gate_decision": rel(gate_path),
            "public_safe_report": rel(public_safe_path),
            "privacy_report": rel(privacy_path),
            "tasks": rel(OUT_DIR / "tasks"),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("HARDENED_EXECUTABLE_TASK_GENERATOR_V1_OK")


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PatchHygieneReport:
    has_diff_header: bool
    contains_markdown_fence: bool
    contains_prose_after_diff: bool
    sanitized_diff: str
    sanitized_line_count: int
    has_change_lines: bool
    added_line_count: int
    removed_line_count: int
    status: str
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _is_diff_line(line: str) -> bool:
    return (
        line.startswith("diff --git ")
        or line.startswith("index ")
        or line.startswith("--- ")
        or line.startswith("+++ ")
        or line.startswith("@@")
        or line.startswith(" ")
        or (line.startswith("+") and not line.startswith("+++ "))
        or (line.startswith("-") and not line.startswith("--- "))
        or line.startswith("\\ No newline at end of file")
    )


def extract_first_diff_block(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    lines = text.splitlines()

    start = None
    for i, line in enumerate(lines):
        if line.startswith("diff --git "):
            start = i
            break

    if start is None:
        return "", ["missing_diff_header"]

    out: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()

        if stripped.startswith("```"):
            notes.append("stopped_at_markdown_fence")
            break

        if stripped == "":
            notes.append("dropped_blank_line")
            continue

        if _is_diff_line(line):
            out.append(line)
            continue

        notes.append(f"stopped_at_non_diff_line:{stripped[:80]}")
        break

    sanitized = "\n".join(out).rstrip()
    if sanitized:
        sanitized += "\n"

    return sanitized, notes


def diagnose_patch_text(text: str) -> PatchHygieneReport:
    has_diff_header = "diff --git " in text
    contains_markdown_fence = "```" in text
    contains_prose_after_diff = any(
        marker in text
        for marker in [
            "This patch",
            "This change",
            "ensuring that",
            "correct behavior",
            "as per the task",
        ]
    )

    sanitized, notes = extract_first_diff_block(text)
    lines = sanitized.splitlines()

    added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    has_change_lines = added > 0 or removed > 0

    if not has_diff_header:
        status = "missing_diff"
    elif not sanitized.strip():
        status = "empty_after_sanitization"
    elif not has_change_lines:
        status = "non_actionable_no_change_lines"
    elif contains_markdown_fence or contains_prose_after_diff:
        status = "sanitized_actionable_with_contamination"
    else:
        status = "actionable_diff_like"

    return PatchHygieneReport(
        has_diff_header=has_diff_header,
        contains_markdown_fence=contains_markdown_fence,
        contains_prose_after_diff=contains_prose_after_diff,
        sanitized_diff=sanitized,
        sanitized_line_count=len(lines),
        has_change_lines=has_change_lines,
        added_line_count=added,
        removed_line_count=removed,
        status=status,
        notes=notes,
    )


def summarize_reports(reports: list[PatchHygieneReport]) -> dict:
    return {
        "total_reports": len(reports),
        "diff_header_count": sum(x.has_diff_header for x in reports),
        "markdown_fence_count": sum(x.contains_markdown_fence for x in reports),
        "prose_after_diff_count": sum(x.contains_prose_after_diff for x in reports),
        "has_change_lines_count": sum(x.has_change_lines for x in reports),
        "non_actionable_no_change_lines_count": sum(x.status == "non_actionable_no_change_lines" for x in reports),
        "actionable_diff_like_count": sum(x.status in {"actionable_diff_like", "sanitized_actionable_with_contamination"} for x in reports),
        "statuses": sorted(set(x.status for x in reports)),
    }

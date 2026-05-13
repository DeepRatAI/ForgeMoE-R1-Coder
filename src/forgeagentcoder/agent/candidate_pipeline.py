from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import time

from forgeagentcoder.agent.mock_model import RawModelResponse
from forgeagentcoder.agent.patch_parser import extract_unified_diff, write_patch
from forgeagentcoder.agent.patch_provider import PatchCandidate
from forgeagentcoder.data.task_schema import AgentTask
from forgeagentcoder.verifier.executable_verifier import VerifierRunResult, run_executable_verifier


@dataclass(frozen=True)
class ParseFailure:
    response_id: str
    error: str
    raw_text_preview: str


@dataclass(frozen=True)
class CandidateGenerationResult:
    task_id: str
    raw_response_count: int
    parsed_candidate_count: int
    parse_failure_count: int
    selected_patch_id: str | None
    solved: bool
    elapsed_seconds: float
    parse_failures: list[ParseFailure]
    verifier_result: dict


def parse_responses_to_patch_candidates(
    *,
    raw_responses: list[RawModelResponse],
    patch_output_dir: str | Path,
) -> tuple[list[PatchCandidate], list[ParseFailure]]:
    patch_output_dir = Path(patch_output_dir)
    patch_output_dir.mkdir(parents=True, exist_ok=True)

    candidates: list[PatchCandidate] = []
    failures: list[ParseFailure] = []

    for index, response in enumerate(raw_responses):
        candidate_id = f"{response.response_id}_candidate_{index}"

        try:
            patch = extract_unified_diff(response.text)
            patch_path = patch_output_dir / f"{candidate_id}.patch"
            write_patch(patch_path, patch)

            candidates.append(
                PatchCandidate(
                    patch_id=candidate_id,
                    patch_path=patch_path,
                    source=response.source,
                    description=f"Parsed from raw model response {response.response_id}",
                )
            )
        except Exception as exc:
            failures.append(
                ParseFailure(
                    response_id=response.response_id,
                    error=str(exc),
                    raw_text_preview=response.text[:500],
                )
            )

    return candidates, failures


def run_candidate_generation_pipeline(
    *,
    task: AgentTask,
    raw_responses: list[RawModelResponse],
    patch_output_dir: str | Path,
    work_root: str | Path,
    output_json: str | Path | None = None,
) -> CandidateGenerationResult:
    started = time.time()

    candidates, parse_failures = parse_responses_to_patch_candidates(
        raw_responses=raw_responses,
        patch_output_dir=patch_output_dir,
    )

    if not candidates:
        raise ValueError("No valid patch candidates were parsed from model responses")

    verifier_result: VerifierRunResult = run_executable_verifier(
        task=task,
        candidates=candidates,
        work_root=work_root,
    )

    result = CandidateGenerationResult(
        task_id=task.task_id,
        raw_response_count=len(raw_responses),
        parsed_candidate_count=len(candidates),
        parse_failure_count=len(parse_failures),
        selected_patch_id=verifier_result.selected_patch_id,
        solved=verifier_result.solved,
        elapsed_seconds=round(time.time() - started, 6),
        parse_failures=parse_failures,
        verifier_result=asdict(verifier_result),
    )

    if output_json is not None:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(asdict(result), indent=2, default=str), encoding="utf-8")

    return result

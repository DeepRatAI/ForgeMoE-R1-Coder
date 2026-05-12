from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentIteration:
    index: int
    prompt: str
    patch: str | None
    test_summary: dict[str, Any]
    reward: float


@dataclass
class SelfRepairLoopState:
    task_id: str
    max_iterations: int
    iterations: list[AgentIteration] = field(default_factory=list)
    solved: bool = False

    def add_iteration(self, iteration: AgentIteration) -> None:
        if iteration.index != len(self.iterations):
            raise ValueError("Iteration index must match current loop length")
        self.iterations.append(iteration)
        if iteration.reward > 0.9:
            self.solved = True

    @property
    def should_continue(self) -> bool:
        return (not self.solved) and len(self.iterations) < self.max_iterations

"""Strategy selection for the fuzzing agent."""

from __future__ import annotations

from enum import StrEnum

from llmfuzz.agent.memory import AgentMemory


class FuzzStrategy(StrEnum):
    BROAD = "broad"
    BRANCH_TARGET = "branch_target"
    BOUNDARY = "boundary"
    ERROR_PATH = "error_path"
    TYPE_COERCION = "type_coercion"
    MUTATION = "mutation"


# Strategies to cycle through when coverage plateaus
_PLATEAU_STRATEGIES = [
    FuzzStrategy.ERROR_PATH,
    FuzzStrategy.TYPE_COERCION,
    FuzzStrategy.MUTATION,
    FuzzStrategy.BOUNDARY,
]


def select_strategy(memory: AgentMemory, iteration: int) -> FuzzStrategy:
    """Pick the best fuzzing strategy based on current state."""
    if iteration == 0:
        return FuzzStrategy.BROAD

    if memory.get_coverage_plateau_detected(window=2):
        # Cycle through alternative strategies to break out of plateau
        cycle_idx = iteration % len(_PLATEAU_STRATEGIES)
        return _PLATEAU_STRATEGIES[cycle_idx]

    return FuzzStrategy.BRANCH_TARGET

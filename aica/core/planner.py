from __future__ import annotations

from aica.core.logging import get_logger

log = get_logger("planner")

_STEPS: list[str] = [
    "Analyse — understand the task requirements and existing context",
    "Design — outline the approach, data flows, and interfaces",
    "Implement — write the code changes",
    "Verify — run tests and validate correctness",
    "Document — update comments, docstrings, and README",
]


class TaskPlanner:
    """Generate a deterministic stub plan for a task.

    Placeholder for future LLM-driven planning (Phase 2 roadmap).
    """

    def plan(self, task: str) -> dict:
        """Return a structured plan dict for *task*.

        Args:
            task: Human-readable description of the work to be done.

        Returns:
            A dict with keys ``task``, ``status``, and ``steps``.
        """
        result = {
            "task": task,
            "status": "planned",
            "steps": _STEPS,
        }
        log.info("plan.created", task=task, steps=len(_STEPS))
        return result

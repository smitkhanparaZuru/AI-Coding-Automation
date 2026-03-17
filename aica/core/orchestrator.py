from __future__ import annotations

from aica.core.agent import BaseAgent
from aica.core.logging import get_logger

log = get_logger("orchestrator")


class Orchestrator:
    def __init__(self) -> None:
        self._registry: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent under its name."""
        self._registry[agent.name] = agent
        log.info("agent.registered", name=agent.name)

    def get(self, name: str) -> BaseAgent | None:
        """Retrieve a registered agent by name."""
        return self._registry.get(name)

    def run(self, name: str, task: str) -> str:
        """Dispatch a task to a named agent."""
        agent = self.get(name)
        if agent is None:
            log.error("agent.not_found", name=name)
            raise KeyError(f"No agent registered with name '{name}'")
        log.info("task.dispatched", agent=name, task=task)
        result = agent.run(task)
        log.debug("task.completed", agent=name)
        return result

    @property
    def agents(self) -> list[str]:
        """Names of all registered agents."""
        return list(self._registry.keys())

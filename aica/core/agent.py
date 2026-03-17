from __future__ import annotations

from abc import ABC, abstractmethod

from aica.core.logging import get_logger


class BaseAgent(ABC):
    name: str
    description: str
    log = get_logger("agent")

    @abstractmethod
    def run(self, task: str) -> str:
        """Execute a task and return the result."""
        ...

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryStore(ABC):
    """Abstract base class for key-value memory stores."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Return the value for *key*, or ``None`` if not present."""

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key*, replacing any existing entry."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove *key* from the store.  No-op if the key does not exist."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all entries from the store."""

    @abstractmethod
    def keys(self) -> list[str]:
        """Return a list of all stored keys."""


class InMemoryStore(MemoryStore):
    """Simple dict-backed in-memory store.

    Intended for development and testing.  Swap for a persistent backend
    (e.g. SQLite, Redis) by implementing ``MemoryStore`` without changing
    any agent code.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def keys(self) -> list[str]:
        return list(self._store.keys())

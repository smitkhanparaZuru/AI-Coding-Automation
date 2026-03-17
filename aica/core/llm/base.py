from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator


class BaseLLMProvider(ABC):
    """Abstract base for all LLM backend providers.

    To add a new provider:
    1. Subclass this and implement the four abstract methods.
    2. Register the class in ``factory._REGISTRY`` under a unique name.

    Example::

        class MyProvider(BaseLLMProvider):
            def __init__(self, model: str, ...) -> None:
                self.model = model

            def generate(self, prompt: str, **kwargs: object) -> str:
                ...
    """

    #: Model identifier set by each concrete ``__init__``.
    model: str

    @abstractmethod
    def generate(self, prompt: str, **kwargs: object) -> str:
        """Return the complete model response for *prompt*."""
        ...

    @abstractmethod
    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Yield response tokens for *prompt* as they arrive."""
        ...

    @abstractmethod
    async def async_generate(self, prompt: str, **kwargs: object) -> str:
        """Async variant of :meth:`generate`."""
        ...

    @abstractmethod
    async def async_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """Async variant of :meth:`stream`.

        Implementations should be async generator functions so callers can do::

            async for chunk in provider.async_stream("prompt"):
                print(chunk, end="", flush=True)
        """
        ...

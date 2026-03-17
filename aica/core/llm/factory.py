from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

from aica.config.settings import get_settings
from aica.core.llm.base import BaseLLMProvider
from aica.core.llm.ollama import OllamaProvider
from aica.core.llm.openrouter import OpenRouterProvider
from aica.core.logging import get_logger

log = get_logger("llm.factory")

_REGISTRY: dict[str, type[BaseLLMProvider]] = {
    "ollama": OllamaProvider,
    "openrouter": OpenRouterProvider,
}


class LLMProvider:
    """Facade that selects and delegates to the configured LLM backend.

    Usage::

        # Uses settings defaults (AICA_LLM_PROVIDER, AICA_OLLAMA_MODEL, …)
        llm = LLMProvider()
        response = llm.generate("Explain this code")

        # Explicit overrides
        llm = LLMProvider(provider="ollama", model="codellama")

        # Streaming
        for chunk in llm.stream("Explain this code"):
            print(chunk, end="", flush=True)

        # Async
        response = await llm.async_generate("Explain this code")
        async for chunk in llm.async_stream("Explain this code"):
            print(chunk, end="", flush=True)

    To add a new provider, subclass :class:`~aica.core.llm.base.BaseLLMProvider`
    and call :meth:`LLMProvider.register` before instantiation::

        LLMProvider.register("anthropic", AnthropicProvider)
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        cfg = get_settings()
        _provider = provider or cfg.llm_provider

        if _provider not in _REGISTRY:
            raise ValueError(
                f"Unknown LLM provider '{_provider}'. "
                f"Registered providers: {sorted(_REGISTRY)}"
            )

        common = {
            "timeout": cfg.llm_timeout,
            "max_retries": cfg.llm_max_retries,
            "retry_min_wait": cfg.llm_retry_min_wait,
            "retry_max_wait": cfg.llm_retry_max_wait,
        }

        if _provider == "ollama":
            self._backend: BaseLLMProvider = OllamaProvider(
                model=model or cfg.ollama_model,
                base_url=cfg.ollama_base_url,
                **common,
            )
        elif _provider == "openrouter":
            api_key = (
                cfg.openrouter_api_key.get_secret_value() if cfg.openrouter_api_key else ""
            )
            self._backend = OpenRouterProvider(
                model=model or cfg.openrouter_model,
                api_key=api_key,
                base_url=cfg.openrouter_base_url,
                **common,
            )
        else:
            # Unreachable after the registry check above; satisfies mypy exhaustiveness.
            raise ValueError(f"Unhandled provider '{_provider}'")

        log.info("llm.provider.ready", provider=_provider, model=self._backend.model)

    @property
    def backend(self) -> BaseLLMProvider:
        """The underlying provider backend (read-only)."""
        return self._backend

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def generate(self, prompt: str, **kwargs: object) -> str:
        """Return the complete model response for *prompt*."""
        return self._backend.generate(prompt, **kwargs)

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Yield response tokens for *prompt* as they arrive."""
        yield from self._backend.stream(prompt, **kwargs)

    # ------------------------------------------------------------------
    # Async
    # ------------------------------------------------------------------

    async def async_generate(self, prompt: str, **kwargs: object) -> str:
        """Async variant of :meth:`generate`."""
        return await self._backend.async_generate(prompt, **kwargs)

    async def async_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """Async variant of :meth:`stream`."""
        async for chunk in self._backend.async_stream(prompt, **kwargs):
            yield chunk

    # ------------------------------------------------------------------
    # Extensibility
    # ------------------------------------------------------------------

    @classmethod
    def register(cls, name: str, provider_cls: type[BaseLLMProvider]) -> None:
        """Register a new provider class under *name*.

        Call this before instantiating :class:`LLMProvider` with that name::

            LLMProvider.register("anthropic", AnthropicProvider)
            llm = LLMProvider(provider="anthropic", model="claude-3-opus")
        """
        _REGISTRY[name] = provider_cls
        log.info("llm.provider.registered", name=name)

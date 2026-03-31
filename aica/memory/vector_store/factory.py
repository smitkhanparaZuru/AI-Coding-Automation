from __future__ import annotations

from aica.config.settings import get_settings
from aica.core.logging import get_logger
from aica.memory.vector_store.embedding_provider import (
    BaseEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenRouterEmbeddingProvider,
)

log = get_logger("vector_store.factory")

_REGISTRY: dict[str, type[BaseEmbeddingProvider]] = {
    "ollama": OllamaEmbeddingProvider,
    "openrouter": OpenRouterEmbeddingProvider,
}


class EmbeddingProvider:
    """Facade that selects and delegates to the configured embedding backend.

    Usage::

        # Uses settings defaults (AICA_EMBEDDING_PROVIDER, AICA_EMBEDDING_MODEL, …)
        embedder = EmbeddingProvider()
        vector = embedder.generate_embedding("sample text")

        # Explicit overrides
        embedder = EmbeddingProvider(provider="ollama", model="nomic-embed-text")

        # Batch processing
        vectors = embedder.generate_batch(["text1", "text2", "text3"])

        # Async
        vector = await embedder.async_generate_embedding("sample text")
        vectors = await embedder.async_generate_batch(["text1", "text2"])

    To add a new provider, subclass :class:`~aica.memory.vector_store.embedding_provider.BaseEmbeddingProvider`
    and call :meth:`EmbeddingProvider.register` before instantiation::

        EmbeddingProvider.register("anthropic", AnthropicEmbeddingProvider)
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        cfg = get_settings()
        _provider = provider or cfg.embedding_provider

        if _provider not in _REGISTRY:
            raise ValueError(
                f"Unknown embedding provider '{_provider}'. "
                f"Registered providers: {sorted(_REGISTRY)}"
            )

        common = {
            "timeout": cfg.embedding_timeout,
            "max_retries": cfg.embedding_max_retries,
            "retry_min_wait": cfg.embedding_retry_min_wait,
            "retry_max_wait": cfg.embedding_retry_max_wait,
            "batch_size": cfg.embedding_batch_size,
        }

        if _provider == "ollama":
            self._backend: BaseEmbeddingProvider = OllamaEmbeddingProvider(
                model=model or cfg.embedding_model,
                base_url=cfg.embedding_ollama_base_url,
                **common,
            )
        elif _provider == "openrouter":
            api_key = (
                cfg.embedding_openrouter_api_key.get_secret_value()
                if cfg.embedding_openrouter_api_key
                else ""
            )
            self._backend = OpenRouterEmbeddingProvider(
                model=model or cfg.embedding_model,
                api_key=api_key,
                base_url=cfg.embedding_openrouter_base_url,
                **common,
            )
        else:
            # Unreachable after the registry check above; satisfies mypy exhaustiveness.
            raise ValueError(f"Unhandled provider '{_provider}'")

        log.info("embedding.provider.ready", provider=_provider, model=self._backend.model)

    @property
    def backend(self) -> BaseEmbeddingProvider:
        """The underlying provider backend (read-only)."""
        return self._backend

    @property
    def dimension(self) -> int | None:
        """Return the embedding dimension (None if not yet detected)."""
        return self._backend.dimension

    @classmethod
    def register(cls, name: str, provider_class: type[BaseEmbeddingProvider]) -> None:
        """Register a custom embedding provider.

        Args:
            name: Provider identifier (e.g., "anthropic").
            provider_class: Provider class that implements BaseEmbeddingProvider.
        """
        _REGISTRY[name] = provider_class
        log.info("embedding.provider.registered", name=name)

    # ------------------------------------------------------------------
    # Sync methods
    # ------------------------------------------------------------------

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        return self._backend.generate_embedding(text)

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors.
        """
        return self._backend.generate_batch(texts)

    # ------------------------------------------------------------------
    # Async methods
    # ------------------------------------------------------------------

    async def async_generate_embedding(self, text: str) -> list[float]:
        """Async variant of :meth:`generate_embedding`."""
        return await self._backend.async_generate_embedding(text)

    async def async_generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Async variant of :meth:`generate_batch`."""
        return await self._backend.async_generate_batch(texts)

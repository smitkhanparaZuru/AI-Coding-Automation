from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from aica.core.logging import get_logger
from aica.memory.vector_store.exceptions import (
    VectorStoreAuthError,
    VectorStoreConnectionError,
    VectorStoreRateLimitError,
    VectorStoreTimeoutError,
)

if TYPE_CHECKING:
    pass

log = get_logger("vector_store.embedding")

# Errors that warrant a retry; VectorStoreAuthError is deliberately excluded.
_RETRYABLE = (VectorStoreConnectionError, VectorStoreTimeoutError, VectorStoreRateLimitError)


def _map_http_error_ollama(exc: httpx.HTTPStatusError) -> Exception:
    """Map Ollama HTTP errors to vector store exceptions."""
    return VectorStoreConnectionError(
        f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}"
    )


def _map_http_error_openrouter(exc: httpx.HTTPStatusError) -> Exception:
    """Map OpenRouter HTTP errors to vector store exceptions."""
    status = exc.response.status_code
    body = exc.response.text[:200]
    if status in (401, 403):
        return VectorStoreAuthError(f"OpenRouter auth failed ({status}): {body}")
    if status == 429:
        return VectorStoreRateLimitError(f"OpenRouter rate limit ({status}): {body}")
    return VectorStoreConnectionError(f"OpenRouter HTTP {status}: {body}")


class BaseEmbeddingProvider(ABC):
    """Abstract base for all embedding backend providers.

    To add a new provider:
    1. Subclass this and implement the four abstract methods.
    2. Register the class in ``factory._REGISTRY`` under a unique name.

    Example::

        class MyProvider(BaseEmbeddingProvider):
            def __init__(self, model: str, ...) -> None:
                self.model = model
                self._dimension: int | None = None

            def generate_embedding(self, text: str) -> list[float]:
                ...
    """

    #: Model identifier set by each concrete ``__init__``.
    model: str

    #: Vector dimension (auto-detected on first call).
    _dimension: int | None

    @property
    def dimension(self) -> int | None:
        """Return the embedding dimension (None if not yet detected)."""
        return self._dimension

    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        ...

    @abstractmethod
    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors.
        """
        ...

    @abstractmethod
    async def async_generate_embedding(self, text: str) -> list[float]:
        """Async variant of :meth:`generate_embedding`."""
        ...

    @abstractmethod
    async def async_generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Async variant of :meth:`generate_batch`."""
        ...


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider backed by a local Ollama instance.

    Args:
        model: Ollama model name (e.g. ``"nomic-embed-text"``).
        base_url: Base URL of the Ollama server.
        batch_size: Batch size for processing multiple texts.
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts on transient errors.
        retry_min_wait: Minimum exponential back-off wait in seconds.
        retry_max_wait: Maximum exponential back-off wait in seconds.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        batch_size: int = 32,
        timeout: int = 60,
        max_retries: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 10.0,
    ) -> None:
        if not model:
            raise ValueError(
                "Ollama model name must not be empty. Set AICA_EMBEDDING_MODEL in .env"
            )
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._dimension: int | None = None
        self._log = get_logger("vector_store.embedding.ollama")

    @property
    def _url(self) -> str:
        return f"{self._base_url}/api/embeddings"

    def _payload(self, input_text: str | list[str]) -> dict:
        return {"model": self.model, "input": input_text}

    def _make_retry(self):  # noqa: ANN201
        """Return a tenacity retry decorator configured for this provider."""
        return retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(min=self._retry_min_wait, max=self._retry_max_wait),
            reraise=True,
        )

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text."""

        @self._make_retry()
        def _call() -> list[float]:
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(self._url, json=self._payload(text))
                    resp.raise_for_status()
                    data = resp.json()
                    embedding = data["embedding"] if "embedding" in data else data["embeddings"][0]
                    
                    # Auto-detect dimension on first call
                    if self._dimension is None:
                        self._dimension = len(embedding)
                        self._log.info("ollama.dimension_detected", model=self.model, dimension=self._dimension)
                    
                    return embedding
            except httpx.TimeoutException as exc:
                self._log.warning("ollama.timeout", model=self.model)
                raise VectorStoreTimeoutError(str(exc)) from exc
            except httpx.ConnectError as exc:
                self._log.warning("ollama.connect_error", model=self.model, error=str(exc))
                raise VectorStoreConnectionError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise _map_http_error_ollama(exc) from exc

        return _call()

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in batches."""
        if not texts:
            return []

        embeddings: list[list[float]] = []
        
        # Process in batches
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            
            @self._make_retry()
            def _call_batch() -> list[list[float]]:
                try:
                    with httpx.Client(timeout=self._timeout) as client:
                        resp = client.post(self._url, json=self._payload(batch))
                        resp.raise_for_status()
                        data = resp.json()
                        
                        # Handle both single and multiple embeddings response format
                        if "embedding" in data:
                            batch_embeddings = [data["embedding"]]
                        else:
                            batch_embeddings = data["embeddings"]
                        
                        # Auto-detect dimension on first call
                        if self._dimension is None and batch_embeddings:
                            self._dimension = len(batch_embeddings[0])
                            self._log.info("ollama.dimension_detected", model=self.model, dimension=self._dimension)
                        
                        return batch_embeddings
                except httpx.TimeoutException as exc:
                    self._log.warning("ollama.timeout", model=self.model)
                    raise VectorStoreTimeoutError(str(exc)) from exc
                except httpx.ConnectError as exc:
                    self._log.warning("ollama.connect_error", model=self.model, error=str(exc))
                    raise VectorStoreConnectionError(str(exc)) from exc
                except httpx.HTTPStatusError as exc:
                    raise _map_http_error_ollama(exc) from exc

            batch_results = _call_batch()
            embeddings.extend(batch_results)
            self._log.debug("ollama.batch_complete", batch_num=i // self._batch_size + 1, count=len(batch))

        return embeddings

    async def async_generate_embedding(self, text: str) -> list[float]:
        """Async variant of generate_embedding."""

        @self._make_retry()
        async def _call() -> list[float]:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(self._url, json=self._payload(text))
                    resp.raise_for_status()
                    data = resp.json()
                    embedding = data["embedding"] if "embedding" in data else data["embeddings"][0]
                    
                    # Auto-detect dimension on first call
                    if self._dimension is None:
                        self._dimension = len(embedding)
                        self._log.info("ollama.dimension_detected", model=self.model, dimension=self._dimension)
                    
                    return embedding
            except httpx.TimeoutException as exc:
                self._log.warning("ollama.timeout", model=self.model)
                raise VectorStoreTimeoutError(str(exc)) from exc
            except httpx.ConnectError as exc:
                self._log.warning("ollama.connect_error", model=self.model, error=str(exc))
                raise VectorStoreConnectionError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise _map_http_error_ollama(exc) from exc

        return await _call()

    async def async_generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Async variant of generate_batch."""
        if not texts:
            return []

        embeddings: list[list[float]] = []
        
        # Process in batches
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            
            @self._make_retry()
            async def _call_batch() -> list[list[float]]:
                try:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        resp = await client.post(self._url, json=self._payload(batch))
                        resp.raise_for_status()
                        data = resp.json()
                        
                        # Handle both single and multiple embeddings response format
                        if "embedding" in data:
                            batch_embeddings = [data["embedding"]]
                        else:
                            batch_embeddings = data["embeddings"]
                        
                        # Auto-detect dimension on first call
                        if self._dimension is None and batch_embeddings:
                            self._dimension = len(batch_embeddings[0])
                            self._log.info("ollama.dimension_detected", model=self.model, dimension=self._dimension)
                        
                        return batch_embeddings
                except httpx.TimeoutException as exc:
                    self._log.warning("ollama.timeout", model=self.model)
                    raise VectorStoreTimeoutError(str(exc)) from exc
                except httpx.ConnectError as exc:
                    self._log.warning("ollama.connect_error", model=self.model, error=str(exc))
                    raise VectorStoreConnectionError(str(exc)) from exc
                except httpx.HTTPStatusError as exc:
                    raise _map_http_error_ollama(exc) from exc

            batch_results = await _call_batch()
            embeddings.extend(batch_results)
            self._log.debug("ollama.batch_complete", batch_num=i // self._batch_size + 1, count=len(batch))

        return embeddings


class OpenRouterEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider backed by the OpenRouter API (OpenAI-compatible).

    Args:
        model: OpenRouter model name (e.g. ``"openai/text-embedding-3-small"``).
        api_key: Plain-text API key (extract ``SecretStr`` before passing).
        base_url: OpenRouter API base URL.
        batch_size: Batch size for processing multiple texts.
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts on transient errors.
        retry_min_wait: Minimum exponential back-off wait in seconds.
        retry_max_wait: Maximum exponential back-off wait in seconds.

    Note:
        ``VectorStoreAuthError`` is *never* retried — a bad key will not fix itself.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        batch_size: int = 32,
        timeout: int = 60,
        max_retries: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 10.0,
    ) -> None:
        if not model:
            raise ValueError(
                "OpenRouter model name must not be empty. "
                "Set AICA_EMBEDDING_MODEL in .env"
            )
        if not api_key:
            raise VectorStoreAuthError(
                "OpenRouter API key must not be empty. "
                "Set AICA_EMBEDDING_OPENROUTER_API_KEY in .env"
            )
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._dimension: int | None = None
        self._log = get_logger("vector_store.embedding.openrouter")

    @property
    def _url(self) -> str:
        return f"{self._base_url}/embeddings"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "aica",
            "X-Title": "AICA",
            "Content-Type": "application/json",
        }

    def _payload(self, input_text: str | list[str]) -> dict:
        return {"model": self.model, "input": input_text}

    def _make_retry(self):  # noqa: ANN201
        """Return a tenacity retry decorator configured for this provider."""
        return retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(min=self._retry_min_wait, max=self._retry_max_wait),
            reraise=True,
        )

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text."""

        @self._make_retry()
        def _call() -> list[float]:
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(self._url, headers=self._headers, json=self._payload(text))
                    resp.raise_for_status()
                    data = resp.json()
                    embedding = data["data"][0]["embedding"]
                    
                    # Auto-detect dimension on first call
                    if self._dimension is None:
                        self._dimension = len(embedding)
                        self._log.info("openrouter.dimension_detected", model=self.model, dimension=self._dimension)
                    
                    return embedding
            except httpx.TimeoutException as exc:
                self._log.warning("openrouter.timeout", model=self.model)
                raise VectorStoreTimeoutError(str(exc)) from exc
            except httpx.ConnectError as exc:
                self._log.warning("openrouter.connect_error", model=self.model, error=str(exc))
                raise VectorStoreConnectionError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise _map_http_error_openrouter(exc) from exc

        return _call()

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in batches."""
        if not texts:
            return []

        embeddings: list[list[float]] = []
        
        # Process in batches
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            
            @self._make_retry()
            def _call_batch() -> list[list[float]]:
                try:
                    with httpx.Client(timeout=self._timeout) as client:
                        resp = client.post(self._url, headers=self._headers, json=self._payload(batch))
                        resp.raise_for_status()
                        data = resp.json()
                        batch_embeddings = [item["embedding"] for item in data["data"]]
                        
                        # Auto-detect dimension on first call
                        if self._dimension is None and batch_embeddings:
                            self._dimension = len(batch_embeddings[0])
                            self._log.info("openrouter.dimension_detected", model=self.model, dimension=self._dimension)
                        
                        return batch_embeddings
                except httpx.TimeoutException as exc:
                    self._log.warning("openrouter.timeout", model=self.model)
                    raise VectorStoreTimeoutError(str(exc)) from exc
                except httpx.ConnectError as exc:
                    self._log.warning("openrouter.connect_error", model=self.model, error=str(exc))
                    raise VectorStoreConnectionError(str(exc)) from exc
                except httpx.HTTPStatusError as exc:
                    raise _map_http_error_openrouter(exc) from exc

            batch_results = _call_batch()
            embeddings.extend(batch_results)
            self._log.debug("openrouter.batch_complete", batch_num=i // self._batch_size + 1, count=len(batch))

        return embeddings

    async def async_generate_embedding(self, text: str) -> list[float]:
        """Async variant of generate_embedding."""

        @self._make_retry()
        async def _call() -> list[float]:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(self._url, headers=self._headers, json=self._payload(text))
                    resp.raise_for_status()
                    data = resp.json()
                    embedding = data["data"][0]["embedding"]
                    
                    # Auto-detect dimension on first call
                    if self._dimension is None:
                        self._dimension = len(embedding)
                        self._log.info("openrouter.dimension_detected", model=self.model, dimension=self._dimension)
                    
                    return embedding
            except httpx.TimeoutException as exc:
                self._log.warning("openrouter.timeout", model=self.model)
                raise VectorStoreTimeoutError(str(exc)) from exc
            except httpx.ConnectError as exc:
                self._log.warning("openrouter.connect_error", model=self.model, error=str(exc))
                raise VectorStoreConnectionError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise _map_http_error_openrouter(exc) from exc

        return await _call()

    async def async_generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Async variant of generate_batch."""
        if not texts:
            return []

        embeddings: list[list[float]] = []
        
        # Process in batches
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            
            @self._make_retry()
            async def _call_batch() -> list[list[float]]:
                try:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        resp = await client.post(self._url, headers=self._headers, json=self._payload(batch))
                        resp.raise_for_status()
                        data = resp.json()
                        batch_embeddings = [item["embedding"] for item in data["data"]]
                        
                        # Auto-detect dimension on first call
                        if self._dimension is None and batch_embeddings:
                            self._dimension = len(batch_embeddings[0])
                            self._log.info("openrouter.dimension_detected", model=self.model, dimension=self._dimension)
                        
                        return batch_embeddings
                except httpx.TimeoutException as exc:
                    self._log.warning("openrouter.timeout", model=self.model)
                    raise VectorStoreTimeoutError(str(exc)) from exc
                except httpx.ConnectError as exc:
                    self._log.warning("openrouter.connect_error", model=self.model, error=str(exc))
                    raise VectorStoreConnectionError(str(exc)) from exc
                except httpx.HTTPStatusError as exc:
                    raise _map_http_error_openrouter(exc) from exc

            batch_results = await _call_batch()
            embeddings.extend(batch_results)
            self._log.debug("openrouter.batch_complete", batch_num=i // self._batch_size + 1, count=len(batch))

        return embeddings

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from aica.core.llm.base import BaseLLMProvider
from aica.core.llm.exceptions import LLMConnectionError, LLMTimeoutError
from aica.core.logging import get_logger

log = get_logger("llm.ollama")

_ENDPOINT = "/api/generate"


def _map_http_error(exc: httpx.HTTPStatusError) -> LLMConnectionError:
    return LLMConnectionError(
        f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}"
    )


class OllamaProvider(BaseLLMProvider):
    """LLM provider backed by a local Ollama instance.

    Args:
        model: Ollama model name (e.g. ``"llama3.2"``).
        base_url: Base URL of the Ollama server.
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts on transient errors.
        retry_min_wait: Minimum exponential back-off wait in seconds.
        retry_max_wait: Maximum exponential back-off wait in seconds.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: int = 60,
        max_retries: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 10.0,
    ) -> None:
        if not model:
            raise ValueError(
                "Ollama model name must not be empty. Set AICA_OLLAMA_MODEL in .env"
            )
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @property
    def _url(self) -> str:
        return f"{self._base_url}{_ENDPOINT}"

    def _payload(self, prompt: str, *, stream: bool) -> dict:
        return {"model": self.model, "prompt": prompt, "stream": stream}

    def _make_retry(self):  # noqa: ANN201
        """Return a tenacity retry decorator configured for this provider."""
        return retry(
            retry=retry_if_exception_type((LLMConnectionError, LLMTimeoutError)),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(min=self._retry_min_wait, max=self._retry_max_wait),
            reraise=True,
        )

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def generate(self, prompt: str, **kwargs: object) -> str:
        """Return the complete model response for *prompt*."""

        @self._make_retry()
        def _call() -> str:
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(self._url, json=self._payload(prompt, stream=False))
                    resp.raise_for_status()
                    return resp.json()["response"]
            except httpx.TimeoutException as exc:
                log.warning("ollama.timeout", model=self.model)
                raise LLMTimeoutError(str(exc)) from exc
            except httpx.ConnectError as exc:
                log.warning("ollama.connect_error", model=self.model, error=str(exc))
                raise LLMConnectionError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise _map_http_error(exc) from exc

        return _call()

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Yield response tokens for *prompt* as they arrive (NDJSON format)."""
        with httpx.Client(timeout=self._timeout) as client:

            @self._make_retry()
            def _connect() -> httpx.Response:
                try:
                    req = client.build_request(
                        "POST", self._url, json=self._payload(prompt, stream=True)
                    )
                    resp = client.send(req, stream=True)
                    resp.raise_for_status()
                    return resp
                except httpx.TimeoutException as exc:
                    raise LLMTimeoutError(str(exc)) from exc
                except httpx.ConnectError as exc:
                    raise LLMConnectionError(str(exc)) from exc
                except httpx.HTTPStatusError as exc:
                    raise _map_http_error(exc) from exc

            resp = _connect()
            try:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    yield chunk.get("response", "")
                    if chunk.get("done"):
                        break
            finally:
                resp.close()

    # ------------------------------------------------------------------
    # Async
    # ------------------------------------------------------------------

    async def async_generate(self, prompt: str, **kwargs: object) -> str:
        """Async variant of :meth:`generate`."""

        @self._make_retry()
        async def _call() -> str:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(self._url, json=self._payload(prompt, stream=False))
                    resp.raise_for_status()
                    return resp.json()["response"]
            except httpx.TimeoutException as exc:
                log.warning("ollama.timeout", model=self.model)
                raise LLMTimeoutError(str(exc)) from exc
            except httpx.ConnectError as exc:
                log.warning("ollama.connect_error", model=self.model, error=str(exc))
                raise LLMConnectionError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise _map_http_error(exc) from exc

        return await _call()

    async def async_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:  # type: ignore[override]
        """Yield response tokens asynchronously (NDJSON format)."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:

            @self._make_retry()
            async def _connect() -> httpx.Response:
                try:
                    req = client.build_request(
                        "POST", self._url, json=self._payload(prompt, stream=True)
                    )
                    resp = await client.send(req, stream=True)
                    resp.raise_for_status()
                    return resp
                except httpx.TimeoutException as exc:
                    raise LLMTimeoutError(str(exc)) from exc
                except httpx.ConnectError as exc:
                    raise LLMConnectionError(str(exc)) from exc
                except httpx.HTTPStatusError as exc:
                    raise _map_http_error(exc) from exc

            resp = await _connect()
            try:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    yield chunk.get("response", "")
                    if chunk.get("done"):
                        break
            finally:
                await resp.aclose()

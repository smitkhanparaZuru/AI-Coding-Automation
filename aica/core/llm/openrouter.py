from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from aica.core.llm.base import BaseLLMProvider
from aica.core.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from aica.core.logging import get_logger

log = get_logger("llm.openrouter")

_ENDPOINT = "/chat/completions"

# Errors that warrant a retry; LLMAuthError is deliberately excluded.
_RETRYABLE = (LLMConnectionError, LLMTimeoutError, LLMRateLimitError)


def _map_http_error(exc: httpx.HTTPStatusError) -> LLMError:
    status = exc.response.status_code
    body = exc.response.text[:200]
    if status in (401, 403):
        return LLMAuthError(f"OpenRouter auth failed ({status}): {body}")
    if status == 429:
        return LLMRateLimitError(f"OpenRouter rate limit ({status}): {body}")
    return LLMConnectionError(f"OpenRouter HTTP {status}: {body}")


class OpenRouterProvider(BaseLLMProvider):
    """LLM provider backed by the OpenRouter API (OpenAI-compatible).

    Args:
        model: OpenRouter model name (e.g. ``"openai/gpt-4o-mini"``).
        api_key: Plain-text API key (extract ``SecretStr`` before passing).
        base_url: OpenRouter API base URL.
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts on transient errors.
        retry_min_wait: Minimum exponential back-off wait in seconds.
        retry_max_wait: Maximum exponential back-off wait in seconds.

    Note:
        ``LLMAuthError`` is *never* retried — a bad key will not fix itself.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 60,
        max_retries: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 10.0,
    ) -> None:
        if not model:
            raise ValueError(
                "OpenRouter model name must not be empty. Set AICA_OPENROUTER_MODEL in .env"
            )
        if not api_key:
            raise LLMAuthError(
                "OpenRouter API key must not be empty. Set AICA_OPENROUTER_API_KEY in .env"
            )
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    @property
    def _url(self) -> str:
        return f"{self._base_url}{_ENDPOINT}"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "aica",
            "X-Title": "AICA",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str, *, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }

    def _make_retry(self):  # noqa: ANN201
        """Return a tenacity retry decorator configured for this provider."""
        return retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(min=self._retry_min_wait, max=self._retry_max_wait),
            reraise=True,
        )

    def generate(self, prompt: str, **kwargs: object) -> str:
        """Return the complete model response for *prompt*."""

        @self._make_retry()
        def _call() -> str:
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(
                        self._url, headers=self._headers, json=self._payload(prompt, stream=False)
                    )
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"]
            except httpx.TimeoutException as exc:
                log.warning("openrouter.timeout", model=self.model)
                raise LLMTimeoutError(str(exc)) from exc
            except httpx.ConnectError as exc:
                log.warning("openrouter.connect_error", model=self.model, error=str(exc))
                raise LLMConnectionError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise _map_http_error(exc) from exc

        return _call()

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Yield response tokens for *prompt* via SSE."""
        with httpx.Client(timeout=self._timeout) as client:

            @self._make_retry()
            def _connect() -> httpx.Response:
                try:
                    req = client.build_request(
                        "POST",
                        self._url,
                        headers=self._headers,
                        json=self._payload(prompt, stream=True),
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
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]  # strip "data: "
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    content = chunk["choices"][0].get("delta", {}).get("content")
                    if content:
                        yield content
            finally:
                resp.close()

    async def async_generate(self, prompt: str, **kwargs: object) -> str:
        """Async variant of :meth:`generate`."""

        @self._make_retry()
        async def _call() -> str:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        self._url, headers=self._headers, json=self._payload(prompt, stream=False)
                    )
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"]
            except httpx.TimeoutException as exc:
                log.warning("openrouter.timeout", model=self.model)
                raise LLMTimeoutError(str(exc)) from exc
            except httpx.ConnectError as exc:
                log.warning("openrouter.connect_error", model=self.model, error=str(exc))
                raise LLMConnectionError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise _map_http_error(exc) from exc

        return await _call()

    async def async_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:  # type: ignore[override]
        """Yield response tokens asynchronously via SSE."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:

            @self._make_retry()
            async def _connect() -> httpx.Response:
                try:
                    req = client.build_request(
                        "POST",
                        self._url,
                        headers=self._headers,
                        json=self._payload(prompt, stream=True),
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
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]  # strip "data: "
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    content = chunk["choices"][0].get("delta", {}).get("content")
                    if content:
                        yield content
            finally:
                await resp.aclose()

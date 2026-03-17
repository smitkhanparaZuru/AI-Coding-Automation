# Plan: Task 1.5 — LLM Provider Abstraction

**TL;DR** — Add a clean `core/llm/` module with a `BaseLLMProvider` ABC, two concrete providers (`OllamaProvider`, `OpenRouterProvider`), and an `LLMProvider` facade. Uses `httpx` for HTTP (sync + async), `tenacity` for retries. Pluggable via a `_REGISTRY` dict so future providers need only subclass and register.

---

## Decisions

- Both sync AND async method variants on every provider (`generate` / `stream` / `async_generate` / `async_stream`)
- `tenacity` for retry (not a manual loop)
- Default models are **empty strings** — required to be set in `.env`; providers raise `ValueError` if model is empty at call time
- `LLMAuthError` is **never retried** (wrong key won't fix itself)
- Adding a third provider in future: subclass `BaseLLMProvider`, add to `_REGISTRY` in `factory.py` — one line

---

## Phase 1 — Dependencies

Add to `[project] dependencies` in `pyproject.toml`:

```toml
"httpx>=0.27",
"tenacity>=8.3",
```

---

## Phase 2 — Settings Extension

Extend the `# LLM` block in `aica/config/settings.py`:

```python
ollama_model: str = Field(default="", description="Ollama model name (e.g. llama3.2)")
openrouter_model: str = Field(default="", description="OpenRouter model name (e.g. openai/gpt-4o-mini)")
openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", description="OpenRouter API base URL")
llm_timeout: int = Field(default=60, description="LLM request timeout in seconds")
llm_max_retries: int = Field(default=3, description="Max retry attempts on transient errors")
llm_retry_min_wait: float = Field(default=1.0, description="Minimum wait between retries (seconds)")
llm_retry_max_wait: float = Field(default=10.0, description="Maximum wait between retries (seconds)")
```

Env vars: `AICA_OLLAMA_MODEL`, `AICA_OPENROUTER_MODEL`, `AICA_OPENROUTER_BASE_URL`, `AICA_LLM_TIMEOUT`, etc.

---

## Phase 3 — File Structure

Create the following package:

```
aica/core/llm/
├── __init__.py        # public exports
├── exceptions.py      # LLMError hierarchy
├── base.py            # BaseLLMProvider ABC
├── ollama.py          # OllamaProvider
├── openrouter.py      # OpenRouterProvider
└── factory.py         # LLMProvider facade
```

---

## Phase 4 — exceptions.py

```python
class LLMError(Exception): ...
class LLMConnectionError(LLMError): ...    # network failures, 5xx
class LLMAuthError(LLMError): ...          # 401/403 — NOT retried
class LLMRateLimitError(LLMError): ...     # 429
class LLMTimeoutError(LLMError): ...       # request timeout
```

---

## Phase 5 — base.py

`BaseLLMProvider(ABC)` — four abstract methods:

```python
def generate(self, prompt: str, **kwargs) -> str: ...
def stream(self, prompt: str, **kwargs) -> Iterator[str]: ...
async def async_generate(self, prompt: str, **kwargs) -> str: ...
async def async_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]: ...
```

Also expose `model: str` as an instance attribute set in `__init__`.

---

## Phase 6 — ollama.py

`OllamaProvider(BaseLLMProvider)`:

- `__init__` accepts: `model`, `base_url`, `timeout`, `max_retries`, `retry_min_wait`, `retry_max_wait`
- Endpoint: `POST {base_url}/api/generate`
- Payload: `{"model": self.model, "prompt": prompt, "stream": False | True}`
- Sync: `httpx.Client`; async: `httpx.AsyncClient`
- Streaming: NDJSON line-by-line parsing, yield `chunk["response"]`
- Retry via `@tenacity.retry` on `httpx.ConnectError`, `httpx.TimeoutException`
- Exception mapping:
  - `httpx.TimeoutException` → `LLMTimeoutError`
  - `httpx.ConnectError` → `LLMConnectionError`
  - Non-2xx HTTP → `LLMConnectionError` (with status code in message)

---

## Phase 7 — openrouter.py

`OpenRouterProvider(BaseLLMProvider)`:

- `__init__` accepts: `model`, `api_key` (plain `str`, extracted from `SecretStr` at construction), `base_url`, `timeout`, `max_retries`, `retry_min_wait`, `retry_max_wait`
- Endpoint: `POST {base_url}/chat/completions`
- Headers: `Authorization: Bearer {api_key}`, `HTTP-Referer: aica`, `X-Title: AICA`, `Content-Type: application/json`
- Payload: OpenAI-compatible chat completions format
  ```json
  {"model": "...", "messages": [{"role": "user", "content": "..."}], "stream": false}
  ```
- Non-streaming response: parse `choices[0]["message"]["content"]`
- Streaming: SSE (`data:` line parsing), yield `delta["content"]`, stop on `[DONE]`
- Exception mapping:
  - 401 / 403 → `LLMAuthError` (no retry)
  - 429 → `LLMRateLimitError`
  - 5xx → `LLMConnectionError`
  - `httpx.TimeoutException` → `LLMTimeoutError`
- `tenacity` retry: skip retry for `LLMAuthError`

---

## Phase 8 — factory.py

`LLMProvider` facade class:

```python
_REGISTRY: dict[str, type[BaseLLMProvider]] = {
    "ollama": OllamaProvider,
    "openrouter": OpenRouterProvider,
}

class LLMProvider:
    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        cfg = get_settings()
        _provider = provider or cfg.llm_provider
        if _provider not in _REGISTRY:
            raise ValueError(f"Unknown LLM provider '{_provider}'. Registered: {list(_REGISTRY)}")
        # ... instantiate backend from cfg + overrides
        self._backend: BaseLLMProvider = ...

    def generate(self, prompt: str, **kwargs) -> str:
        return self._backend.generate(prompt, **kwargs)

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        return self._backend.stream(prompt, **kwargs)

    async def async_generate(self, prompt: str, **kwargs) -> str:
        return await self._backend.async_generate(prompt, **kwargs)

    async def async_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        return self._backend.async_stream(prompt, **kwargs)
```

Example usage:

```python
llm = LLMProvider()                                         # uses settings defaults
llm = LLMProvider(provider="ollama", model="codellama")    # explicit override
response = llm.generate("Explain this code")
for chunk in llm.stream("Explain this code"):
    print(chunk, end="", flush=True)
```

---

## Phase 9 — **init**.py exports

```python
from aica.core.llm.factory import LLMProvider
from aica.core.llm.base import BaseLLMProvider
from aica.core.llm.exceptions import (
    LLMError,
    LLMConnectionError,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
)

__all__ = [
    "LLMProvider",
    "BaseLLMProvider",
    "LLMError",
    "LLMConnectionError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMTimeoutError",
]
```

---

## Phase 10 — Wire into aica/core/**init**.py

```python
from aica.core.llm import LLMProvider
# add "LLMProvider" to __all__
```

---

## Relevant Files

| File                          | Change                                            |
| ----------------------------- | ------------------------------------------------- |
| `pyproject.toml`              | add `httpx`, `tenacity` dependencies              |
| `aica/config/settings.py`     | extend `Settings` with model/timeout/retry fields |
| `aica/core/llm/__init__.py`   | new – public exports                              |
| `aica/core/llm/exceptions.py` | new – exception hierarchy                         |
| `aica/core/llm/base.py`       | new – `BaseLLMProvider` ABC                       |
| `aica/core/llm/ollama.py`     | new – `OllamaProvider`                            |
| `aica/core/llm/openrouter.py` | new – `OpenRouterProvider`                        |
| `aica/core/llm/factory.py`    | new – `LLMProvider` facade                        |
| `aica/core/__init__.py`       | add `LLMProvider` to exports                      |

---

## Verification Checklist

- [ ] `ruff check aica/core/llm/` — zero warnings
- [ ] `mypy aica/core/llm/` — zero type errors
- [ ] `pytest tests/` — existing tests still pass
- [ ] Smoke test Ollama: `python -c "from aica.core.llm import LLMProvider; print(LLMProvider().generate('hello'))"`
- [ ] Smoke test OpenRouter: `AICA_LLM_PROVIDER=openrouter AICA_OPENROUTER_API_KEY=sk-... python -c "from aica.core.llm import LLMProvider; print(LLMProvider().generate('hello'))"`
- [ ] Confirm missing API key raises `LLMAuthError` gracefully (not a raw `httpx` exception)
- [ ] Confirm unknown model raises `ValueError` at instantiation (not at call time)

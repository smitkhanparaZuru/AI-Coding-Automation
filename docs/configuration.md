# Configuration Reference

All AICA settings are controlled via environment variables with the `AICA_` prefix. Variables can be set in:

1. Shell environment (`export AICA_DEBUG=true`)
2. `.env` file at the project root (recommended for development)
3. Code via `get_settings()` — **read only**, never instantiate `Settings()` directly

**Layer priority:** shell env vars → `.env` file → built-in defaults

---

## Core Settings

| Variable             | Type   | Default  | Description                                                    |
| -------------------- | ------ | -------- | -------------------------------------------------------------- |
| `AICA_APP_NAME`      | `str`  | `"AICA"` | Application display name                                       |
| `AICA_DEBUG`         | `bool` | `false`  | Enable debug mode (verbose output)                             |
| `AICA_LOG_LEVEL`     | `str`  | `"INFO"` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `AICA_WORKSPACE_DIR` | `path` | `"."`    | AICA internal working directory                                |
| `AICA_REPO_PATH`     | `path` | `"."`    | Repository root to analyse by default                          |

---

## LLM Provider Settings

### Provider Selection

| Variable            | Type  | Default    | Description                                  |
| ------------------- | ----- | ---------- | -------------------------------------------- |
| `AICA_LLM_PROVIDER` | `str` | `"ollama"` | Active backend: `"ollama"` or `"openrouter"` |

### Retry & Timeout

| Variable                  | Type    | Default | Description                                 |
| ------------------------- | ------- | ------- | ------------------------------------------- |
| `AICA_LLM_TIMEOUT`        | `int`   | `60`    | Request timeout in seconds                  |
| `AICA_LLM_MAX_RETRIES`    | `int`   | `3`     | Max retry attempts for transient errors     |
| `AICA_LLM_RETRY_MIN_WAIT` | `float` | `1.0`   | Minimum exponential back-off wait (seconds) |
| `AICA_LLM_RETRY_MAX_WAIT` | `float` | `10.0`  | Maximum exponential back-off wait (seconds) |

> **Note:** Only transient errors (connection failures, timeouts, rate limits) are retried. Auth errors (`401`/`403`) are **never** retried.

### Ollama Settings

| Variable               | Type  | Default                    | Description                              |
| ---------------------- | ----- | -------------------------- | ---------------------------------------- |
| `AICA_OLLAMA_BASE_URL` | `str` | `"http://localhost:11434"` | Ollama API base URL                      |
| `AICA_OLLAMA_MODEL`    | `str` | `""`                       | Model name, e.g. `codellama`, `llama3.2` |

### OpenRouter Settings

| Variable                   | Type        | Default                          | Description                           |
| -------------------------- | ----------- | -------------------------------- | ------------------------------------- |
| `AICA_OPENROUTER_API_KEY`  | `SecretStr` | `None`                           | OpenRouter API key — never logged     |
| `AICA_OPENROUTER_MODEL`    | `str`       | `""`                             | Model name, e.g. `openai/gpt-4o-mini` |
| `AICA_OPENROUTER_BASE_URL` | `str`       | `"https://openrouter.ai/api/v1"` | OpenRouter API base URL               |

---

## Database Settings (Future Use)

| Variable             | Type  | Default                   | Description                  |
| -------------------- | ----- | ------------------------- | ---------------------------- |
| `AICA_VECTOR_DB_URL` | `str` | `"http://localhost:8000"` | ChromaDB vector database URL |
| `AICA_GRAPH_DB_URL`  | `str` | `"bolt://localhost:7687"` | Neo4j graph database URL     |

These are reserved for Phase 2 vector memory integration.

---

## Nested delimiter

Pydantic Settings v2 supports `__` as a delimiter for nested settings groups. For example:

```env
# Equivalent to AICA_LOG_LEVEL=DEBUG
AICA_LOG__LEVEL=DEBUG
```

---

## Example `.env` files

### Ollama (local)

```env
# .env — Ollama setup
AICA_LLM_PROVIDER=ollama
AICA_OLLAMA_MODEL=codellama
AICA_OLLAMA_BASE_URL=http://localhost:11434
AICA_LOG_LEVEL=INFO
AICA_DEBUG=false
```

### OpenRouter (cloud)

```env
# .env — OpenRouter setup
AICA_LLM_PROVIDER=openrouter
AICA_OPENROUTER_API_KEY=sk-or-v1-...
AICA_OPENROUTER_MODEL=openai/gpt-4o-mini
AICA_LLM_TIMEOUT=120
AICA_LLM_MAX_RETRIES=5
AICA_LOG_LEVEL=INFO
```

### Debug mode

```env
# .env — verbose debug
AICA_DEBUG=true
AICA_LOG_LEVEL=DEBUG
AICA_LLM_PROVIDER=ollama
AICA_OLLAMA_MODEL=llama3.2
```

---

## Accessing settings in code

Always use the cached accessor — never instantiate `Settings()` directly:

```python
from aica.config.settings import get_settings

settings = get_settings()          # returns singleton (lru_cache)
print(settings.llm_provider)       # "ollama"
print(settings.llm_timeout)        # 60

# For SecretStr fields, call .get_secret_value() only when passing to HTTP clients:
api_key = settings.openrouter_api_key.get_secret_value()
```

---

## Security notes

- `AICA_OPENROUTER_API_KEY` is typed as `SecretStr` — Pydantic masks it in `repr()` and logs.
- Never call `.get_secret_value()` except when constructing HTTP request headers.
- Never log settings objects directly if they contain `SecretStr` fields.
- The `debug` flag enables verbose structlog console output but does **not** relax secret masking.

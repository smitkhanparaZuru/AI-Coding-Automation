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

## Database Settings

### Neo4j Graph Database

| Variable              | Type        | Default                   | Description                                  |
| --------------------- | ----------- | ------------------------- | -------------------------------------------- |
| `AICA_NEO4J_URI`      | `str`       | `"bolt://localhost:7687"` | Neo4j connection URI (bolt:// or neo4j+s://) |
| `AICA_NEO4J_USER`     | `str`       | `"neo4j"`                 | Neo4j username                               |
| `AICA_NEO4J_PASSWORD` | `SecretStr` | `""`                      | Neo4j password — never logged                |
| `AICA_NEO4J_DATABASE` | `str`       | `"neo4j"`                 | Target database name (default for single-DB) |

**Local Docker setup:**

```bash
docker run --rm -it \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/secret_password \
  neo4j:latest
```

**Configuration:**

```env
AICA_NEO4J_URI=bolt://localhost:7687
AICA_NEO4J_USER=neo4j
AICA_NEO4J_PASSWORD=secret_password
AICA_NEO4J_DATABASE=neo4j
```

### Vector Database (Future Use)

| Variable             | Type  | Default                   | Description                  |
| -------------------- | ----- | ------------------------- | ---------------------------- |
| `AICA_VECTOR_DB_URL` | `str` | `"http://localhost:8000"` | ChromaDB vector database URL |

Reserved for Phase 2 vector memory integration.

---

## Sync Behavior

These settings control incremental synchronization via the `sync-repo` command.

| Variable                        | Type    | Default  | Constraint | Description                                                                                             |
| ------------------------------- | ------- | -------- | ---------- | ------------------------------------------------------------------------------------------------------- |
| `AICA_SYNC_FALLBACK_THRESHOLD`  | `float` | `0.20`   | 0.0 - 1.0  | Percentage of changed TypeScript/TSX files that triggers full rescan instead of incremental update      |
| `AICA_SYNC_MAX_AST_AGE_SECONDS` | `int`   | `259200` | >= 0       | Maximum age (in seconds) for cached AST artifacts before forcing reanalysis (default: 3 days = 259200s) |

**How incremental sync works:**

1. **Detect changes**: Compare working directory against base ref (default: `HEAD`)
2. **Calculate change ratio**: `changed_files / total_ts_tsx_files`
3. **Decide strategy**:
   - If ratio ≤ threshold → incremental update (fast)
   - If ratio > threshold → full rescan (more accurate)
4. **Check AST staleness**: If AST artifacts are older than `sync_max_ast_age_seconds`, force graph rebuild

**Examples:**

```env
# More aggressive incremental updates (fallback at 15% changed files)
AICA_SYNC_FALLBACK_THRESHOLD=0.15

# Disable AST age check (always trust cached AST data)
AICA_SYNC_MAX_AST_AGE_SECONDS=0

# More frequent AST invalidation (1 day = 86400 seconds)
AICA_SYNC_MAX_AST_AGE_SECONDS=86400
```

**Command-line overrides:**

```bash
# Force full rescan regardless of change ratio
aica sync-repo --full

# Override threshold for this run only
aica sync-repo --threshold 0.10

# Use different base ref (e.g., compare against main branch)
aica sync-repo --base main
```

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

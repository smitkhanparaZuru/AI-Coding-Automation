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

### Qdrant Vector Database

| Variable                       | Type        | Default                   | Description                                           |
| ------------------------------ | ----------- | ------------------------- | ----------------------------------------------------- |
| `AICA_QDRANT_URL`              | `str`       | `"http://localhost:6333"` | Qdrant server URL                                     |
| `AICA_QDRANT_API_KEY`          | `SecretStr` | `None`                    | Qdrant API key (optional, for cloud deployments)      |
| `AICA_QDRANT_COLLECTION_NAME`  | `str`       | `"aica-code"`             | Collection name for code embeddings                   |
| `AICA_QDRANT_VECTOR_DIMENSION` | `int`       | `None`                    | Vector dimension (auto-detected from embedding model) |
| `AICA_QDRANT_BATCH_SIZE`       | `int`       | `500`                     | Batch size for vector upsert operations               |

**Local Qdrant setup with Docker:**

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

**Configuration:**

```env
AICA_QDRANT_URL=http://localhost:6333
AICA_QDRANT_COLLECTION_NAME=aica-code
```

**Cloud/authenticated setup:**

```env
AICA_QDRANT_URL=https://xyz-example.aws.cloud.qdrant.io
AICA_QDRANT_API_KEY=your-api-key-here
```

---

## Embedding Provider Settings

### Provider Selection

| Variable                  | Type  | Default              | Description                                     |
| ------------------------- | ----- | -------------------- | ----------------------------------------------- |
| `AICA_EMBEDDING_PROVIDER` | `str` | `"ollama"`           | Embedding backend: `"ollama"` or `"openrouter"` |
| `AICA_EMBEDDING_MODEL`    | `str` | `"nomic-embed-text"` | Model name for embeddings                       |

### Batch & Retry Settings

| Variable                        | Type    | Default | Description                                 |
| ------------------------------- | ------- | ------- | ------------------------------------------- |
| `AICA_EMBEDDING_BATCH_SIZE`     | `int`   | `32`    | Number of chunks to embed per API call      |
| `AICA_EMBEDDING_TIMEOUT`        | `int`   | `60`    | Request timeout in seconds                  |
| `AICA_EMBEDDING_MAX_RETRIES`    | `int`   | `3`     | Max retry attempts for transient errors     |
| `AICA_EMBEDDING_RETRY_MIN_WAIT` | `float` | `1.0`   | Minimum exponential back-off wait (seconds) |
| `AICA_EMBEDDING_RETRY_MAX_WAIT` | `float` | `10.0`  | Maximum exponential back-off wait (seconds) |

### Ollama Embedding Settings

| Variable                         | Type  | Default                    | Description                        |
| -------------------------------- | ----- | -------------------------- | ---------------------------------- |
| `AICA_EMBEDDING_OLLAMA_BASE_URL` | `str` | `"http://localhost:11434"` | Ollama API base URL for embeddings |

**Recommended Ollama models:**

- `nomic-embed-text` — 384 dimensions, fast, good quality (default)
- `mxbai-embed-large` — 1024 dimensions, higher quality, slower
- `all-minilm` — 384 dimensions, lightweight

**Example configuration:**

```env
AICA_EMBEDDING_PROVIDER=ollama
AICA_EMBEDDING_MODEL=nomic-embed-text
AICA_EMBEDDING_OLLAMA_BASE_URL=http://localhost:11434
```

### OpenRouter Embedding Settings

| Variable                             | Type        | Default                          | Description                       |
| ------------------------------------ | ----------- | -------------------------------- | --------------------------------- |
| `AICA_EMBEDDING_OPENROUTER_API_KEY`  | `SecretStr` | `None`                           | OpenRouter API key — never logged |
| `AICA_EMBEDDING_OPENROUTER_BASE_URL` | `str`       | `"https://openrouter.ai/api/v1"` | OpenRouter API base URL           |

**Recommended OpenRouter models:**

- `openai/text-embedding-3-small` — 1536 dimensions, cost-effective
- `openai/text-embedding-3-large` — 3072 dimensions, highest quality
- `text-embedding-ada-002` — 1536 dimensions, legacy but stable

**Example configuration:**

```env
AICA_EMBEDDING_PROVIDER=openrouter
AICA_EMBEDDING_MODEL=openai/text-embedding-3-small
AICA_EMBEDDING_OPENROUTER_API_KEY=sk-or-v1-...
AICA_EMBEDDING_BATCH_SIZE=100
```

> **Cost optimization**: OpenRouter charges per token. Larger batch sizes reduce API overhead but may hit rate limits. Start with default (32) and increase if needed.

---

## Sync Behavior

These settings control incremental synchronization and automatic embedding updates.

| Variable                        | Type    | Default  | Constraint | Description                                                                                             |
| ------------------------------- | ------- | -------- | ---------- | ------------------------------------------------------------------------------------------------------- |
| `AICA_SYNC_FALLBACK_THRESHOLD`  | `float` | `0.20`   | 0.0 - 1.0  | Percentage of changed TypeScript/TSX files that triggers full rescan instead of incremental update      |
| `AICA_SYNC_MAX_AST_AGE_SECONDS` | `int`   | `259200` | >= 0       | Maximum age (in seconds) for cached AST artifacts before forcing reanalysis (default: 3 days = 259200s) |
| `AICA_SYNC_UPDATE_EMBEDDINGS`   | `bool`  | `true`   | -          | Whether to automatically update code embeddings during sync operations                                  |

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

# Disable automatic embedding updates during sync (manual indexing only)
AICA_SYNC_UPDATE_EMBEDDINGS=false
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
# .env — Ollama setup for LLM + Embeddings
AICA_LLM_PROVIDER=ollama
AICA_OLLAMA_MODEL=codellama

AICA_EMBEDDING_PROVIDER=ollama
AICA_EMBEDDING_MODEL=nomic-embed-text

AICA_QDRANT_URL=http://localhost:6333

AICA_LOG_LEVEL=INFO
AICA_DEBUG=false
```

### OpenRouter (cloud)

```env
# .env — OpenRouter setup for LLM + Embeddings
AICA_LLM_PROVIDER=openrouter
AICA_OPENROUTER_API_KEY=sk-or-v1-...
AICA_OPENROUTER_MODEL=openai/gpt-4o-mini

AICA_EMBEDDING_PROVIDER=openrouter
AICA_EMBEDDING_OPENROUTER_API_KEY=sk-or-v1-...
AICA_EMBEDDING_MODEL=openai/text-embedding-3-small

AICA_QDRANT_URL=http://localhost:6333

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

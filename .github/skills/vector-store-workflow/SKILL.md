---
name: vector-store-workflow
description: 'Complete workflow for working with AICA vector store and embedding system. Use when: setting up embeddings, configuring Qdrant, implementing chunking strategies, semantic code search, testing vector search, incremental embedding updates, adding embedding providers.'
argument-hint: 'Describe what to do (e.g., "set up Ollama embeddings", "implement custom chunker", "configure Qdrant search")'
---

# Vector Store & Embedding Workflow

Complete step-by-step guide for working with AICA's vector store and embedding system for semantic code search.

## When to Use

- Setting up embedding providers (Ollama or OpenRouter)
- Configuring Qdrant vector database
- Implementing custom chunking strategies for code entities
- Building semantic code search queries with filters
- Testing embedding generation and vector search
- Implementing incremental embedding updates for changed files
- Adding new embedding provider backends
- Troubleshooting embedding or search issues

## Prerequisites

- Understanding of vector embeddings and semantic search concepts
- Qdrant vector database running (local or cloud)
- LLM provider configured for embeddings (Ollama or OpenRouter account)
- Repository already scanned with AST extractors
- Familiarity with AICA's AST extractor output format

## Architecture Overview

AICA's vector store system transforms code into searchable embeddings:

```
Source Code
    ↓
AST Extractors (functions.json, components.json, types.json)
    ↓
Chunkers (chunk_functions, chunk_components, chunk_types)
    ↓
CodeChunk objects (with metadata)
    ↓
Embedding Provider (Ollama or OpenRouter)
    ↓
Qdrant Vector Store
    ↓
Semantic Search (with filters, re-ranking)
    ↓
Formatted Results (table, code, or LLM context)
```

**Key components:**

- `embedding_provider.py` - Pluggable embedding backends
- `factory.py` - Provider factory pattern
- `chunkers.py` - Code chunking strategies
- `qdrant_client.py` - Vector database operations
- `retriever.py` - Search, filtering, re-ranking
- `incremental_updater.py` - Update embeddings for changed files
- `schemas.py` - Data models for chunks and search

## Workflow Steps

### 1. Choose and Configure Embedding Provider

AICA supports two embedding providers via a factory pattern.

#### Option A: Ollama (Local, Free)

**Best for:** Development, testing, air-gapped environments, privacy

**Setup:**

```bash
# 1. Install Ollama
# https://ollama.ai/download

# 2. Pull an embedding model
ollama pull nomic-embed-text

# 3. Configure AICA
AICA_EMBEDDING_PROVIDER=ollama
AICA_OLLAMA_EMBEDDING_MODEL=nomic-embed-text
AICA_OLLAMA_BASE_URL=http://localhost:11434
```

**Provider features:**

- HTTP POST to `/api/embeddings` endpoint
- Auto-detects embedding dimension (768 for nomic-embed-text)
- Synchronous only (no streaming)
- Built-in retry with exponential backoff
- No API key required

#### Option B: OpenRouter (Cloud, Paid)

**Best for:** Production, access to multiple models, no local setup

**Setup:**

```bash
# 1. Get API key from https://openrouter.ai/

# 2. Configure AICA
AICA_EMBEDDING_PROVIDER=openrouter
AICA_OPENROUTER_API_KEY=sk-or-v1-...
AICA_OPENROUTER_EMBEDDING_MODEL=text-embedding-ada-002
AICA_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

**Provider features:**

- OpenAI-compatible API (POST `/embeddings`)
- Access to 10+ embedding models
- Automatic dimension detection via `/models` endpoint
- Authentication via `Authorization: Bearer` header
- Supports batch processing

#### Configuration Reference

All embedding settings use `AICA_EMBEDDING_*` prefix:

| Variable                     | Default  | Description                               |
| ---------------------------- | -------- | ----------------------------------------- |
| `AICA_EMBEDDING_PROVIDER`    | `ollama` | Provider name (ollama/openrouter)         |
| `AICA_EMBEDDING_BATCH_SIZE`  | `32`     | Batch size for embedding generation       |
| `AICA_EMBEDDING_TIMEOUT`     | `300`    | Request timeout in seconds                |
| `AICA_EMBEDDING_MAX_RETRIES` | `3`      | Max retry attempts                        |
| `AICA_EMBEDDING_RETRY_DELAY` | `2.0`    | Initial retry delay (exponential backoff) |

Provider-specific:

```bash
# Ollama
AICA_OLLAMA_EMBEDDING_MODEL=nomic-embed-text
AICA_OLLAMA_BASE_URL=http://localhost:11434

# OpenRouter
AICA_OPENROUTER_API_KEY=sk-or-v1-...
AICA_OPENROUTER_EMBEDDING_MODEL=text-embedding-ada-002
AICA_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

#### Using the Factory Pattern

```python
from aica.memory.vector_store.factory import EmbeddingProvider

# Factory auto-selects provider based on settings
provider = EmbeddingProvider()

# Generate single embedding
text = "def fetch_user(id: str) -> User:"
embedding = provider.embed(text)  # Returns list[float]

# Batch embeddings (more efficient)
texts = ["function1", "function2", "function3"]
embeddings = provider.embed_batch(texts)  # List[list[float]]

# Get embedding dimension
dimension = provider.dimension  # e.g., 768
```

**Error handling:**

```python
from aica.memory.vector_store.exceptions import (
    EmbeddingError,
    EmbeddingAuthError,
    EmbeddingConnectionError,
)

try:
    embedding = provider.embed(text)
except EmbeddingAuthError:
    # Invalid API key - never retried
    log.error("embedding.auth_failed")
except EmbeddingConnectionError:
    # Network failure - retried automatically
    log.error("embedding.connection_failed")
except EmbeddingError as e:
    # Generic error
    log.error("embedding.failed", error=str(e))
```

---

### 2. Configure Qdrant Vector Database

Qdrant stores and searches vector embeddings efficiently.

#### Installation

```bash
# Docker (recommended for development)
docker run -p 6333:6333 qdrant/qdrant

# Or use Qdrant Cloud
# https://cloud.qdrant.io/
```

#### Configuration

```bash
# Local Qdrant
AICA_QDRANT_URL=http://localhost:6333
AICA_QDRANT_COLLECTION_NAME=aica_code
AICA_QDRANT_API_KEY=  # Optional for local

# Qdrant Cloud
AICA_QDRANT_URL=https://xyz-example.qdrant.io
AICA_QDRANT_API_KEY=your-api-key
AICA_QDRANT_COLLECTION_NAME=aica_code
```

#### Using QdrantClient

```python
from pathlib import Path
from aica.config import get_settings
from aica.memory.vector_store.qdrant_client import QdrantClient
from aica.core.logging import get_logger

log = get_logger("embedding.setup")
settings = get_settings()

# Initialize client (lazy connection)
client = QdrantClient(
    url=settings.qdrant_url,
    api_key=settings.qdrant_api_key,
    collection_name=settings.qdrant_collection_name,
)

# Verify connectivity
try:
    client.connect()
    log.info("qdrant.connected", url=settings.qdrant_url)
except Exception as e:
    log.error("qdrant.connection_failed", error=str(e))
    raise

# Create collection (one-time setup)
from aica.memory.vector_store.factory import EmbeddingProvider

provider = EmbeddingProvider()
dimension = provider.dimension  # e.g., 768

client.create_collection(
    dimension=dimension,
    distance="Cosine",  # or "Euclid", "Dot"
)
log.info("qdrant.collection_created", dimension=dimension)

# Verify collection exists
collections = client.client.get_collections().collections
collection_names = [c.name for c in collections]
assert settings.qdrant_collection_name in collection_names
```

**Collection already exists handling:**

```python
from qdrant_client.http.exceptions import UnexpectedResponse

try:
    client.create_collection(dimension=768, distance="Cosine")
except UnexpectedResponse as e:
    if "already exists" in str(e).lower():
        log.info("qdrant.collection_exists")
    else:
        raise
```

---

### 3. Implement Chunking Strategies

Chunkers convert AST-extracted code entities into searchable `CodeChunk` objects.

#### Understanding CodeChunk Schema

```python
from dataclasses import dataclass

@dataclass
class CodeChunk:
    """Searchable code chunk with metadata."""
    id: str              # Unique: {file}::{name}::{line}
    text: str            # Source code + docstring
    file: str            # Relative path from repo root
    line: int            # Start line (1-indexed)
    chunk_type: str      # "function", "component", "type"
    name: str            # Entity name
    exported: bool       # Is exported?
    feature: str | None  # Inferred feature (e.g., "auth", "api")
    dependencies: list[str]  # Imported modules
    language: str        # "typescript"
    truncated: bool      # Was source truncated?

    # Entity-specific fields (optional)
    params: list[str] | None     # Function parameters
    props: list[str] | None      # Component props
    members: list[str] | None    # Type/interface members
    kind: str | None             # "function", "arrow", "class", etc.
    async_: bool | None          # Is async function?
```

#### Built-in Chunkers

##### A. chunk_functions()

Extracts function definitions with source code and docstrings.

```python
from pathlib import Path
import json
from aica.memory.vector_store.chunkers import chunk_functions

# Load AST extractor output
repo_path = Path("/path/to/repo")
ast_dir = repo_path / ".repo_intelligence" / "ast"

with open(ast_dir / "functions.json") as f:
    functions = json.load(f)

# Chunk functions
chunks = chunk_functions(functions, repo_path)

# Examine chunk
chunk = chunks[0]
print(f"ID: {chunk.id}")           # src/auth/login.ts::loginUser::42
print(f"Text: {chunk.text[:100]}") # function loginUser(email: str...
print(f"Type: {chunk.chunk_type}") # function
print(f"Params: {chunk.params}")   # ['email', 'password']
print(f"Async: {chunk.async_}")    # True
```

**Features:**

- Extracts up to 50 lines or 2000 characters
- Prioritizes docstrings (if found, extracts full docstring first)
- Sets `truncated=True` if source exceeds limits
- Infers feature from path (e.g., `src/auth/` → "auth")

##### B. chunk_components()

Extracts React components with JSX.

```python
from aica.memory.vector_store.chunkers import chunk_components

with open(ast_dir / "components.json") as f:
    components = json.load(f)

chunks = chunk_components(components, repo_path)

chunk = chunks[0]
print(f"Props: {chunk.props}")     # ['user', 'onClose']
print(f"Kind: {chunk.kind}")       # "function" or "arrow" or "class"
print(f"Feature: {chunk.feature}") # "dashboard" (from path)
```

**Features:**

- Extracts up to 60 lines (components often larger)
- Captures component props
- Marks exported components

##### C. chunk_types()

Extracts TypeScript types and interfaces.

```python
from aica.memory.vector_store.chunkers import chunk_types

with open(ast_dir / "types.json") as f:
    types = json.load(f)

chunks = chunk_types(types, repo_path)

chunk = chunks[0]
print(f"Members: {chunk.members}")  # ['id', 'name', 'email', 'role']
print(f"Kind: {chunk.kind}")        # "interface" or "type"
```

**Features:**

- Extracts up to 30 lines (types usually compact)
- Captures interface/type members
- Handles both interfaces and type aliases

#### Orchestrating All Chunkers

```python
from aica.memory.vector_store.chunkers import create_code_chunks

# Load all AST JSONs and create chunks
chunks = create_code_chunks(repo_path)

# Returns deduplicated list of CodeChunk objects
print(f"Total chunks: {len(chunks)}")

# Group by type
by_type = {}
for chunk in chunks:
    by_type.setdefault(chunk.chunk_type, []).append(chunk)

print(f"Functions: {len(by_type['function'])}")
print(f"Components: {len(by_type['component'])}")
print(f"Types: {len(by_type['type'])}")
```

**Features:**

- Loads all AST JSONs (functions, components, types)
- Applies all chunkers
- Deduplicates by chunk ID
- Enriches with dependency data (imports)
- Infers features from file paths

#### Implementing Custom Chunkers

Follow the established pattern for consistency:

```python
from __future__ import annotations

from pathlib import Path
from aica.core.logging import get_logger
from aica.memory.vector_store.chunkers import (
    extract_source_lines,
    infer_feature,
    truncate_text,
)
from aica.memory.vector_store.schemas import CodeChunk

log = get_logger("chunker.custom")


def chunk_custom_entities(
    entities: list[dict],
    repo_path: Path,
) -> list[CodeChunk]:
    """Chunk custom code entities from AST extractor output.

    Args:
        entities: List of entity dicts from AST extractor
        repo_path: Repository root path

    Returns:
        List of CodeChunk objects
    """
    chunks = []

    for entity in entities:
        file_path = entity["file"]
        name = entity["name"]
        line = entity["line"]

        # Extract source code
        source = extract_source_lines(
            repo_path / file_path,
            start_line=line,
            max_lines=40,
            max_chars=1500,
        )

        if not source:
            log.warning("chunker.empty_source", file=file_path, line=line)
            continue

        # Build chunk
        chunk = CodeChunk(
            id=f"{file_path}::{name}::{line}",
            text=source.text,
            file=file_path,
            line=line,
            chunk_type="custom_entity",
            name=name,
            exported=entity.get("exported", False),
            feature=infer_feature(file_path),
            dependencies=[],
            language="typescript",
            truncated=source.truncated,
            # Add custom fields as needed
            kind=entity.get("kind"),
        )

        chunks.append(chunk)

    log.info("chunker.completed", count=len(chunks))
    return chunks
```

**Key helpers:**

- `extract_source_lines(file, start_line, max_lines, max_chars)` - Read source with limits
- `infer_feature(file_path)` - Guess feature from path patterns
- `truncate_text(text, max_length)` - Truncate with indicator

---

### 4. Generate and Store Embeddings

Transform chunks into vector embeddings and store in Qdrant.

#### Full Indexing Workflow

```python
from pathlib import Path
from aica.memory.vector_store.factory import EmbeddingProvider
from aica.memory.vector_store.qdrant_client import QdrantClient
from aica.memory.vector_store.chunkers import create_code_chunks
from aica.core.logging import get_logger
from qdrant_client.models import PointStruct

log = get_logger("indexing")

def index_repository(repo_path: Path) -> dict:
    """Index entire repository for semantic search."""

    # 1. Create chunks from AST data
    log.info("indexing.chunking_started")
    chunks = create_code_chunks(repo_path)
    log.info("indexing.chunking_completed", count=len(chunks))

    # 2. Generate embeddings
    log.info("indexing.embedding_started")
    provider = EmbeddingProvider()
    texts = [chunk.text for chunk in chunks]
    embeddings = provider.embed_batch(texts)
    log.info("indexing.embedding_completed", count=len(embeddings))

    # 3. Prepare Qdrant points
    points = [
        PointStruct(
            id=chunk.id,
            vector=embedding,
            payload={
                "file": chunk.file,
                "line": chunk.line,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name,
                "exported": chunk.exported,
                "feature": chunk.feature,
                "dependencies": chunk.dependencies,
                "language": chunk.language,
                "truncated": chunk.truncated,
                "text": chunk.text,
                # Add entity-specific fields
                "params": chunk.params,
                "props": chunk.props,
                "members": chunk.members,
                "kind": chunk.kind,
                "async": chunk.async_,
            },
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]

    # 4. Upsert to Qdrant
    log.info("indexing.upload_started")
    client = QdrantClient()
    client.connect()
    client.upsert_vectors(points)
    log.info("indexing.upload_completed", count=len(points))

    return {
        "chunks": len(chunks),
        "embeddings": len(embeddings),
        "dimension": provider.dimension,
    }
```

#### Using CLI Command

```bash
# Index repository
aica index-embeddings --path /path/to/repo

# Force reindex (delete + recreate collection)
aica index-embeddings --path /path/to/repo --force

# Check status
aica embedding-status

# Clear all embeddings (destructive!)
aica clear-embeddings
```

---

### 5. Semantic Search with Filters

Search code using natural language queries with metadata filters.

#### Basic Search

```python
from aica.memory.vector_store.retriever import search_code
from aica.core.logging import get_logger

log = get_logger("search")

# Natural language query
results = search_code(
    query="authentication login functions",
    repo_path="/path/to/repo",
    limit=10,
)

# Examine results
for result in results.results:
    print(f"Score: {result.score:.3f}")
    print(f"File: {result.file}:{result.line}")
    print(f"Name: {result.name}")
    print(f"Type: {result.chunk_type}")
    print(f"Text: {result.text[:200]}")
    print("---")
```

#### Advanced Filtering

```python
from aica.memory.vector_store.schemas import SearchQuery

# Search with filters
query = SearchQuery(
    query="user authentication",
    limit=20,
    chunk_types=["function"],           # Only functions
    exported_only=True,                  # Only exported
    file_pattern="src/auth/**/*.ts",    # Glob pattern
    features=["auth", "security"],       # Specific features
    min_score=0.7,                       # Score threshold
)

results = search_code(
    query=query.query,
    repo_path="/path/to/repo",
    limit=query.limit,
    chunk_types=query.chunk_types,
    exported_only=query.exported_only,
    file_pattern=query.file_pattern,
    features=query.features,
    min_score=query.min_score,
)
```

**Available filters:**

| Parameter       | Type        | Description                              |
| --------------- | ----------- | ---------------------------------------- |
| `query`         | `str`       | Natural language search query            |
| `limit`         | `int`       | Max results (default: 10)                |
| `chunk_types`   | `list[str]` | Filter by type (function/component/type) |
| `exported_only` | `bool`      | Only exported entities                   |
| `file_pattern`  | `str`       | Glob pattern (e.g., `src/**/*.ts`)       |
| `features`      | `list[str]` | Filter by feature tags                   |
| `min_score`     | `float`     | Minimum similarity score (0.0-1.0)       |

#### Re-ranking Logic

AICA applies automatic re-ranking to boost relevance:

```python
# Base score from Qdrant
base_score = 0.75

# Boost exported entities (+0.05)
if chunk.exported:
    score += 0.05

# Boost entities with docstrings (+0.03)
if "\"\"\"" in chunk.text or "/**" in chunk.text:
    score += 0.03

# Boost same-feature matches (+0.04)
if query_feature and chunk.feature == query_feature:
    score += 0.04

# Cap at 1.0
final_score = min(score, 1.0)
```

#### Output Formats

```python
from aica.memory.vector_store.retriever import (
    format_search_results,
    build_context_from_results,
)

# Format 1: Rich CLI table (for display)
formatted = format_search_results(results, format="table")
print(formatted)  # Rich table with syntax highlighting

# Format 2: Code snippets only
formatted = format_search_results(results, format="code")
print(formatted)  # Just the code, no metadata

# Format 3: LLM context (for prompts)
context = build_context_from_results(
    results,
    max_length=8000,  # Character limit
    include_metadata=True,
)
print(context)
# Output:
# File: src/auth/login.ts:42
# Type: function
# Name: loginUser
# Exported: true
# Dependencies: bcrypt, jsonwebtoken
#
# async function loginUser(email: string, password: string) {
#   ...
# }
```

#### Using CLI Command

```bash
# Basic search
aica search-code "authentication functions"

# With filters
aica search-code "user login" \
  --type function \
  --exported \
  --file "src/auth/**" \
  --limit 20

# Different output formats
aica search-code "components" --format table
aica search-code "components" --format code
aica search-code "components" --format context
```

---

### 6. Incremental Embedding Updates

Update embeddings when files change without full reindex.

#### Understanding the Update Process

```
Changed Files Detected (via git or hash comparison)
    ↓
Expand to Affected Files (detect importers + callers)
    ↓
Delete Old Embeddings (Qdrant filter: file IN [affected])
    ↓
Re-chunk Affected Files (filter AST JSONs)
    ↓
Generate New Embeddings (batch processing)
    ↓
Upsert to Qdrant
```

#### Using the Incremental Updater

```python
from pathlib import Path
from aica.memory.vector_store.incremental_updater import (
    update_embeddings_for_files,
)
from aica.core.logging import get_logger

log = get_logger("incremental_update")

# Files changed/deleted (from git or hash comparison)
changed_files = [
    "src/auth/login.ts",
    "src/auth/register.ts",
]
deleted_files = [
    "src/auth/old_session.ts",
]

# Update embeddings
summary = update_embeddings_for_files(
    repo_path=Path("/path/to/repo"),
    changed_files=changed_files,
    deleted_files=deleted_files,
)

# Examine summary
log.info(
    "update.completed",
    affected_files=len(summary.affected_files),
    deleted_count=summary.deleted_count,
    added_count=summary.added_count,
    duration_seconds=summary.duration_seconds,
)
```

**What it does:**

1. **Expands affected files** using `detect_all_affected_files()`:
   - Files that import changed files
   - Files whose functions are called by changed files
2. **Deletes old embeddings** for all affected files

3. **Re-chunks affected files** by filtering AST JSONs

4. **Generates new embeddings** in batches

5. **Upserts to Qdrant** atomically

**EmbeddingUpdateSummary fields:**

```python
@dataclass
class EmbeddingUpdateSummary:
    affected_files: list[str]  # All files re-indexed
    deleted_count: int         # Vectors deleted
    added_count: int           # Vectors added
    duration_seconds: float    # Total time
```

#### Integration with Sync System

The sync orchestrator automatically updates embeddings when enabled:

```bash
# Enable embedding updates in sync
AICA_SYNC_UPDATE_EMBEDDINGS=true

# Run sync (automatically updates embeddings)
aica sync-repo --path /path/to/repo
```

**Sync workflow:**

```python
from aica.repo_intelligence.sync.orchestrator import sync_repository

result = sync_repository(
    repo_path=Path("/path/to/repo"),
    base_ref="HEAD",
)

# Check if embeddings were updated
if result.embedding_summary:
    print(f"Embeddings updated: {result.embedding_summary.added_count}")
else:
    print("Embedding updates disabled")
```

---

## Common Patterns

### Pattern 1: Conditional Embedding Provider

Use different providers for dev vs production:

```python
from aica.config import get_settings
from aica.memory.vector_store.factory import EmbeddingProvider

settings = get_settings()

if settings.environment == "development":
    # Use local Ollama
    settings.embedding_provider = "ollama"
else:
    # Use cloud OpenRouter
    settings.embedding_provider = "openrouter"

provider = EmbeddingProvider()
```

### Pattern 2: Progressive Indexing

Index incrementally to avoid memory issues:

```python
from aica.memory.vector_store.chunkers import (
    chunk_functions,
    chunk_components,
    chunk_types,
)

def index_progressively(repo_path: Path) -> None:
    """Index in stages to manage memory."""
    client = QdrantClient()
    provider = EmbeddingProvider()

    # Stage 1: Functions
    functions = json.loads((repo_path / ".repo_intelligence/ast/functions.json").read_text())
    chunks = chunk_functions(functions, repo_path)
    embeddings = provider.embed_batch([c.text for c in chunks])
    client.upsert_vectors(_to_points(chunks, embeddings))

    # Stage 2: Components
    components = json.loads((repo_path / ".repo_intelligence/ast/components.json").read_text())
    chunks = chunk_components(components, repo_path)
    embeddings = provider.embed_batch([c.text for c in chunks])
    client.upsert_vectors(_to_points(chunks, embeddings))

    # Stage 3: Types
    types = json.loads((repo_path / ".repo_intelligence/ast/types.json").read_text())
    chunks = chunk_types(types, repo_path)
    embeddings = provider.embed_batch([c.text for c in chunks])
    client.upsert_vectors(_to_points(chunks, embeddings))
```

### Pattern 3: Feature-Scoped Search

Search within specific features only:

```python
def search_feature(feature_name: str, query: str) -> list:
    """Search within a specific feature."""
    results = search_code(
        query=query,
        repo_path="/path/to/repo",
        features=[feature_name],
        limit=20,
    )
    return results.results

# Usage
auth_results = search_feature("auth", "login validation")
api_results = search_feature("api", "rate limiting")
```

### Pattern 4: Hybrid Search (Keyword + Semantic)

Combine traditional grep with semantic search:

```python
from pathlib import Path
from aica.memory.vector_store.retriever import search_code
import subprocess

def hybrid_search(repo_path: Path, query: str) -> dict:
    """Combine grep and semantic search."""

    # Keyword search (exact matches)
    grep_result = subprocess.run(
        ["git", "grep", "-n", query],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    keyword_matches = grep_result.stdout.splitlines()

    # Semantic search (fuzzy matches)
    semantic_results = search_code(
        query=query,
        repo_path=repo_path,
        limit=15,
    )

    return {
        "keyword": keyword_matches,
        "semantic": semantic_results.results,
    }
```

### Pattern 5: Batch Embedding with Progress

Track progress for large batches:

```python
from aica.memory.vector_store.factory import EmbeddingProvider
from rich.progress import track

def embed_with_progress(texts: list[str]) -> list[list[float]]:
    """Generate embeddings with progress bar."""
    provider = EmbeddingProvider()
    batch_size = 32
    all_embeddings = []

    batches = [
        texts[i:i + batch_size]
        for i in range(0, len(texts), batch_size)
    ]

    for batch in track(batches, description="Embedding"):
        embeddings = provider.embed_batch(batch)
        all_embeddings.extend(embeddings)

    return all_embeddings
```

### Pattern 6: Smart Re-indexing

Only re-index if AST files are fresh:

```python
from pathlib import Path
import json
from datetime import datetime, timedelta

def should_reindex(repo_path: Path, max_age_hours: int = 24) -> bool:
    """Check if AST files are recent enough."""
    ast_dir = repo_path / ".repo_intelligence" / "ast"

    if not ast_dir.exists():
        return False

    # Check functions.json age
    functions_file = ast_dir / "functions.json"
    if not functions_file.exists():
        return False

    file_age = datetime.now() - datetime.fromtimestamp(
        functions_file.stat().st_mtime
    )

    return file_age < timedelta(hours=max_age_hours)

# Usage
if should_reindex(repo_path):
    index_repository(repo_path)
else:
    print("AST files too old, run `aica scan-repo` first")
```

---

## Troubleshooting

### Problem: Embeddings fail with connection error

**Symptoms:** `EmbeddingConnectionError` when calling `embed()` or `embed_batch()`

**Solutions:**

1. **Check provider is running:**

   ```bash
   # For Ollama
   curl http://localhost:11434/api/embeddings -d '{"model":"nomic-embed-text","prompt":"test"}'

   # For OpenRouter
   curl https://openrouter.ai/api/v1/models -H "Authorization: Bearer YOUR_KEY"
   ```

2. **Verify base URL:**

   ```bash
   # Check environment variable
   echo $AICA_OLLAMA_BASE_URL
   echo $AICA_OPENROUTER_BASE_URL
   ```

3. **Check firewall/network:**
   ```bash
   # Ping the service
   ping localhost  # For Ollama
   ```

### Problem: Qdrant collection not found

**Symptoms:** `ValueError: Collection 'aica_code' does not exist`

**Solutions:**

1. **Create collection explicitly:**

   ```python
   from aica.memory.vector_store.qdrant_client import QdrantClient
   from aica.memory.vector_store.factory import EmbeddingProvider

   client = QdrantClient()
   provider = EmbeddingProvider()
   client.connect()
   client.create_collection(dimension=provider.dimension, distance="Cosine")
   ```

2. **Or use CLI to initialize:**
   ```bash
   aica index-embeddings --force  # Creates collection if missing
   ```

### Problem: Search returns irrelevant results

**Symptoms:** Low-quality matches, unrelated code chunks

**Solutions:**

1. **Use filters to narrow scope:**

   ```python
   results = search_code(
       query="user login",
       chunk_types=["function"],      # Only functions
       exported_only=True,             # Only exported
       file_pattern="src/auth/**",    # Specific directory
       min_score=0.6,                  # Higher threshold
   )
   ```

2. **Improve query specificity:**

   ```python
   # ❌ Vague
   search_code("validate")

   # ✅ Specific
   search_code("email validation with regex pattern")
   ```

3. **Re-rank manually:**

   ```python
   results = search_code("login", limit=50)

   # Custom re-ranking
   filtered = [
       r for r in results.results
       if r.score > 0.7 and "password" in r.text.lower()
   ]
   ```

### Problem: Incremental update misses dependencies

**Symptoms:** Changed file indexed, but importing files out of date

**Solutions:**

1. **Force full reindex periodically:**

   ```bash
   # Weekly full reindex via cron
   0 0 * * 0 aica index-embeddings --force
   ```

2. **Check affected files expansion:**

   ```python
   from aica.memory.graph_store.cross_file_detector import detect_all_affected_files

   affected = detect_all_affected_files(
       changed_files,
       imports_data,
       functions_data,
       calls_data,
   )

   print(f"Changed: {len(changed_files)}")
   print(f"Affected: {len(affected)}")  # Should be larger
   ```

### Problem: Out of memory during indexing

**Symptoms:** Process killed, OOM errors

**Solutions:**

1. **Reduce batch size:**

   ```bash
   AICA_EMBEDDING_BATCH_SIZE=16  # Default is 32
   ```

2. **Index progressively** (see Pattern 2 above)

3. **Use streaming insertion:**
   ```python
   for i in range(0, len(points), 500):
       batch = points[i:i+500]
       client.upsert_vectors(batch)
       # Memory freed between batches
   ```

### Problem: Dimension mismatch error

**Symptoms:** `ValueError: Vector dimension mismatch`

**Solutions:**

1. **Delete and recreate collection:**

   ```bash
   aica clear-embeddings
   aica index-embeddings --force
   ```

2. **Or manually recreate:**

   ```python
   client = QdrantClient()
   client.connect()

   # Delete existing
   client.client.delete_collection(settings.qdrant_collection_name)

   # Recreate with correct dimension
   provider = EmbeddingProvider()
   client.create_collection(dimension=provider.dimension, distance="Cosine")
   ```

---

## Key Files Reference

| File                     | Purpose                                      |
| ------------------------ | -------------------------------------------- |
| `embedding_provider.py`  | Ollama/OpenRouter providers                  |
| `factory.py`             | Provider factory pattern                     |
| `chunkers.py`            | Code chunking strategies                     |
| `qdrant_client.py`       | Vector database wrapper                      |
| `retriever.py`           | Search, filtering, re-ranking                |
| `incremental_updater.py` | Update embeddings for changed files          |
| `schemas.py`             | Data models (CodeChunk, SearchQuery, etc.)   |
| `exceptions.py`          | Error types                                  |
| `interfaces/cli.py`      | CLI commands (search-code, index-embeddings) |
| `config/settings.py`     | Environment variables                        |

---

## Related Documentation

- [AST Extractor Workflow](../ast-extractor-workflow/SKILL.md) - Generate AST data for chunking
- [Detector Workflow](../detector-workflow/SKILL.md) - Scanner detector patterns
- [Pre-release Checklist](../pre-release-checklist/SKILL.md) - Quality validation
- [AICA Coding Guidelines](../../copilot-instructions.md) - Code conventions

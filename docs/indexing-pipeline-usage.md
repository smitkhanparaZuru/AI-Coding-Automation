# Indexing Pipeline Usage Example

## Basic Usage

```python
from pathlib import Path
from aica.memory.vector_store import index_codebase

# Index a repository
repo_path = Path("/path/to/your/repo")
summary = index_codebase(repo_path)

print(summary)
# Output: ✅ Indexed 1200/1200 code chunks in 45.2s (skipped: 0, failed: 0)
```

## Force Reindex

Delete existing collection and rebuild from scratch:

```python
summary = index_codebase(repo_path, force_reindex=True)
```

## Accessing Summary Details

```python
summary = index_codebase(repo_path)

print(f"Total chunks: {summary.total_chunks}")
print(f"Successfully embedded: {summary.embedded}")
print(f"Successfully stored: {summary.stored}")
print(f"Skipped (already exist): {summary.skipped}")
print(f"Failed: {summary.failed}")
print(f"Duration: {summary.duration_seconds:.1f}s")

# Check for errors
if summary.errors:
    print(f"\nErrors encountered:")
    for error in summary.errors[:5]:  # Show first 5 errors
        print(f"  - Chunk: {error['chunk_id']}")
        print(f"    Error: {error['error']}")
```

## Configuration

Set environment variables to configure embedding and vector store:

```bash
# Qdrant configuration
export AICA_QDRANT_URL="http://localhost:6333"
export AICA_QDRANT_COLLECTION_NAME="aica-code"
export AICA_QDRANT_VECTOR_DIMENSION=384  # Optional, auto-detected if not set

# Embedding provider configuration
export AICA_EMBEDDING_PROVIDER="ollama"  # or "openrouter"
export AICA_EMBEDDING_MODEL="nomic-embed-text"
export AICA_EMBEDDING_BATCH_SIZE=32
```

## Progress Tracking

The pipeline automatically shows a progress bar when running in an interactive terminal:

```
Indexing code chunks ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1200/1200 • 3:45 remaining • 5.3 chunks/s

✅ Indexed 1200/1200 code chunks in 45.2s (skipped: 0, failed: 0)
```

In non-interactive mode (CI/CD, scripts), structured logging is used instead.

## Error Recovery

The pipeline is resilient to failures:

- **Batch failures**: If embedding a batch fails, individual chunks are retried
- **Individual failures**: Failed chunks are collected in the summary with error details
- **Partial progress**: Successfully indexed chunks are stored even if later batches fail
- **Cleanup**: Database connections are always closed, even on failure

## What Gets Indexed

The pipeline indexes three types of code entities:

1. **Functions** — Function declarations (function, arrow, method)
2. **Components** — React/UI components
3. **Types** — TypeScript interfaces and type aliases

Each chunk includes:

- Source code text (up to 2000 characters)
- Rich metadata (file, line, name, exported status, dependencies)
- Computed fields (text length, has docstring, line count)
- Timestamped with indexed_at, repo_path, aica_version

## Next Steps

After indexing, use Sub-plan 4 (Semantic Retrieval) to search the indexed code:

```python
from aica.memory.vector_store import search_code

results = search_code("authentication logic", top_k=5)
for result in results:
    print(f"{result.chunk.metadata.name} (score: {result.score:.2f})")
```

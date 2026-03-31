# Code Embeddings CLI Usage

This document describes how to use the new CLI commands for semantic code search with Qdrant vector database.

## Prerequisites

1. **Qdrant running**: Start Qdrant locally (default: `http://localhost:6333`)

   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

2. **AST artifacts**: Run AST analysis first

   ```bash
   aica scan-repo
   aica index-code
   ```

3. **Configuration**: Set embedding provider

   ```bash
   # Option 1: Ollama (local)
   export AICA_EMBEDDING_PROVIDER=ollama
   export AICA_EMBEDDING_MODEL=nomic-embed-text

   # Option 2: OpenRouter (cloud)
   export AICA_EMBEDDING_PROVIDER=openrouter
   export AICA_EMBEDDING_MODEL=text-embedding-3-small
   export AICA_OPENROUTER_API_KEY=your-key-here
   ```

## Commands

### 1. index-embeddings — Generate and Store Embeddings

Generate embeddings for all code chunks and store them in Qdrant.

```bash
# Index current workspace
aica index-embeddings

# Force reindex (delete and recreate)
aica index-embeddings --force

# Index specific repository
aica index-embeddings --path /path/to/repo
```

**Output:**

```
╭─────────────────── Embedding Indexing Complete ────────────────────╮
│ Metric             │ Value                                          │
│ ────────────────── │ ────────────────────────────────────────────── │
│ Total chunks       │ 1247                                           │
│ Embedded           │ 1247                                           │
│ Stored in Qdrant   │ 1247                                           │
│ Skipped (exists)   │ 0                                              │
│ Failed             │ 0                                              │
│ Duration           │ 42.35s                                         │
╰────────────────────────────────────────────────────────────────────╯
```

### 2. search-code — Semantic Code Search

Search for code using natural language queries.

```bash
# Basic search
aica search-code "authentication middleware"

# Limit results
aica search-code "React hooks for data fetching" --limit 5

# Filter by chunk type
aica search-code "database queries" --type function

# Filter by file pattern
aica search-code "API routes" --file "src/app/**"

# Only exported entities
aica search-code "utility functions" --exported

# Different output formats
aica search-code "login logic" --format table    # Default: table view
aica search-code "login logic" --format code     # Syntax-highlighted code
aica search-code "login logic" --format context  # LLM-friendly format
```

**Output (table format):**

```
╭───────────────────────── Search Results ─────────────────────────╮
│ Rank │ Name           │ File                      │ Score │ Line │
│ ──── │ ────────────── │ ───────────────────────── │ ───── │ ──── │
│ 1    │ loginUser      │ services/auth.service.ts  │ 0.925 │ 45   │
│ 2    │ authenticate   │ middleware/auth.ts        │ 0.891 │ 12   │
│ 3    │ validateToken  │ utils/jwt.ts              │ 0.864 │ 89   │
╰──────────────────────────────────────────────────────────────────╯
```

### 3. embedding-status — Check Index Status

View embedding configuration and collection status.

```bash
aica embedding-status
```

**Output:**

```
╭──────────────────────── Configuration ────────────────────────╮
│ Setting             │ Value                                    │
│ ─────────────────── │ ──────────────────────────────────────── │
│ Qdrant URL          │ http://localhost:6333                    │
│ Collection          │ aica-code                                │
│ Embedding Provider  │ ollama                                   │
│ Embedding Model     │ nomic-embed-text                         │
│ Batch Size          │ 32                                       │
│ Vector Dimension    │ 384                                      │
╰────────────────────────────────────────────────────────────────╯

╭──────────────────────── Index Status ─────────────────────────╮
│ Metric              │ Value                                    │
│ ─────────────────── │ ──────────────────────────────────────── │
│ Collection Status   │ ✓ Exists                                 │
│ Action              │ Run aica search-code "query" to search   │
╰────────────────────────────────────────────────────────────────╯
```

### 4. clear-embeddings — Delete Collection

Delete the embedding collection from Qdrant.

```bash
# Interactive confirmation
aica clear-embeddings

# Skip confirmation
aica clear-embeddings --force
```

**Output:**

```
Delete collection 'aica-code'? This cannot be undone. [y/N]: y
✓ Collection 'aica-code' deleted successfully.
```

## Workflow Examples

### Initial Setup

```bash
# 1. Scan repository
aica scan-repo

# 2. Generate AST artifacts
aica index-code

# 3. Generate embeddings
aica index-embeddings

# 4. Check status
aica embedding-status
```

### Search Workflow

```bash
# Find authentication logic
aica search-code "user authentication and session management" --limit 3

# Find React components for forms
aica search-code "form input validation" --type component --exported

# Find database queries
aica search-code "SQL queries for user data" --file "src/db/**"
```

### Update Workflow

```bash
# After code changes, reindex
aica index-embeddings --force

# Or use incremental sync (if Sub-plan 6 implemented)
aica sync-repo  # Automatically updates embeddings
```

## Error Handling

### Qdrant Not Running

```bash
$ aica embedding-status
Qdrant connection failed: Connection refused
Ensure Qdrant is running at http://localhost:6333
```

**Solution:** Start Qdrant container

### Missing AST Files

```bash
$ aica index-embeddings
Error: No .repo_intelligence/ast/ directory found.
Run aica index-code first to generate AST files.
```

**Solution:** Run `aica index-code` first

### Collection Not Created

```bash
$ aica search-code "test"
Qdrant connection failed: Collection 'aica-code' does not exist
```

**Solution:** Run `aica index-embeddings` first

## Configuration Options

All commands respect these environment variables:

```bash
# Qdrant Configuration
export AICA_QDRANT_URL=http://localhost:6333
export AICA_QDRANT_COLLECTION_NAME=aica-code
export AICA_QDRANT_API_KEY=your-api-key  # Optional, for cloud Qdrant
export AICA_QDRANT_VECTOR_DIMENSION=384  # Auto-detected from model
export AICA_QDRANT_BATCH_SIZE=500

# Embedding Provider Configuration
export AICA_EMBEDDING_PROVIDER=ollama  # or openrouter
export AICA_EMBEDDING_MODEL=nomic-embed-text
export AICA_EMBEDDING_BATCH_SIZE=32

# For OpenRouter
export AICA_OPENROUTER_API_KEY=your-key
export AICA_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

## Performance Tips

1. **Batch size**: Increase for faster indexing (if API supports)

   ```bash
   export AICA_EMBEDDING_BATCH_SIZE=64
   ```

2. **Local embeddings**: Use Ollama for faster, offline embedding generation

3. **Incremental updates**: Use `aica sync-repo` instead of full reindex (when available)

4. **Filter early**: Use metadata filters to reduce search space
   ```bash
   aica search-code "query" --type function --exported --file "src/core/**"
   ```

## Integration with LLMs

Use the `--format context` option to generate LLM-friendly output:

```bash
# Generate context for LLM prompt
aica search-code "authentication implementation" --format context --limit 5 > context.txt

# Use in prompt
echo "Based on this code:\n$(cat context.txt)\n\nImplement a new auth feature..."
```

## Troubleshooting

| Issue              | Solution                                                 |
| ------------------ | -------------------------------------------------------- |
| Connection timeout | Increase timeout: `export AICA_QDRANT_TIMEOUT=120`       |
| Out of memory      | Reduce batch size: `export AICA_EMBEDDING_BATCH_SIZE=16` |
| Slow indexing      | Use local Ollama instead of API calls                    |
| Empty results      | Check collection exists: `aica embedding-status`         |
| Wrong results      | Try different query phrasing or filters                  |

## See Also

- [Phase 5 Plan](../.github/prompts/plan-phase5CodeEmbeddings.prompt.md) - Full implementation plan
- [Qdrant Documentation](https://qdrant.tech/documentation/) - Vector database docs
- [Ollama Embeddings](https://ollama.com/blog/embedding-models) - Local embedding models

# Embeddings Workflow Guide

Complete guide to using AICA's semantic code search with vector embeddings.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Workflow Steps](#workflow-steps)
- [Search Examples](#search-examples)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

---

## Overview

AICA's semantic search indexes your TypeScript/TSX codebase as vector embeddings, enabling natural language queries like "authentication middleware" or "React hooks for data fetching" that find relevant code based on meaning, not just keywords.

**Key benefits:**

- **Natural language queries** — search code by intent, not just exact names
- **Cross-file discovery** — find related code across your entire codebase
- **Contextual ranking** — results sorted by semantic similarity score
- **Filter support** — narrow results by type (function/component/hook), file pattern, or exported symbols only

---

## Quick Start

```bash
# 1. Start Qdrant vector database
docker run -d --name aica-qdrant -p 6333:6333 qdrant/qdrant

# 2. Configure embedding provider (example: Ollama with nomic-embed-text)
export AICA_EMBEDDING_PROVIDER=ollama
export AICA_EMBEDDING_MODEL=nomic-embed-text

# 3. Make sure you have AST artifacts (from previous scan)
aica index-code

# 4. Index embeddings
aica index-embeddings

# 5. Search your code semantically
aica search-code "authentication logic"
```

---

## Prerequisites

### 1. Running Services

**Qdrant Vector Database** (required):

```bash
# Local Docker instance
docker run -d --name aica-qdrant \
  -p 6333:6333 -p 6334:6334 \
  qdrant/qdrant

# Verify it's running
curl http://localhost:6333/health
# Should return: {"title":"qdrant - vector search engine","version":"..."}
```

**Embedding Provider** (choose one):

**Option A: Ollama (local, free)**

```bash
# Install Ollama
ollama pull nomic-embed-text

# Configure AICA
export AICA_EMBEDDING_PROVIDER=ollama
export AICA_EMBEDDING_MODEL=nomic-embed-text
```

**Option B: OpenRouter (cloud, paid)**

```bash
# Get API key from https://openrouter.ai/keys

# Configure AICA
export AICA_EMBEDDING_PROVIDER=openrouter
export AICA_EMBEDDING_MODEL=openai/text-embedding-3-small
export AICA_EMBEDDING_OPENROUTER_API_KEY=sk-or-v1-...
```

### 2. AST Artifacts

Embeddings are generated from AST data, so you must run `aica index-code` first:

```bash
cd /path/to/your/nextjs-app
aica index-code
```

This creates `.repo_intelligence/ast/` files (imports.json, functions.json, exports.json, etc.).

---

## Workflow Steps

### Step 1: Index Code (AST Extraction)

Extract TypeScript/TSX code structure:

```bash
aica index-code --path /path/to/repo
```

**Output:**

- `.repo_intelligence/ast/imports.json`
- `.repo_intelligence/ast/functions.json`
- `.repo_intelligence/ast/exports.json`
- `.repo_intelligence/ast/components.json`
- `.repo_intelligence/ast/hooks.json`
- `.repo_intelligence/ast/types.json`
- `.repo_intelligence/ast/call_graph.json`

**Time:** ~30 seconds for 500 TypeScript files

---

### Step 2: Index Embeddings

Convert AST artifacts into vector embeddings:

```bash
aica index-embeddings --path /path/to/repo
```

**What happens:**

1. **Chunking:** AST data is split into meaningful chunks (functions, components, etc.)
2. **Embedding:** Each chunk is converted to a vector via your embedding model
3. **Storage:** Vectors are uploaded to Qdrant with metadata (file, type, exported, etc.)

**Output:**

```
╭─ Embedding Index Complete ──────────────────────╮
│ Files processed:     142                         │
│ Chunks created:      1,234                       │
│ Embeddings indexed:  1,234                       │
│ Collection:          aica-code                   │
│ Vector dimension:    384                         │
│ Duration:            2m 15s                      │
╰──────────────────────────────────────────────────╯
```

**Time:** ~2-3 minutes for 500 TypeScript files (depends on embedding provider)

**Force re-indexing:**

```bash
aica index-embeddings --force
```

---

### Step 3: Search Your Code

Run natural language queries:

```bash
aica search-code "authentication middleware"
```

**Output:**

```
╭─ Semantic Code Search Results ──────────────────────────────────────────╮
│ Query: authentication middleware                                         │
│ Results: 10 / 1,234                                                      │
│ Collection: aica-code                                                    │
╰──────────────────────────────────────────────────────────────────────────╯

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┓
┃ File                      ┃ Symbol          ┃ Type      ┃ Score ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━┩
│ src/middleware/auth.ts    │ authMiddleware  │ function  │ 0.92  │
│ src/lib/auth.ts           │ requireAuth     │ function  │ 0.87  │
│ src/app/api/auth/[...].ts │ AuthHandler     │ function  │ 0.84  │
│ src/hooks/useAuth.ts      │ useAuth         │ hook      │ 0.79  │
│ src/types/auth.ts         │ AuthUser        │ type      │ 0.76  │
└───────────────────────────┴─────────────────┴───────────┴───────┘
```

---

## Search Examples

### Basic Queries

```bash
# Find authentication-related code
aica search-code "authentication logic"

# Find data fetching patterns
aica search-code "fetch data from API"

# Find error handling
aica search-code "error handling and retry"
```

### Filtered Searches

**By type:**

```bash
# Only functions
aica search-code "data validation" --type function

# Only React components
aica search-code "form input" --type component

# Only React hooks
aica search-code "state management" --type hook

# Only TypeScript types
aica search-code "user interface" --type type
```

**By file pattern:**

```bash
# Only in src/app directory
aica search-code "API routes" --file "src/app/**"

# Only in components directory
aica search-code "button" --file "src/components/**"

# Specific subdirectory
aica search-code "auth logic" --file "src/features/auth/**"
```

**By export status:**

```bash
# Only exported symbols (public API)
aica search-code "utility functions" --exported

# Combine with type filter
aica search-code "helper functions" --type function --exported
```

**Custom result limit:**

```bash
# Get top 3 results
aica search-code "database query" --limit 3

# Get top 20 results
aica search-code "React components" --limit 20
```

### Output Formats

**Table format (default):**

```bash
aica search-code "authentication" --format table
```

**Code snippets:**

```bash
aica search-code "authentication" --format code
```

Output includes full code with syntax highlighting:

```typescript
// src/middleware/auth.ts
export async function authMiddleware(req: Request) {
  const token = req.headers.get('authorization')?.split(' ')[1];
  if (!token) throw new Error('No token provided');

  const decoded = await verifyToken(token);
  return decoded.userId;
}
```

**JSON format (for scripting):**

```bash
aica search-code "authentication" --format json > results.json
```

---

## Advanced Usage

### Check Embedding Status

Before searching, verify embeddings exist:

```bash
aica embedding-status
```

**Output:**

```
╭─ Embedding Index Status ─────────────────────────╮
│ Qdrant:         Connected ✓                      │
│ Collection:     aica-code                        │
│ Vectors:        1,234                            │
│ Files indexed:  142                              │
│ Last indexed:   2026-03-30 14:32:15              │
│ Model:          nomic-embed-text (384d)          │
│ Provider:       ollama                           │
╰──────────────────────────────────────────────────╯
```

### Clear Embeddings

Delete all embeddings (useful for re-indexing with different settings):

```bash
# With confirmation prompt
aica clear-embeddings

# Skip confirmation
aica clear-embeddings --force
```

### Incremental Sync

After code changes, sync embeddings incrementally:

```bash
aica sync-repo
```

**What it does:**

1. Detects changed TypeScript/TSX files via git
2. Re-extracts AST for changed files only
3. Updates embeddings for changed chunks (if `AICA_SYNC_UPDATE_EMBEDDINGS=true`)
4. Removes embeddings for deleted files

**Disable automatic embedding updates:**

```env
AICA_SYNC_UPDATE_EMBEDDINGS=false
```

Then manually re-index:

```bash
aica index-embeddings --force
```

---

## Troubleshooting

### Qdrant Not Running

**Error:** `Connection refused at http://localhost:6333`

**Solution:**

```bash
# Check if Qdrant is running
docker ps | grep qdrant

# If not, start it
docker run -d --name aica-qdrant -p 6333:6333 qdrant/qdrant

# Verify health
curl http://localhost:6333/health
```

### Embedding Provider Not Configured

**Error:** `Embedding provider not configured`

**Solution:**

```bash
# For Ollama
export AICA_EMBEDDING_PROVIDER=ollama
export AICA_EMBEDDING_MODEL=nomic-embed-text

# Pull model if needed
ollama pull nomic-embed-text

# For OpenRouter
export AICA_EMBEDDING_PROVIDER=openrouter
export AICA_EMBEDDING_MODEL=openai/text-embedding-3-small
export AICA_EMBEDDING_OPENROUTER_API_KEY=sk-or-v1-...
```

### No AST Artifacts Found

**Error:** `No AST artifacts found. Run 'aica index-code' first.`

**Solution:**

```bash
cd /path/to/your/repo
aica index-code
aica index-embeddings
```

### Slow Embedding Generation

**Issue:** Indexing takes too long

**Solutions:**

**Option 1: Use faster embedding model**

```bash
# Switch to lighter model
export AICA_EMBEDDING_MODEL=all-minilm  # Ollama
# or
export AICA_EMBEDDING_MODEL=openai/text-embedding-3-small  # OpenRouter
```

**Option 2: Increase batch size**

```bash
export AICA_EMBEDDING_BATCH_SIZE=100  # default: 32
```

**Option 3: Use cloud provider**

OpenRouter API is often faster than local Ollama for large codebases.

### Empty Search Results

**Issue:** `No results found`

**Possible causes:**

1. **Query too specific:** Try broader terms
2. **Type filter too narrow:** Remove `--type` flag or try different type
3. **File filter excludes matches:** Check `--file` glob pattern
4. **Embeddings not indexed:** Run `aica embedding-status` to verify

**Solutions:**

```bash
# Broader query
aica search-code "auth" instead of "JWT authentication middleware"

# Remove filters
aica search-code "auth"  # no --type or --file

# Check status
aica embedding-status

# Re-index if needed
aica index-embeddings --force
```

### Version Dimension Mismatch

**Error:** `Vector dimension mismatch: expected 384, got 1536`

**Cause:** Changed embedding model without clearing old vectors

**Solution:**

```bash
# Clear old embeddings
aica clear-embeddings --force

# Re-index with new model
aica index-embeddings
```

---

## Best Practices

1. **Index embeddings after major code changes**
   - Use `aica sync-repo` for small changes
   - Re-run `aica index-embeddings --force` after refactors or framework upgrades

2. **Use descriptive queries**
   - Good: "authentication middleware with JWT verification"
   - Bad: "auth"

3. **Combine filters for precision**
   - `aica search-code "API client" --type function --file "src/lib/**" --exported`

4. **Check embedding status regularly**
   - Run `aica embedding-status` to ensure index is up-to-date

5. **Choose the right embedding model**
   - **Fast & local:** `nomic-embed-text` (Ollama)
   - **High quality:** `openai/text-embedding-3-large` (OpenRouter)
   - **Balanced:** `openai/text-embedding-3-small` (OpenRouter)

6. **Monitor Qdrant disk usage**
   - Large codebases generate millions of vectors
   - Use `docker exec -it aica-qdrant du -sh /qdrant/storage`

---

## Configuration Reference

See [configuration.md](configuration.md) for complete settings reference:

- [Qdrant Vector Database Settings](configuration.md#qdrant-vector-database)
- [Embedding Provider Settings](configuration.md#embedding-provider-settings)
- [Sync Behavior Settings](configuration.md#sync-behavior)

---

## Next Steps

- **Tutorial:** [Semantic Code Search Tutorial](tutorials.md#tutorial-4-semantic-code-search-with-embeddings)
- **CLI Reference:** [Embedding Commands](cli.md#aica-index-embeddings)
- **Troubleshooting:** [Common Issues](troubleshooting.md)

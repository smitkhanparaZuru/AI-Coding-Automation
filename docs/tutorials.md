# AICA Tutorials

Step-by-step guides for common AICA workflows. Choose your path based on experience level and goals.

---

## Table of Contents

- [Tutorial 1: Quick Start (5 minutes)](#tutorial-1-quick-start-5-minutes)
- [Tutorial 2: Deep Dive — Analyzing a Next.js App (20 minutes)](#tutorial-2-deep-dive--analyzing-a-nextjs-app-20-minutes)
- [Tutorial 3: Cloud Setup — OpenRouter + Neo4j Aura (15 minutes)](#tutorial-3-cloud-setup--openrouter--neo4j-aura-15-minutes)
- [Tutorial 4: Semantic Code Search with Embeddings (15 minutes)](#tutorial-4-semantic-code-search-with-embeddings-15-minutes)

---

## Tutorial 1: Quick Start (5 minutes)

**Goal:** Scan a Next.js repository, extract AST data, build a dependency graph, and run your first query.

**Prerequisites:**

- Python 3.11+
- Docker (for Neo4j)
- A Next.js repository (or clone a sample)

---

### Step 1: Install AICA

```bash
cd AI-Coding-Automation
pip install -e ".[dev]"
```

Verify installation:

```bash
aica version
# aica 0.1.0
```

---

### Step 2: Start Neo4j

```bash
docker run --rm -d \
  --name aica-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/quickstart \
  neo4j:latest
```

Wait 10 seconds for Neo4j to start, then verify:

```bash
curl -I http://localhost:7474
# HTTP/1.1 200 OK
```

---

### Step 3: Configure AICA

Create `.env` in your AICA directory:

```env
# Local Ollama setup (optional for this tutorial)
AICA_LLM_PROVIDER=ollama
AICA_OLLAMA_MODEL=codellama

# Neo4j connection
AICA_NEO4J_URI=bolt://localhost:7687
AICA_NEO4J_USER=neo4j
AICA_NEO4J_PASSWORD=quickstart
AICA_NEO4J_DATABASE=neo4j

# Logging
AICA_LOG_LEVEL=INFO
AICA_DEBUG=false
```

---

### Step 4: Scan a Repository

```bash
# Navigate to a Next.js repo (or use your own)
cd /path/to/your/nextjs-app

# Run the scanner
aica scan-repo --verbose
```

**Expected output:**

- Framework detection table (Next.js, TypeScript, pnpm, etc.)
- Routes, components, services tables
- Summary: "17 artifacts written to .repo_intelligence/"

---

### Step 5: Extract AST Data

```bash
aica index-code
```

**Expected output:**

- Summary table with function count, imports, calls, hooks, components, types
- "7 AST artifacts written to .repo_intelligence/ast/"

---

### Step 6: Build the Graph

```bash
aica build-graph
```

**Expected output:**

- Node counts (Files, Functions, Components, Types, Hooks, Routes, Services, Stores)
- Edge counts (Import Edges, Call Edges, Hook Usage Edges)

---

### Step 7: Query the Graph

Open Neo4j Browser at [http://localhost:7474](http://localhost:7474)

**Login:**

- Username: `neo4j`
- Password: `quickstart`

**Run your first query:**

```cypher
// Find all routes in the app
MATCH (f:File)-[:HAS_ROUTE]->(r:Route)
RETURN r.route, r.type, r.methods, f.path
ORDER BY r.route
LIMIT 20
```

**Try another:**

```cypher
// Find components using useState
MATCH (comp:Component)-[:USES_HOOK]->(hook:Hook {name: "useState"})
RETURN comp.name, comp.file
ORDER BY comp.name
```

---

### Step 8: Explore

Try these queries from [neo4j-graph.md](neo4j-graph.md#sample-cypher-queries):

- Find circular dependencies
- Find high-degree functions (most called)
- Trace import chains

---

### Next Steps

- **Tutorial 2:** Deep dive into scanning, AST analysis, and advanced queries
- **Tutorial 3:** Set up cloud infrastructure (OpenRouter + Neo4j Aura)
- **[neo4j-graph.md](neo4j-graph.md):** Comprehensive Neo4j guide with 10+ query examples

---

## Tutorial 2: Deep Dive — Analyzing a Next.js App (20 minutes)

**Goal:** Perform a comprehensive codebase analysis using Ollama (local LLM) and explore all AICA features.

**Prerequisites:**

- Ollama installed ([ollama.com](https://ollama.com))
- Neo4j running (Docker or Desktop)
- A real-world Next.js repository

---

### Step 1: Set Up Ollama

Pull a code-focused model:

```bash
ollama pull codellama
# or
ollama pull qwen2.5-coder
```

Verify:

```bash
ollama list
# Should show codellama or qwen2.5-coder
```

---

### Step 2: Configure AICA for Ollama

Update `.env`:

```env
AICA_LLM_PROVIDER=ollama
AICA_OLLAMA_MODEL=codellama
AICA_OLLAMA_BASE_URL=http://localhost:11434

AICA_NEO4J_URI=bolt://localhost:7687
AICA_NEO4J_USER=neo4j
AICA_NEO4J_PASSWORD=your_password
AICA_NEO4J_DATABASE=neo4j

AICA_LOG_LEVEL=DEBUG  # Verbose logging for learning
```

---

### Step 3: Check AICA Status

```bash
aica status
```

**Expected output:**

- Version: 0.1.0
- LLM Provider: ollama
- Ollama Model: codellama
- Neo4j URI: bolt://localhost:7687
- Module status: all ✓ loaded

---

### Step 4: Deep Scan the Repository

```bash
cd /path/to/nextjs-app
aica scan-repo --verbose
```

**Study the output:**

1. **Framework Detection:**
   - Next.js version (e.g., 16.0)
   - App Router enabled
   - Package manager (pnpm, npm, yarn)

2. **Structure:**
   - Source directories (src/app, src/components, etc.)
   - Config files (tsconfig.json, next.config.ts, etc.)

3. **Routes:** (if --verbose)
   - All pages and API routes
   - Methods (GET, POST, PUT, DELETE)
   - Dynamic routes ([id], [...slug])

4. **Components:**
   - Component names and props
   - File locations

5. **Zustand Stores:**
   - Store modules (user, chat, settings, etc.)
   - Slices per store
   - Middleware (devtools, persist, immer)

6. **tRPC Routers:**
   - Tier (lambda, async, edge)
   - Router names
   - Procedure counts

7. **i18n:**
   - Source locale (e.g., zh-CN)
   - Target locales
   - Namespaces (chat, setting, auth, etc.)

8. **Auth:**
   - Providers (Clerk, NextAuth, Auth0, etc.)
   - Session strategy (JWT or database)
   - Protected routes

9. **Environment Variables:**
   - Categories (LLM, AUTH, DATABASE, S3, etc.)
   - Variable names (not values!)

---

### Step 5: Index Code with AST

```bash
aica index-code
```

**Study the output:**

- **Functions:** Total, exported, async
- **Imports:** External (npm), alias (@/), relative (../)
- **Call Graph:** How many functions call others
- **Hooks:** Custom hooks (useIsMobile, useQuery, etc.) + built-in (useState, useEffect)
- **Components:** React components with inferred props
- **Types:** TypeScript interfaces and type aliases

**Inspect the artifacts:**

```bash
ls -lh .repo_intelligence/ast/
# imports.json, functions.json, exports.json, call_graph.json,
# hooks.json, components.json, types.json
```

---

### Step 6: Build the Dependency Graph

```bash
aica build-graph
```

**Expected output:**

- Files: 200-500 (depending on repo size)
- Functions: 1,000-5,000
- Components: 50-200
- Types: 50-150
- Hooks: 10-30
- Routes: 20-100
- Services: 5-20
- Stores: 3-15

---

### Step 7: Advanced Graph Queries

Open Neo4j Browser ([http://localhost:7474](http://localhost:7474)) and try these:

#### Find API route handlers

```cypher
MATCH (r:Route)-[:HAS_ROUTE]-(f:File)
WHERE r.type = 'api'
MATCH (f)-[:DEFINES]->(fn:Function)
WHERE fn.exported = true
RETURN r.route, fn.name, fn.kind, f.path
ORDER BY r.route
```

#### Find store usage patterns

```cypher
MATCH (s:Store)
MATCH (f:File)-[:HAS_STORE]->(s)
MATCH (f)-[:DEFINES]->(fn:Function)
RETURN s.store, fn.name, fn.params, fn.exported
ORDER BY s.store, fn.name
```

#### Trace import chain for a file

```cypher
MATCH path = (f:File {path: "src/app/api/chat/route.ts"})-[:IMPORTS*1..3]->(target)
RETURN path
```

#### Find components with most dependencies

```cypher
MATCH (c:Component)-[:DEFINES]-(f:File)
MATCH (f)-[:IMPORTS]->(dep)
WITH c, count(dep) AS dep_count
WHERE dep_count > 10
RETURN c.name, c.file, dep_count
ORDER BY dep_count DESC
```

#### Find hook usage by component

```cypher
MATCH (c:Component)-[:USES_HOOK]->(h:Hook)
RETURN c.name, collect(h.name) AS hooks, count(h) AS hook_count
ORDER BY hook_count DESC
```

---

### Step 8: Regenerate Summary

After manual edits to `.repo_intelligence/*.json` files:

```bash
aica summarize-repo
```

This updates `repo_summary.json` without re-scanning the entire codebase.

---

### Step 9: Plan a Task (LLM-Assisted)

```bash
aica plan-task "Add pagination to the user list API endpoint"
```

**Expected output:**

- 5-step plan: Analyse → Design → Implement → Verify → Document

> **Note:** In v0.1.0, plans are deterministic. LLM-driven planning arrives in Phase 2.

---

### Step 10: Execute a Command

```bash
aica run-task "npm run lint" --cwd /path/to/nextjs-app
```

**Expected output:**

- Exit code (0 = success)
- stdout panel with lint results
- stderr panel if any errors

---

### Next Steps

- **Extend AICA:** Add a custom detector (see [extending.md](extending.md))
- **Integrate with CI:** Run `aica scan-repo` in GitHub Actions
- **Export graph data:** Query Neo4j and export to JSON/CSV for analysis

---

## Tutorial 3: Cloud Setup — OpenRouter + Neo4j Aura (15 minutes)

**Goal:** Configure AICA for cloud-based LLM inference (OpenRouter) and cloud graph database (Neo4j Aura).

**Use case:** No local GPU, remote team, production deployment.

---

### Step 1: Get OpenRouter API Key

1. Visit [openrouter.ai](https://openrouter.ai)
2. Sign up or log in
3. Navigate to **Keys** → **Create Key**
4. Copy the key (starts with `sk-or-v1-...`)

---

### Step 2: Create Neo4j Aura Instance

1. Visit [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura/)
2. Sign up or log in
3. Click **Create Instance** → **Free Tier**
4. Wait 2-3 minutes for provisioning
5. **Copy the connection URI and password** (shown once!)

Example URI: `neo4j+s://xxxxx.databases.neo4j.io`

---

### Step 3: Configure AICA for Cloud

Create `.env` with cloud settings:

```env
# OpenRouter LLM
AICA_LLM_PROVIDER=openrouter
AICA_OPENROUTER_API_KEY=sk-or-v1-...your-key...
AICA_OPENROUTER_MODEL=openai/gpt-4o-mini  # or anthropic/claude-3-haiku
AICA_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Neo4j Aura
AICA_NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
AICA_NEO4J_USER=neo4j
AICA_NEO4J_PASSWORD=your-generated-password
AICA_NEO4J_DATABASE=neo4j

# Workspace
AICA_WORKSPACE_DIR=.
AICA_REPO_PATH=.

# Logging
AICA_LOG_LEVEL=INFO
AICA_DEBUG=false
```

---

### Step 4: Verify Connection

```bash
aica status
```

**Check:**

- LLM Provider: `openrouter`
- OpenRouter Model: `openai/gpt-4o-mini`
- Neo4j URI: `neo4j+s://...` (note the `s` for secure)

---

### Step 5: Test LLM Provider

```bash
aica plan-task "Add user authentication with OAuth"
```

**Expected output:**

- 5-step plan generated via OpenRouter LLM

> **Note:** OpenRouter charges per token. Check [openrouter.ai/models](https://openrouter.ai/models) for pricing.

---

### Step 6: Scan and Build Graph

```bash
cd /path/to/your/repo
aica scan-repo
aica index-code
aica build-graph
```

**Note:** Graph building may be slower over the internet (Aura) vs. local Docker. Expect 2-3x longer build times for large repos.

---

### Step 7: Access Neo4j Aura Browser

1. Go to [aura.neo4j.io](https://aura.neo4j.io)
2. Click your instance → **Open Browser**
3. Log in with your password
4. Run queries:

```cypher
// Count all nodes by type
MATCH (n)
RETURN labels(n)[0] AS node_type, count(n) AS count
ORDER BY count DESC
```

```cypher
// Find most imported modules
MATCH (f:File)-[:IMPORTS]->(m:Module)
RETURN m.name, count(f) AS usage_count
ORDER BY usage_count DESC
LIMIT 10
```

---

### Step 8: Cost Optimization

**OpenRouter:**

- Use cheaper models for simple tasks: `openai/gpt-4o-mini`, `anthropic/claude-3-haiku`
- Monitor usage: [openrouter.ai/activity](https://openrouter.ai/activity)
- Set rate limits in OpenRouter dashboard

**Neo4j Aura:**

- Free tier: 50k nodes, 175k relationships (sufficient for small-medium repos)
- Upgrade to paid tier for larger repos or longer retention

---

### Step 9: CI/CD Integration

Add to `.github/workflows/aica-scan.yml`:

```yaml
name: AICA Code Analysis

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install AICA
        run: pip install git+https://github.com/your-org/AICA.git

      - name: Configure AICA
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
        run: |
          echo "AICA_LLM_PROVIDER=openrouter" >> .env
          echo "AICA_OPENROUTER_API_KEY=$OPENROUTER_API_KEY" >> .env
          echo "AICA_OPENROUTER_MODEL=openai/gpt-4o-mini" >> .env
          echo "AICA_NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io" >> .env
          echo "AICA_NEO4J_USER=neo4j" >> .env
          echo "AICA_NEO4J_PASSWORD=$NEO4J_PASSWORD" >> .env

      - name: Scan repository
        run: aica scan-repo

      - name: Index code
        run: aica index-code

      - name: Build graph
        run: aica build-graph

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: repo-intelligence
          path: .repo_intelligence/
```

---

### Step 10: Query from CI

Add a query script `scripts/analyze-deps.py`:

```python
from neo4j import GraphDatabase
import os

uri = os.getenv("AICA_NEO4J_URI")
user = os.getenv("AICA_NEO4J_USER")
password = os.getenv("AICA_NEO4J_PASSWORD")

with GraphDatabase.driver(uri, auth=(user, password)) as driver:
    with driver.session() as session:
        # Find circular dependencies
        result = session.run("""
            MATCH path = (f:File)-[:IMPORTS*2..5]->(f)
            RETURN [node IN nodes(path) | node.path] AS cycle
            LIMIT 10
        """)

        cycles = [record["cycle"] for record in result]

        if cycles:
            print("⚠️  Circular dependencies found:")
            for cycle in cycles:
                print(f"  → {' → '.join(cycle)}")
            exit(1)
        else:
            print("✅ No circular dependencies")
```

Run in CI:

```yaml
- name: Check for circular dependencies
  run: python scripts/analyze-deps.py
```

---

### Next Steps

- **Monitor costs:** Track OpenRouter and Neo4j Aura usage
- **Optimize queries:** Use indexes and query profiling (`PROFILE` prefix in Cypher)
- **Scale up:** Upgrade Neo4j Aura tier for larger repos
- **Automate:** Run AICA analysis on every PR and post results as comments

---

## Tutorial 4: Semantic Code Search with Embeddings (15 minutes)

**Goal:** Index your codebase with vector embeddings and perform semantic code search to find relevant implementations by intent, not just keywords.

**Prerequisites:**

- Completed Tutorial 1 or 2 (AST artifacts exist)
- Docker (for Qdrant)
- Ollama running (or OpenRouter API key)

---

### Step 1: Start Qdrant Vector Database

```bash
docker run --rm -d \
  --name aica-qdrant \
  -p 6333:6333 -p 6334:6334 \
  qdrant/qdrant
```

Verify Qdrant is running:

```bash
curl http://localhost:6333/health
# {"title":"qdrant - vector search engine","version":"..."}
```

---

### Step 2: Configure Embedding Provider

**Option A: Ollama (Local, Free)**

```bash
# Pull embedding model
ollama pull nomic-embed-text

# Add to .env
cat >> .env << EOF
# Embedding configuration
AICA_EMBEDDING_PROVIDER=ollama
AICA_EMBEDDING_MODEL=nomic-embed-text
AICA_QDRANT_URL=http://localhost:6333
EOF
```

**Option B: OpenRouter (Cloud, Paid)**

```bash
# Add to .env
cat >> .env << EOF
# Embedding configuration
AICA_EMBEDDING_PROVIDER=openrouter
AICA_EMBEDDING_MODEL=openai/text-embedding-3-small
AICA_EMBEDDING_OPENROUTER_API_KEY=sk-or-v1-your-key-here
AICA_QDRANT_URL=http://localhost:6333
EOF
```

---

### Step 3: Generate Code Embeddings

Navigate to your analyzed repository:

```bash
cd /path/to/your/nextjs-app

# Index the codebase (generates embeddings for all functions, components, types)
aica index-embeddings
```

**Expected output:**

```
╭─────────────────── Embedding Indexing Complete ────────────────────╮
│ Metric             │ Value                                          │
│ ────────────────── │ ────────────────────────────────────────────── │
│ Total chunks       │ 847                                            │
│ Embedded           │ 847                                            │
│ Stored in Qdrant   │ 847                                            │
│ Skipped (exists)   │ 0                                              │
│ Failed             │ 0                                              │
│ Duration           │ 28.43s                                         │
╰────────────────────────────────────────────────────────────────────╯
```

**What happened:**

- AST artifacts (functions.json, components.json, types.json) were chunked
- Each code chunk was embedded using your configured model
- Vectors were stored in Qdrant with rich metadata (file, line, type, exported status)

---

### Step 4: Semantic Search Basics

**Search by intent** (not exact keywords):

```bash
# Find authentication-related code
aica search-code "user login and authentication logic"
```

**Output:**

```
╭───────────────────────── Search Results ─────────────────────────╮
│ Rank │ Name           │ File                      │ Score │ Line │
│ ──── │ ────────────── │ ───────────────────────── │ ───── │ ──── │
│ 1    │ loginUser      │ services/auth.service.ts  │ 0.912 │ 45   │
│ 2    │ authenticate   │ middleware/auth.ts        │ 0.887 │ 12   │
│ 3    │ validateToken  │ utils/jwt.ts              │ 0.854 │ 89   │
╰──────────────────────────────────────────────────────────────────╯
```

---

### Step 5: Advanced Search with Filters

**Filter by entity type:**

```bash
# Only search in React components
aica search-code "form validation" --type component

# Only search in functions
aica search-code "database queries" --type function --limit 10
```

**Filter by file pattern:**

```bash
# Search only in API routes
aica search-code "error handling" --file "src/app/api/**"

# Search in specific feature
aica search-code "data fetching" --file "src/features/dashboard/**"
```

**Filter by exported entities only:**

```bash
# Find only exported utilities
aica search-code "string utilities" --exported
```

---

### Step 6: View Full Code Context

**Get syntax-highlighted code:**

```bash
aica search-code "React hooks for data fetching" --format code --limit 3
```

**Output:**

```
╭───────────────────── Result 1 (Score: 0.923) ─────────────────────╮
│ useUserData (hooks/useUserData.ts:12) — component                 │
╰────────────────────────────────────────────────────────────────────╯

export function useUserData(userId: string) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/users/${userId}`)
      .then(res => res.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [userId]);

  return { data, loading };
}
```

**Get LLM-friendly context:**

```bash
aica search-code "authentication flow" --format context > context.txt
```

This format is optimized for feeding to an LLM for code analysis or generation.

---

### Step 7: Check Index Status

View collection info and configuration:

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
```

---

### Step 8: Real-World Use Cases

**Use Case 1: Find Similar Implementations**

```bash
# You're implementing a new feature and want to see similar patterns
aica search-code "API endpoint with pagination and filtering" --limit 5
```

**Use Case 2: Locate Error Handling Patterns**

```bash
# Find all error handling implementations
aica search-code "try catch error handling with logging" --type function
```

**Use Case 3: Discover Reusable Components**

```bash
# Find modal/dialog components you can reuse
aica search-code "modal dialog popup" --type component --exported
```

**Use Case 4: Analyze Security Patterns**

```bash
# Find authentication and authorization checks
aica search-code "check user permissions and access control"
```

---

### Step 9: Incremental Updates (Automatic)

When you modify code and run sync, embeddings are automatically updated:

```bash
# Make changes to your code
vim src/auth.service.ts

# Run sync (automatically updates embeddings for changed files)
aica sync-repo
```

**Check what updated:**

The sync output will show:

```
─────────────────── Embedding Sync Summary ───────────────────
• Deleted: 3 chunks
• Created: 4 chunks
• Duration: 1.2s
```

---

### Step 10: Advanced — Programmatic Search

Use the Python API for custom workflows:

```python
from pathlib import Path
from aica.memory.vector_store import search_code, SearchQuery

# Search with filters
query = SearchQuery(
    query="database connection pooling",
    top_k=5,
    filters={
        "chunk_type": "function",
        "exported_only": True,
        "file_pattern": "src/db/**",
    }
)

response = search_code(query)

for result in response.results[:3]:
    print(f"{result.chunk.metadata.name} ({result.score:.3f})")
    print(f"  File: {result.chunk.metadata.file}:{result.chunk.metadata.line}")
    print(f"  Code: {result.chunk.text[:100]}...")
    print()
```

---

### Cleanup (Optional)

**Delete the embedding collection:**

```bash
aica clear-embeddings --force
```

**Stop services:**

```bash
docker stop aica-qdrant
docker stop aica-neo4j
```

---

### What You Learned

- ✅ Set up Qdrant vector database
- ✅ Configure embedding provider (Ollama or OpenRouter)
- ✅ Generate code embeddings with `index-embeddings`
- ✅ Perform semantic search with `search-code`
- ✅ Use filters (file pattern, type, exported only)
- ✅ View results in different formats (table, code, context)
- ✅ Check index status with `embedding-status`
- ✅ Understand automatic incremental updates via sync
- ✅ Use the Python API for programmatic searches

---

### Next Steps

- **Combine with Neo4j queries**: Use semantic search to find candidates, then query Neo4j for their dependencies
- **Build RAG pipelines**: Use `build_context_from_results()` to create LLM context
- **Explore different models**: Try `mxbai-embed-large` for better quality or `text-embedding-3-large` for highest accuracy
- **Custom workflows**: Write Python scripts that combine search with analysis

See the [Embeddings CLI Usage Guide](embeddings-cli-usage.md) for complete command reference.

---

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues and solutions.

---

## Additional Resources

- **[CLI Reference](cli.md)** — All commands and options
- **[Configuration Reference](configuration.md)** — All environment variables
- **[Neo4j Graph Guide](neo4j-graph.md)** — Comprehensive graph schema and query examples
- **[API Reference](api-reference.md)** — Programmatic usage
- **[Extending AICA](extending.md)** — Add custom agents, detectors, tools

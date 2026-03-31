# CLI Reference

AICA provides 13 commands via the `aica` entry point.

```bash
aica --help
```

---

## Global behaviour

- Settings are loaded once at startup from env vars / `.env` file.
- All output uses `rich` panels and tables for readability.
- Structured logs are written to stderr (stdout reserved for rich output).

---

## Commands

### `aica status`

Display the current AICA configuration and module load status.

```bash
aica status
```

**Output:**

- Version, app name, debug flag, log level, workspace directory
- Module status table: `core`, `repo_intelligence`, `memory`, `tools`, `execution`, `interfaces`, `config`

**Example:**

```
╭─ AICA Status ───────────────────────────────╮
│ Version     0.1.0                            │
│ App Name    AICA                             │
│ Debug       False                            │
│ Log Level   INFO                             │
│ Workspace   .                                │
╰──────────────────────────────────────────────╯
```

---

### `aica version`

Print the installed AICA version string.

```bash
aica version
# aica 0.1.0
```

---

### `aica scan-repo`

Deep-scan a repository. Runs all 17 detectors, writes all 16 intelligence files to `.repo_intelligence/`, and displays a summary table. Add `--verbose` to also render per-entity tables in the terminal.

```bash
aica scan-repo [--path PATH] [--verbose]
```

**Options:**

| Option      | Type   | Default           | Description                                                                                                                                                                          |
| ----------- | ------ | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--path`    | `Path` | current directory | Path to the repository root to scan                                                                                                                                                  |
| `--verbose` | flag   | off               | Render per-entity rich tables (framework, routes, components, services, database, packages, stores, tRPC, i18n, auth, server modules, agent runtime, env vars, hooks, scripts, libs) |

**Output files written to `<path>/.repo_intelligence/`:**

| File                  | Contents                                                         |
| --------------------- | ---------------------------------------------------------------- |
| `structure.json`      | Full merged scan result from all detectors                       |
| `routes.json`         | Route list (route, type, methods, file)                          |
| `components.json`     | Component list (name, props, file)                               |
| `services.json`       | Service list (service, exported functions, file)                 |
| `database.json`       | Database ORM list (orm, schema, models)                          |
| `packages.json`       | Categorised packages (framework, ui, database, auth, state)      |
| `stores.json`         | Zustand store modules (slices, middleware)                       |
| `trpc_routers.json`   | tRPC routers per tier (lambda/async/edge) with procedures        |
| `i18n.json`           | i18n config (source locale, target locales, namespaces)          |
| `auth.json`           | Auth setup (providers, session strategy, middleware matchers)    |
| `server_modules.json` | Server-side module inventory with exported symbols               |
| `agent_runtime.json`  | LLM provider capabilities + SSO provider list                    |
| `env_vars.json`       | Env vars categorised by type (LLM / AUTH / DATABASE / S3 / etc.) |
| `hooks.json`          | Custom React hooks with parameter names                          |
| `scripts.json`        | Automation scripts directory inventory                           |
| `libs.json`           | Integration libraries / SDK catalog                              |
| `repo_summary.json`   | High-level counts summary                                        |

**Summary table columns:** routes, components, services, database, stores, tRPC routers, tRPC procedures, i18n namespaces, auth providers, server modules, LLM providers, env vars total, hooks, scripts, libs.

**Examples:**

```bash
# Scan current directory
aica scan-repo

# Scan a specific repo
aica scan-repo --path /projects/my-app

# Scan with per-entity tables
aica scan-repo --path /projects/my-app --verbose
```

---

### `aica summarize-repo`

Regenerate `repo_summary.json` from **existing** `.repo_intelligence/` artifact files — no re-scan required. Useful after manually editing the JSON files or to refresh the summary without the overhead of a full scan.

```bash
aica summarize-repo [--path PATH]
```

**Options:**

| Option   | Type   | Default           | Description                                      |
| -------- | ------ | ----------------- | ------------------------------------------------ |
| `--path` | `Path` | current directory | Repository root containing `.repo_intelligence/` |

**Input files read:** all `.repo_intelligence/*.json` files — `structure.json`, `routes.json`, `components.json`, `services.json`, `database.json`, `packages.json`, `stores.json`, `trpc_routers.json`, `i18n.json`, `auth.json`, `server_modules.json`, `agent_runtime.json`, `env_vars.json`, `hooks.json`, `scripts.json`, `libs.json`

**Output:** Writes / overwrites `<path>/.repo_intelligence/repo_summary.json`

**Summary fields:**

| Field                   | Description                              |
| ----------------------- | ---------------------------------------- |
| `framework`             | Detected framework name                  |
| `language`              | Primary language                         |
| `routes_count`          | Number of routes                         |
| `components_count`      | Number of components                     |
| `services_count`        | Number of services                       |
| `database`              | ORM name or `null`                       |
| `db_models_count`       | Number of database models                |
| `stores_count`          | Number of Zustand store modules          |
| `trpc_routers_count`    | Number of tRPC router files              |
| `trpc_procedures_count` | Total tRPC procedures across all routers |
| `i18n_source_lang`      | Source locale code (e.g. `zh-CN`)        |
| `i18n_namespace_count`  | Number of i18n namespaces                |
| `auth_providers`        | List of detected auth provider names     |
| `server_modules_count`  | Number of server-side modules            |
| `ai_providers_count`    | Number of LLM / AI providers             |
| `sso_providers_count`   | Number of SSO providers                  |
| `hooks_count`           | Number of custom React hooks             |
| `scripts_count`         | Number of automation scripts             |
| `env_vars_total`        | Total environment variables found        |
| `libs_count`            | Number of integration libraries          |

**Example:**

```bash
aica summarize-repo --path /projects/my-app
```

---

### `aica build-graph`

Build a Neo4j dependency graph from AST and scanner artifacts. This command loads all AST JSONs (imports, functions, calls, hooks, components, types) and scanner JSONs (routes, services, stores) from `.repo_intelligence/` and writes them into a Neo4j graph database.

```bash
aica build-graph [--path PATH]
```

**Options:**

| Option   | Type   | Default           | Description                                                |
| -------- | ------ | ----------------- | ---------------------------------------------------------- |
| `--path` | `Path` | current directory | Repository root containing `.repo_intelligence/` artifacts |

**Prerequisites:**

1. Neo4j database running (Docker, Desktop, or Aura)
2. Connection configured via env vars: `AICA_NEO4J_URI`, `AICA_NEO4J_USER`, `AICA_NEO4J_PASSWORD`
3. Artifacts generated: `aica scan-repo` and `aica index-code` must be run first

**Graph Schema:**

| Node Types | Description                            |
| ---------- | -------------------------------------- |
| File       | Source files                           |
| Function   | Functions, arrows, methods             |
| Component  | React components                       |
| Hook       | React hooks (custom + built-in)        |
| Type       | TypeScript interfaces and type aliases |
| Module     | External npm modules                   |
| Route      | Next.js routes                         |
| Service    | Service modules                        |
| Store      | Zustand stores                         |

| Relationship Types | Description                            |
| ------------------ | -------------------------------------- |
| IMPORTS            | File imports another file or module    |
| DEFINES            | File defines a function/component/type |
| CALLS              | Function calls another function        |
| USES_HOOK          | Function/Component uses a React hook   |
| HAS_ROUTE          | File defines a route                   |
| HAS_STORE          | Directory contains a Zustand store     |
| BELONGS_TO         | Service belongs to a file              |
| EXPORTS            | File exports a symbol                  |

**Output:** Displays a summary table with node counts (Files, Functions, Components, Types, Hooks, Routes, Services, Stores) and edge counts (Import Edges, Call Edges, Hook Usage Edges).

**Note:** This command is **additive** — it adds to existing graph data. To start fresh, clear the database first via Neo4j Browser or Cypher:

```cypher
MATCH (n) DETACH DELETE n
```

**Examples:**

```bash
# Build graph for current directory
aica build-graph

# Build graph for a specific repository
aica build-graph --path /projects/my-nextjs-app
```

---

### `aica index-code`

Run full TypeScript/TSX **AST analysis** on all `.ts` and `.tsx` files using tree-sitter. Writes seven JSON files to `.repo_intelligence/ast/` — no LLM required.

```bash
aica index-code [--path PATH]
```

**Options:**

| Option   | Type   | Default              | Description                               |
| -------- | ------ | -------------------- | ----------------------------------------- |
| `--path` | `Path` | `AICA_WORKSPACE_DIR` | TypeScript/TSX repository root to analyse |

**Output files written to `<path>/.repo_intelligence/ast/`:**

| File              | Contents                                                |
| ----------------- | ------------------------------------------------------- |
| `imports.json`    | All import statements (kind, named, default, type-only) |
| `functions.json`  | Functions, arrows, methods (async, exported, params)    |
| `exports.json`    | Named, default, re-export, namespace-reexport forms     |
| `call_graph.json` | Per-file call graph (caller → callees, new expressions) |
| `hooks.json`      | React hook invocations (use\* pattern)                  |
| `components.json` | React component definitions with inferred props         |
| `types.json`      | TypeScript interface and type alias declarations        |

**Summary table columns:** functions, exported functions, imports (external/alias/relative), call relations, new expressions, exports (named/default/re-exports), hooks, components, types.

**Examples:**

```bash
# Index the current workspace
aica index-code

# Index a specific TypeScript/Next.js repository
aica index-code --path /projects/my-nextjs-app
```

---

### `aica sync-repo`

Incrementally sync repository changes and update scanner/AST/graph artifacts. This command detects changed files from git state, applies targeted updates, and automatically falls back to full sync when change volume exceeds thresholds.

```bash
aica sync-repo [--path PATH] [--base REF] [--full] [--threshold N] [--verbose]
```

**Options:**

| Option        | Type    | Default           | Description                                                      |
| ------------- | ------- | ----------------- | ---------------------------------------------------------------- |
| `--path`      | `Path`  | current directory | Repository root to sync                                          |
| `--base`      | `str`   | `HEAD`            | Base git ref used when working tree is clean                     |
| `--full`      | flag    | off               | Force full sync instead of incremental update                    |
| `--threshold` | `float` | configured value  | Override incremental fallback threshold, between `0.0` and `1.0` |
| `--verbose`   | flag    | off               | Render changed-file details in addition to the sync summary      |

**Behaviour:**

- Uses git diff/status to determine changed files
- Updates `.repo_intelligence/` artifacts incrementally where possible
- Can rebuild graph-related outputs when required by detected changes
- Exits gracefully when no changes are detected

**Examples:**

```bash
# Sync current repository changes
aica sync-repo

# Sync against main branch
aica sync-repo --base origin/main

# Force a full sync
aica sync-repo --full

# Show changed files and sync details
aica sync-repo --verbose
```

---

### `aica plan-task`

Generate a structured multi-step execution plan for a given coding task using `TaskPlanner`.

> **Note:** In v0.1.0 plans are deterministic (5 fixed steps). LLM-driven planning arrives in Phase 2.

```bash
aica plan-task TASK
```

**Arguments:**

| Argument | Type  | Description                              |
| -------- | ----- | ---------------------------------------- |
| `TASK`   | `str` | Free-text description of the coding task |

**Output:** Rich panel displaying the 5-step plan:

1. **Analyse** — understand requirements and context
2. **Design** — outline the implementation approach
3. **Implement** — write the code
4. **Verify** — test and validate the changes
5. **Document** — update documentation

**Examples:**

```bash
aica plan-task "Refactor the authentication module to use JWT"
aica plan-task "Add pagination to the /api/users endpoint"
aica plan-task "Migrate from class components to React hooks"
```

---

### `aica run-task`

Execute a shell command and display captured stdout and stderr in rich panels.

```bash
aica run-task COMMAND [--cwd CWD]
```

**Arguments:**

| Argument  | Type  | Description              |
| --------- | ----- | ------------------------ |
| `COMMAND` | `str` | Shell command to execute |

**Options:**

| Option  | Type  | Default | Description                       |
| ------- | ----- | ------- | --------------------------------- |
| `--cwd` | `str` | `None`  | Working directory for the command |

**Output:**

- Exit code (coloured green=success, red=failure)
- `stdout` panel (if any output)
- `stderr` panel (if any errors)

**Examples:**

```bash
# Run tests
aica run-task "pytest tests/ -v"

# Run tests in a specific project directory
aica run-task "pytest tests/ -v" --cwd /projects/my-app

# Lint code
aica run-task "ruff check aica/" --cwd /projects/aica

# Database migration
aica run-task "pnpm run db:migrate" --cwd /projects/my-nextjs-app

# Any shell command
aica run-task "git log --oneline -10" --cwd /projects/my-repo
```

---

### `aica index-embeddings`

Generate vector embeddings for semantic code search. Processes all TypeScript/TSX AST artifacts and indexes them in Qdrant for similarity search.

```bash
aica index-embeddings [--path PATH] [--force]
```

**Options:**

| Option    | Type   | Default           | Description                                        |
| --------- | ------ | ----------------- | -------------------------------------------------- |
| `--path`  | `Path` | current directory | Path to the repository root                        |
| `--force` | flag   | off               | Force re-indexing even if embeddings already exist |

**Prerequisites:**

- Qdrant running (Docker: `docker run -p 6333:6333 qdrant/qdrant`)
- AST artifacts exist (run `aica index-code` first)
- Embedding provider configured (OpenAI, Ollama, etc.)

**Output:**

- Progress bars for chunking and embedding
- Statistics: files processed, chunks created, embeddings indexed
- Success/failure status

**Examples:**

```bash
# Index current repository
aica index-embeddings

# Force re-index
aica index-embeddings --force

# Index specific repository
aica index-embeddings --path /path/to/repo
```

---

### `aica search-code`

Search your codebase semantically using natural language queries. Returns relevant code snippets ranked by similarity.

```bash
aica search-code QUERY [--type TYPE] [--file PATTERN] [--exported] [--format FORMAT] [--limit N]
```

**Arguments:**

| Argument | Type  | Required | Description                   |
| -------- | ----- | -------- | ----------------------------- |
| `QUERY`  | `str` | yes      | Natural language search query |

**Options:**

| Option       | Type  | Default | Description                                             |
| ------------ | ----- | ------- | ------------------------------------------------------- |
| `--type`     | `str` | all     | Filter by type: `function`, `component`, `hook`, `type` |
| `--file`     | `str` | all     | Filter by file pattern (glob): `src/app/**`             |
| `--exported` | flag  | off     | Only search exported symbols                            |
| `--format`   | `str` | `table` | Output format: `table`, `code`, `json`                  |
| `--limit`    | `int` | `10`    | Maximum number of results to return                     |

**Examples:**

```bash
# Basic semantic search
aica search-code "authentication middleware"

# Search for React hooks related to data fetching
aica search-code "React hooks for data fetching" --type function

# Find API routes in specific directory
aica search-code "API routes" --file "src/app/**" --exported

# Get code snippets for database queries
aica search-code "database queries" --format code --limit 3
```

**Output formats:**

- `table` — Rich table with file, symbol, type, score
- `code` — Full code snippets with syntax highlighting
- `json` — Machine-readable JSON array

---

### `aica embedding-status`

Display current embedding index status and statistics.

```bash
aica embedding-status [--path PATH]
```

**Options:**

| Option   | Type   | Default           | Description             |
| -------- | ------ | ----------------- | ----------------------- |
| `--path` | `Path` | current directory | Path to repository root |

**Output:**

- Qdrant connection status
- Collection name and vector count
- Indexed files count
- Last indexed timestamp
- Embedding model used
- Next steps if not indexed

**Examples:**

```bash
# Check status for current repository
aica embedding-status
```

---

### `aica clear-embeddings`

Delete all embeddings from the vector store for the current repository.

```bash
aica clear-embeddings [--path PATH] [--force]
```

**Options:**

| Option    | Type   | Default           | Description              |
| --------- | ------ | ----------------- | ------------------------ |
| `--path`  | `Path` | current directory | Path to repository root  |
| `--force` | flag   | off               | Skip confirmation prompt |

**Examples:**

```bash
# Clear with confirmation
aica clear-embeddings

# Clear without confirmation
aica clear-embeddings --force
```

**Warning:** This action is irreversible. Re-index with `aica index-embeddings` to restore.

---

## Output files reference

All scan commands write to `.repo_intelligence/` inside the target repository:

```
<repo>/.repo_intelligence/
├── structure.json        ← Full merged scan result (all 17 detectors)
├── routes.json           ← Route list
├── components.json       ← Component list
├── services.json         ← Service list
├── database.json         ← Database ORM list
├── packages.json         ← Categorised package catalog
├── stores.json           ← Zustand store modules and slices
├── trpc_routers.json     ← tRPC routers per tier with procedures
├── i18n.json             ← i18n config, locales, and namespaces
├── auth.json             ← Auth providers, session strategy, middleware
├── server_modules.json   ← Server-side module inventory
├── agent_runtime.json    ← LLM provider capabilities + SSO providers
├── env_vars.json         ← Environment variables by category
├── hooks.json            ← Custom React hook catalog
├── scripts.json          ← Automation scripts inventory
├── libs.json             ← Integration library catalog
└── repo_summary.json     ← High-level summary (counts)
```

Python code indexing writes to:

```
<workspace>/.aica/
└── index.json          ← Python AST index (files, classes, functions)
```

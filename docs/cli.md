# CLI Reference

AICA provides 7 commands via the `aica` entry point.

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

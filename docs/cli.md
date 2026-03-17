# CLI Reference

AICA provides 8 commands via the `aica` entry point.

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

Deep-scan a repository. Runs all 7 detectors, writes all intelligence files to `.repo_intelligence/`, and displays a summary table.

```bash
aica scan-repo [--path PATH]
```

**Options:**

| Option   | Type   | Default           | Description                         |
| -------- | ------ | ----------------- | ----------------------------------- |
| `--path` | `Path` | current directory | Path to the repository root to scan |

**Output files written to `<path>/.repo_intelligence/`:**

| File                | Contents                                                    |
| ------------------- | ----------------------------------------------------------- |
| `structure.json`    | Full merged scan result from all detectors                  |
| `routes.json`       | Route list (route, type, methods, file)                     |
| `components.json`   | Component list (name, props, file)                          |
| `services.json`     | Service list (service, exported functions, file)            |
| `database.json`     | Database ORM list (orm, schema, models)                     |
| `packages.json`     | Categorised packages (framework, ui, database, auth, state) |
| `repo_summary.json` | High-level counts summary                                   |

**Summary table columns:** routes count, components count, services count, database ORM.

**Examples:**

```bash
# Scan current directory
aica scan-repo

# Scan a specific repo
aica scan-repo --path /projects/my-app

# Scan and write outputs
aica scan-repo --path D:\repos\my-nextjs-app
```

---

### `aica scan-next`

Verbose deep-scan optimised for **Next.js App Router** repositories. Writes the same `.repo_intelligence/` files as `scan-repo` but renders rich per-entity tables in the terminal.

```bash
aica scan-next [--path PATH]
```

**Options:**

| Option   | Type   | Default           | Description                         |
| -------- | ------ | ----------------- | ----------------------------------- |
| `--path` | `Path` | current directory | Path to the Next.js repository root |

**Rich panels displayed:**

| Panel            | Fields shown                                                             |
| ---------------- | ------------------------------------------------------------------------ |
| Framework        | `framework`, `language`, `app_router`, `next_version`, `package_manager` |
| Source structure | Directory tree                                                           |
| Config files     | List of detected config files                                            |
| Routes           | `route`, `type`, `methods`, `file`                                       |
| Components       | `name`, `file`, `props`                                                  |
| Services         | `service`, `file`, `exported_functions`                                  |
| Database         | `orm`, `schema`, `models`                                                |
| Packages         | `ui`, `database`, `auth`, `state`                                        |

**Examples:**

```bash
# Scan a Next.js repo with verbose output
aica scan-next --path /projects/my-nextjs-app

# Scan current directory (must be a Next.js project)
aica scan-next
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

**Input files read:** `routes.json`, `components.json`, `services.json`, `database.json`, `structure.json`

**Output:** Writes / overwrites `<path>/.repo_intelligence/repo_summary.json`

**Summary fields:**

| Field              | Description             |
| ------------------ | ----------------------- |
| `framework`        | Detected framework name |
| `language`         | Primary language        |
| `routes_count`     | Number of routes        |
| `components_count` | Number of components    |
| `services_count`   | Number of services      |
| `database`         | ORM name or `null`      |

**Example:**

```bash
aica summarize-repo --path /projects/my-app
```

---

### `aica index-code`

Index Python source files in the target workspace and save a structured index to `.aica/index.json`. Uses Python AST parsing — no LLM required.

```bash
aica index-code [--path PATH]
```

**Options:**

| Option   | Type   | Default              | Description              |
| -------- | ------ | -------------------- | ------------------------ |
| `--path` | `Path` | `AICA_WORKSPACE_DIR` | Python codebase to index |

**Output:** `.aica/index.json` containing:

- File list
- Line counts
- Classes (name, methods, line numbers)
- Functions (name, line number)

**Summary table columns:** files count, total lines, classes count, functions count.

**Examples:**

```bash
# Index the current workspace
aica index-code

# Index a specific Python project
aica index-code --path /projects/my-python-lib
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
├── structure.json      ← Full merged scan result (all detectors)
├── routes.json         ← Route list
├── components.json     ← Component list
├── services.json       ← Service list
├── database.json       ← Database ORM list
├── packages.json       ← Categorised package catalog
└── repo_summary.json   ← High-level summary (counts)
```

Python code indexing writes to:

```
<workspace>/.aica/
└── index.json          ← Python AST index (files, classes, functions)
```

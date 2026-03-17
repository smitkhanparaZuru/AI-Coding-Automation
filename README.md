# AICA — AI Coding Automation Engine

A local, CLI-first AI coding automation engine built on Python 3.11+. AICA orchestrates AI agents to plan, analyze, and execute coding tasks against a local workspace, backed by your choice of LLM provider.

## Features

- **Dual LLM backend** — switch between [Ollama](https://ollama.com) (local) and [OpenRouter](https://openrouter.ai) (cloud) via a single env var
- **Pluggable provider facade** — `LLMProvider` factory with sync, async, streaming, and async-streaming APIs; exponential-backoff retries on transient errors
- **Modular agent architecture** — composable `BaseAgent` ABC dispatched by an `Orchestrator` registry
- **Task planner** — `TaskPlanner` generates structured multi-step execution plans (LLM-driven in Phase 2)
- **Repo intelligence** — 17 detectors deep-scan Next.js repos (routes, stores, tRPC, i18n, auth, env vars, and more); 7 TypeScript AST extractors (functions, imports, exports, calls, hooks, components, types) via tree-sitter
- **Execution runner** — safe subprocess wrapper (`ExecutionRunner`) with captured stdout/stderr and a `RunResult` return type
- **Pluggable memory** — `MemoryStore` ABC with an in-memory implementation; swap for a persistent backend without touching agent code
- **Extensible tool system** — grow automation capabilities by subclassing `BaseTool`
- **Rich CLI** — seven commands with beautiful `rich` panels via `typer`
- **Layered config** — env vars → `.env` file → defaults via Pydantic Settings v2; secrets masked in logs

## Requirements

- Python 3.11+
- pip or pipx

## Installation

### Development (editable)

```bash
pip install -e ".[dev]"
```

### Production

```bash
pip install .
```

## Configuration

Copy `.env.example` to `.env` and override any defaults:

```bash
cp .env.example .env
```

### Core settings

| Environment Variable | Default | Description                           |
| -------------------- | ------- | ------------------------------------- |
| `AICA_APP_NAME`      | `AICA`  | Application display name              |
| `AICA_DEBUG`         | `false` | Enable debug mode                     |
| `AICA_LOG_LEVEL`     | `INFO`  | Log level (`DEBUG`/`INFO`/`WARNING`…) |
| `AICA_WORKSPACE_DIR` | `.`     | Target workspace directory            |
| `AICA_REPO_PATH`     | `.`     | Repository root for analysis          |

### LLM settings

| Environment Variable       | Default                        | Description                                 |
| -------------------------- | ------------------------------ | ------------------------------------------- |
| `AICA_LLM_PROVIDER`        | `ollama`                       | Backend: `ollama` or `openrouter`           |
| `AICA_OLLAMA_BASE_URL`     | `http://localhost:11434`       | Ollama API base URL                         |
| `AICA_OLLAMA_MODEL`        | _(required for Ollama)_        | Model name, e.g. `llama3.2` or `codellama`  |
| `AICA_OPENROUTER_API_KEY`  | _(required for OpenRouter)_    | OpenRouter API key (stored as `SecretStr`)  |
| `AICA_OPENROUTER_MODEL`    | _(required for OpenRouter)_    | Model name, e.g. `openai/gpt-4o-mini`       |
| `AICA_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL                     |
| `AICA_LLM_TIMEOUT`         | `60`                           | Request timeout in seconds                  |
| `AICA_LLM_MAX_RETRIES`     | `3`                            | Max retry attempts on transient errors      |
| `AICA_LLM_RETRY_MIN_WAIT`  | `1.0`                          | Minimum exponential back-off wait (seconds) |
| `AICA_LLM_RETRY_MAX_WAIT`  | `10.0`                         | Maximum exponential back-off wait (seconds) |

Settings can also be passed via nested env vars using `__` as delimiter,
e.g. `AICA_LOG_LEVEL=DEBUG`.

### Using Ollama (local)

```bash
# Install and pull a model
ollama pull codellama

# Configure AICA
AICA_LLM_PROVIDER=ollama
AICA_OLLAMA_MODEL=codellama
```

### Using OpenRouter (cloud)

```bash
AICA_LLM_PROVIDER=openrouter
AICA_OPENROUTER_API_KEY=sk-or-...
AICA_OPENROUTER_MODEL=openai/gpt-4o-mini
```

## CLI Commands

```text
aica --help
```

| Command               | Description                                                                   |
| --------------------- | ----------------------------------------------------------------------------- |
| `status`              | Display current configuration and loaded modules                              |
| `version`             | Print the installed AICA version                                              |
| `scan-repo`           | Deep-scan a repo, write all 16 intelligence JSON files, and display a summary |
| `scan-repo --verbose` | Same scan, plus per-entity rich tables (routes, stores, auth, tRPC, etc.)     |
| `index-code`          | Run TypeScript/TSX AST analysis and write to `.repo_intelligence/ast/`        |
| `summarize-repo`      | Regenerate `repo_summary.json` from existing `.repo_intelligence/` artifacts  |
| `plan-task`           | Generate a structured multi-step execution plan for a task                    |
| `run-task`            | Execute a shell command and display captured stdout / stderr                  |

### Examples

```bash
# Show engine status and config
aica status

# Scan a repository and write all .repo_intelligence/ files
aica scan-repo --path /path/to/repo

# Verbose scan with per-entity rich tables (routes, components, stores, tRPC, etc.)
aica scan-repo --path /path/to/nextjs-repo --verbose

# Regenerate repo_summary.json from existing artifacts (no re-scan)
aica summarize-repo --path /path/to/repo

# Run TypeScript/TSX AST analysis on all source files
aica index-code --path /path/to/repo

# Generate an execution plan
aica plan-task "Refactor the authentication module to use JWT"

# Run a shell command and capture output
aica run-task "pytest tests/ -v" --cwd /path/to/project
```

## Project Structure

```
aica/
├── __about__.py           # Version
├── config/                # Pydantic Settings v2 (layered config)
├── core/
│   ├── agent.py           # BaseAgent ABC
│   ├── orchestrator.py    # Agent registry and dispatcher
│   ├── planner.py         # TaskPlanner — structured execution plans
│   ├── logging/
│   │   └── logger.py      # structlog setup (JSON prod / console debug)
│   └── llm/
│       ├── base.py        # BaseLLMProvider ABC
│       ├── factory.py     # LLMProvider facade (provider selection)
│       ├── ollama.py      # OllamaProvider
│       ├── openrouter.py  # OpenRouterProvider (with retry logic)
│       └── exceptions.py  # LLMError hierarchy
├── repo_intelligence/
│   ├── ast/
│   │   ├── parser.py      # tree-sitter TypeScript/TSX parser (cached Language instances)
│   │   ├── runner.py      # ASTExtractorRunner — walks .ts/.tsx files, runs all 7 extractors
│   │   ├── writer.py      # ASTWriter — writes JSON to .repo_intelligence/ast/
│   │   └── extractors/
│   │       ├── imports.py     # extract_imports   → per-file import statements
│   │       ├── functions.py   # extract_functions → functions, arrows, methods
│   │       ├── exports.py     # extract_exports   → named/default/re-export forms
│   │       ├── calls.py       # extract_calls + build_call_graph()
│   │       ├── hooks.py       # extract_hooks     → React use* call sites
│   │       ├── components.py  # extract_components → React component definitions
│   │       └── types.py       # extract_types     → interface and type alias decls
│   └── scanner/
│       ├── core.py        # RepositoryScanner — orchestrates all 17 detectors
│       ├── summarizer.py  # RepoSummaryGenerator — repo_summary.json
│       ├── writers.py     # OutputWriter — serialize dicts to .repo_intelligence/
│       └── detectors/
            ├── framework.py       # FrameworkDetector
            ├── structure.py       # StructureDetector
            ├── routes.py          # RouteDetector
            ├── components.py      # ComponentDetector
            ├── services.py        # ServiceDetector
            ├── database.py        # DatabaseDetector
            ├── packages.py        # PackageDetector
            ├── stores.py          # ZustandStoreDetector
            ├── trpc.py            # TRPCRouterDetector
            ├── i18n.py            # I18nDetector
            ├── auth.py            # AuthDetector
            ├── server_modules.py  # ServerModulesDetector
            ├── agent_runtime.py   # AgentRuntimeDetector
            ├── env_vars.py        # EnvVarsDetector
            ├── hooks.py           # HooksDetector
            ├── scripts.py         # ScriptsDetector
            └── libs.py            # LibsDetector
├── memory/
│   └── store.py           # MemoryStore ABC + InMemoryStore
├── tools/
│   └── base.py            # BaseTool ABC
├── execution/
│   ├── runner.py          # ExecutionRunner + RunResult
│   └── terminal/
│       └── runner.py      # TerminalRunner — timeout + cwd management
├── interfaces/
│   └── cli.py             # Typer CLI (7 commands)
tests/                     # pytest suite
```

## Development

```bash
# Lint
ruff check aica/

# Type check
mypy aica/

# Run tests
pytest tests/ -v

# Tests with coverage
pytest tests/ --cov=aica --cov-report=term-missing
```

## Roadmap

- **Phase 2** — LLM-driven task planning, async agent execution, vector store memory
- **Phase 3** — Multi-agent collaboration, GitHub Actions integration, web UI
- **Phase 3** — Vector memory backend, persistent sessions
- **Phase 4** — Web / API interface via FastAPI

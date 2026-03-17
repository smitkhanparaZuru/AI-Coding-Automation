# Plan: AI Coding Automation Engine — Phase 1 Foundation

## TL;DR
Bootstrap a local Python 3.11+ CLI-first AI coding automation engine. Single root package `aica/` containing seven subpackages (core, repo_intelligence, memory, tools, execution, interfaces, config). CLI via Typer with a `status` command, configuration via Pydantic Settings v2.

---

## File Tree (target state)

```
d:\ZURU\AI-Coding-Automation\
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── aica/
│   ├── __init__.py
│   ├── __about__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py         ← BaseAgent ABC
│   │   └── orchestrator.py  ← Orchestrator stub
│   ├── repo_intelligence/
│   │   ├── __init__.py
│   │   └── analyzer.py      ← RepoAnalyzer stub
│   ├── memory/
│   │   ├── __init__.py
│   │   └── store.py         ← MemoryStore ABC + InMemoryStore
│   ├── tools/
│   │   ├── __init__.py
│   │   └── base.py          ← BaseTool ABC
│   ├── execution/
│   │   ├── __init__.py
│   │   └── runner.py        ← ExecutionRunner stub
│   ├── interfaces/
│   │   ├── __init__.py
│   │   └── cli.py           ← Typer app + status command
│   └── config/
│       ├── __init__.py
│       └── settings.py      ← Pydantic BaseSettings
└── tests/
    ├── __init__.py
    └── test_cli.py          ← smoke test for status command
```

---

## Steps

### Phase A — Scaffold (no dependencies between steps, all parallel)
1. Create `pyproject.toml` — hatchling build backend, runtime deps (typer[all], pydantic-settings, rich, structlog, python-dotenv), dev deps (pytest, ruff, mypy), `[project.scripts] aica = "aica.interfaces.cli:app"`
2. Create `README.md` — project intro, install, usage section with `aica status`
3. Create `.env.example` and `.gitignore`
4. Create `aica/__init__.py` and `aica/__about__.py` (version = "0.1.0")

### Phase B — Config layer (depends on Phase A)
5. Create `aica/config/settings.py` — Pydantic `BaseSettings` with `model_config` (env_file=".env", env_nested_delimiter="__"), fields: `app_name`, `debug`, `log_level`, `workspace_dir`
6. Create `aica/config/__init__.py` — re-export `Settings`, `get_settings()` cached singleton

### Phase C — Core abstractions (depends on Phase B, parallel across modules)
7. `aica/core/agent.py` — `BaseAgent` ABC with `name`, `description`, abstract `run(task: str) -> str`
8. `aica/core/orchestrator.py` — `Orchestrator` that holds a registry of `BaseAgent` instances
9. `aica/memory/store.py` — `MemoryStore` ABC with `save/load/clear`; `InMemoryStore` concrete impl
10. `aica/tools/base.py` — `BaseTool` ABC with `name`, `description`, abstract `execute(**kwargs)`
11. `aica/repo_intelligence/analyzer.py` — `RepoAnalyzer` stub with `analyze(path: Path) -> dict`
12. `aica/execution/runner.py` — `ExecutionRunner` stub with `run(command: str) -> RunResult`

### Phase D — CLI interface (depends on Phase C)
13. `aica/interfaces/cli.py` — Typer `app`, `status` command that loads Settings and prints rich table of current config + loaded modules
14. All remaining `__init__.py` files with clean re-exports

### Phase E — Tests (depends on Phase D)
15. `tests/test_cli.py` — use `typer.testing.CliRunner` to invoke `status` and assert exit code 0

---

## Relevant Files to Create
- `pyproject.toml` — hatchling, scripts, tool config (ruff, mypy, pytest)
- `aica/config/settings.py` — layered Pydantic settings
- `aica/core/agent.py` — BaseAgent ABC
- `aica/interfaces/cli.py` — Typer app with `status` command
- `tests/test_cli.py` — CLI smoke test

---

## Verification
1. `pip install -e ".[dev]"` installs cleanly from pyproject.toml
2. `aica status` prints a rich status panel without errors
3. `pytest tests/` passes (exit 0)
4. `ruff check aica/` reports no lint errors

---

## Decisions
- Package name: `aica` (short, importable, maps to CLI command)
- Build backend: `hatchling` (modern, zero-config)
- Config: Pydantic Settings v2 (pydantic-settings) — env > .env file > defaults
- Logging: `rich` for CLI output; `structlog` wired in for structured logs in agents
- No async at this phase — keep sync-first, async can be added in Phase 2
- Layout: flat (aica/ at root, not src/ layout) — simpler for local dev install with `pip install -e .`

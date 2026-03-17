# AICA — AI Coding Automation Engine

Python 3.11+ CLI tool that orchestrates AI agents to plan, analyze, and execute coding tasks. Backed by Ollama (local) or OpenRouter (cloud).

## Build & Test

```bash
pip install -e ".[dev]"        # Development install (editable)
pip install .                   # Production install

ruff check aica/               # Lint
mypy aica/                     # Type check
pytest tests/ -v               # Run tests
pytest tests/ --cov=aica --cov-report=term-missing  # With coverage
```

Entry point: `aica` CLI → `aica.interfaces.cli:app`

## Architecture

```
aica/
  config/settings.py           # Pydantic v2 Settings, AICA_ prefix, .env support
  core/
    agent.py                   # BaseAgent ABC → name, description, run(task) -> str
    orchestrator.py            # Orchestrator → register/dispatch agents by name
    planner.py                 # TaskPlanner → 5-step structured plans (LLM-driven in Phase 2)
    llm/
      base.py                  # BaseLLMProvider ABC → 4 methods: generate/stream/async_generate/async_stream
      factory.py               # LLMProvider facade → selects backend from AICA_LLM_PROVIDER
      ollama.py                # OllamaProvider → POST /api/generate, NDJSON
      openrouter.py            # OpenRouterProvider → POST /chat/completions, SSE
      exceptions.py            # LLMError hierarchy → Connection/Auth/RateLimit/Timeout
    logging/logger.py          # structlog setup → JSON (prod) or console (debug)
  execution/
    runner.py                  # ExecutionRunner → subprocess.run shell=True, RunResult dataclass
    terminal/runner.py         # TerminalRunner → timeout + cwd management, run_command() helper
  interfaces/cli.py            # Typer CLI: status, version, scan-repo, index-code, plan-task, run-task
  memory/store.py              # MemoryStore ABC + InMemoryStore (dict-backed, swap for persistence)
  repo_intelligence/
    analyzer.py                # RepoAnalyzer → metadata (git, file count)
    indexer.py                 # CodeIndexer → AST parse Python → .aica/index.json
  tools/base.py                # BaseTool ABC → name, description, execute(**kwargs) -> Any
```

## Conventions

### Extending Core Abstractions

**New Agent:**

```python
from aica.core.agent import BaseAgent

class MyAgent(BaseAgent):
    name = "my-agent"
    description = "Does X"
    def run(self, task: str) -> str: ...

orchestrator.register(MyAgent())
orchestrator.run("my-agent", task)
```

**New LLM Provider:**

```python
from aica.core.llm.base import BaseLLMProvider

class MyProvider(BaseLLMProvider):
    # Implement all 4: generate, stream, async_generate, async_stream
    ...

LLMProvider.register("myprovider", MyProvider)
# Then set AICA_LLM_PROVIDER=myprovider
```

**New Tool:**

```python
from aica.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my-tool"
    description = "Does Y"
    def execute(self, **kwargs) -> Any: ...
```

### Logging

- Use `get_logger("module.submodule")` — never `print()` or `logging.getLogger()`
- Logger name format: `"llm.ollama"`, `"repo.indexer"`, `"cli"` etc.
- Never log sensitive data (API keys, secrets)

### Settings Access

- Always use `get_settings()` (cached via `@lru_cache`) — never instantiate `Settings()` directly
- Sensitive fields use `SecretStr`; call `.get_secret_value()` only when passing to HTTP clients

### Error Handling

- LLM errors: use `LLMConnectionError`, `LLMAuthError`, `LLMRateLimitError`, `LLMTimeoutError`
- Retry only transient errors (Connection, Timeout, RateLimit) — never retry `LLMAuthError`
- `ExecutionRunner.run()` uses `shell=True` intentionally (dev-environment subprocess wrapper)

### RunResult Pattern

All command execution returns `RunResult`: check `.success` (`returncode == 0`), `.stdout`, `.stderr`.

### Configuration

- All env vars use `AICA_` prefix (e.g. `AICA_LLM_PROVIDER`, `AICA_DEBUG`)
- Nested keys use `__` delimiter (e.g. `AICA_LOG_LEVEL`)
- Layer order: env vars → `.env` file → defaults

## Testing

- Tests live in `tests/`, mirror the `aica/` module structure
- Use `pytest` with standard fixtures — no custom test base class
- Mock external HTTP calls (Ollama/OpenRouter) — tests must not require live services
- `RunResult` is a dataclass; construct directly for assertions in terminal runner tests

# API Reference

Public classes and their method signatures for all core AICA modules.

---

## `aica.config.settings`

### `Settings`

Pydantic v2 `BaseSettings`. Environment prefix: `AICA_`. Do not instantiate directly.

```python
class Settings(BaseSettings):
    # Core
    app_name: str = "AICA"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    workspace_dir: Path = Path(".")
    repo_path: Path = Path(".")

    # LLM
    llm_provider: Literal["ollama", "openrouter"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout: int = 60
    llm_max_retries: int = 3
    llm_retry_min_wait: float = 1.0
    llm_retry_max_wait: float = 10.0

    # Database (future)
    vector_db_url: str = "http://localhost:8000"
    graph_db_url: str = "bolt://localhost:7687"
```

### `get_settings() -> Settings`

Returns the cached singleton `Settings` instance. Always use this instead of `Settings()`.

```python
from aica.config.settings import get_settings

settings = get_settings()
```

---

## `aica.core.llm.base`

### `BaseLLMProvider` _(ABC)_

```python
class BaseLLMProvider(ABC):
    model: str  # Model identifier string

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Synchronously generate a full completion for the given prompt."""

    @abstractmethod
    def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Synchronously stream completion tokens as they arrive."""

    @abstractmethod
    async def async_generate(self, prompt: str, **kwargs: Any) -> str:
        """Asynchronously generate a full completion."""

    @abstractmethod
    async def async_stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Asynchronously stream completion tokens."""
```

---

## `aica.core.llm.factory`

### `LLMProvider`

Facade that selects and wraps a `BaseLLMProvider` backend.

```python
class LLMProvider:
    def __init__(
        self,
        provider: str | None = None,   # Override AICA_LLM_PROVIDER
        model: str | None = None,      # Override model from settings
    ) -> None: ...

    @property
    def backend(self) -> BaseLLMProvider:
        """The underlying provider instance (read-only)."""

    def generate(self, prompt: str, **kwargs: Any) -> str: ...
    def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]: ...
    async def async_generate(self, prompt: str, **kwargs: Any) -> str: ...
    async def async_stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]: ...

    @classmethod
    def register(cls, name: str, provider_cls: type[BaseLLMProvider]) -> None:
        """Register a custom provider under the given name."""
```

**Built-in registry:**

| Name           | Class                |
| -------------- | -------------------- |
| `"ollama"`     | `OllamaProvider`     |
| `"openrouter"` | `OpenRouterProvider` |

---

## `aica.core.llm.exceptions`

```python
LLMError(Exception)                  # Base class for all LLM errors
├── LLMConnectionError(LLMError)     # Network/server failures — retried
├── LLMAuthError(LLMError)           # 401/403 — NEVER retried
├── LLMRateLimitError(LLMError)      # 429 — retried
└── LLMTimeoutError(LLMError)        # Request timeout — retried
```

---

## `aica.core.agent`

### `BaseAgent` _(ABC)_

```python
class BaseAgent(ABC):
    name: str          # Unique agent identifier (kebab-case)
    description: str   # Human-readable description (one sentence)

    @abstractmethod
    def run(self, task: str) -> str:
        """Execute the given task and return the result string."""
```

---

## `aica.core.orchestrator`

### `Orchestrator`

```python
class Orchestrator:
    def __init__(self) -> None:
        """Initialise with an empty agent registry."""

    def register(self, agent: BaseAgent) -> None:
        """Register an agent under its `name` attribute."""

    def get(self, name: str) -> BaseAgent | None:
        """Return the registered agent, or None if not found."""

    def run(self, name: str, task: str) -> str:
        """Dispatch `task` to the named agent.

        Raises:
            KeyError: If no agent with `name` is registered.
        """

    @property
    def agents(self) -> list[str]:
        """Names of all currently registered agents."""
```

---

## `aica.core.planner`

### `TaskPlanner`

```python
class TaskPlanner:
    def plan(self, task: str) -> dict:
        """Generate a structured execution plan for the given task.

        Returns:
            dict with keys:
                'task'   (str)   — original task input
                'status' (str)   — always 'planned' in v0.1.0
                'steps'  (list)  — list of step dicts, each with:
                    'step'        (int)  — 1-indexed step number
                    'name'        (str)  — step name
                    'description' (str)  — what to do in this step
        """
```

**Fixed steps (v0.1.0):**

| Step | Name      | Description                         |
| ---- | --------- | ----------------------------------- |
| 1    | Analyse   | Understand requirements and context |
| 2    | Design    | Outline the implementation approach |
| 3    | Implement | Write the code                      |
| 4    | Verify    | Test and validate the changes       |
| 5    | Document  | Update documentation                |

---

## `aica.execution.runner`

### `RunResult`

```python
@dataclass
class RunResult:
    command: str       # The shell command that was executed
    returncode: int    # Process exit code (0 = success)
    stdout: str        # Captured standard output (stripped)
    stderr: str        # Captured standard error (stripped)

    @property
    def success(self) -> bool:
        """True if returncode == 0."""
```

### `ExecutionRunner`

```python
class ExecutionRunner:
    def run(self, command: str, cwd: str | None = None) -> RunResult:
        """Execute a shell command synchronously.

        Uses shell=True (intentional for dev-environment subprocess wrapper).
        Always returns a RunResult — never raises on non-zero exit codes.

        Args:
            command: Shell command string to execute.
            cwd:     Working directory for the process.
        """
```

---

## `aica.execution.terminal.runner`

### `TerminalRunner`

```python
class TerminalRunner:
    def __init__(
        self,
        timeout: int = 60,
        cwd: str | None = None,
    ) -> None: ...

    def run(
        self,
        command: str,
        *,
        cwd: str | None = None,      # Overrides instance cwd if provided
        timeout: int | None = None,  # Overrides instance timeout if provided
    ) -> RunResult:
        """Execute command with timeout support.

        On timeout: returns RunResult(returncode=-1, stderr="<timeout message>")
        Logs truncated output (first 500 chars of stdout/stderr).
        """
```

### `run_command`

```python
def run_command(
    command: str,
    *,
    timeout: int = 60,
    cwd: str | None = None,
) -> RunResult:
    """Convenience wrapper around TerminalRunner().run()."""
```

---

## `aica.memory.store`

### `MemoryStore` _(ABC)_

```python
class MemoryStore(ABC):
    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Return value for `key`, or None if not found."""

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Store `value` under `key`, replacing any existing value."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the entry for `key`. No-op if key doesn't exist."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all entries."""

    @abstractmethod
    def keys(self) -> list[str]:
        """Return all stored keys."""
```

### `InMemoryStore`

```python
class InMemoryStore(MemoryStore):
    """Dict-backed in-memory implementation.
    Thread-safety: not guaranteed. Suitable for single-threaded dev/testing.
    Data is lost when the process exits.
    """
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
```

---

## `aica.tools.base`

### `BaseTool` _(ABC)_

```python
class BaseTool(ABC):
    name: str          # Unique tool identifier (kebab-case)
    description: str   # Human-readable description

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given keyword arguments."""
```

---

## `aica.repo_intelligence.scanner.core`

### `RepositoryScanner`

```python
class RepositoryScanner:
    def __init__(self) -> None:
        """Initialise with all 7 detectors."""

    def scan(self, repo_path: Path) -> dict:
        """Run all detectors against `repo_path` and return merged results.

        Returns dict containing:
            'repo_path'     (str)    — absolute repo path
            'framework'     (str)    — detected framework
            'language'      (str)    — primary language
            'app_router'    (bool)   — Next.js App Router detected
            'next_version'  (str)    — Next.js version string
            'package_manager' (str)  — npm|pnpm|yarn|bun
            'src_structure' (dict)   — directory map
            'config_files'  (list)   — config file paths
            'routes'        (list)   — route dicts
            'components'    (list)   — component dicts
            'services'      (list)   — service dicts
            'database'      (list)   — database dicts
            'packages'      (dict)   — categorised packages
        """
```

### `scan_repository`

```python
def scan_repository(repo_path: str) -> dict:
    """Convenience function: RepositoryScanner().scan(Path(repo_path))."""
```

---

## `aica.repo_intelligence.scanner.summarizer`

### `RepoSummaryGenerator`

```python
class RepoSummaryGenerator:
    def generate(self, repo_path: Path) -> dict:
        """Read existing .repo_intelligence/*.json files and write repo_summary.json.

        Returns summary dict:
            'framework'         (str)       — framework name
            'language'          (str)       — primary language
            'routes_count'      (int)       — number of routes
            'components_count'  (int)       — number of components
            'services_count'    (int)       — number of services
            'database'          (str|None)  — ORM name or None
        """

    @classmethod
    def from_scan_data(cls, scan_data: dict) -> dict:
        """Derive summary directly from in-memory scan result dict.
        No disk I/O — caller is responsible for persisting via OutputWriter.
        Returns same summary structure as generate().
        """
```

---

## `aica.repo_intelligence.scanner.writers`

### `OutputWriter`

```python
class OutputWriter:
    def write(self, repo_path: Path, scan_data: dict) -> None:
        """Serialize scan_data to .repo_intelligence/*.json files.

        Writes:
            .repo_intelligence/structure.json
            .repo_intelligence/routes.json
            .repo_intelligence/components.json
            .repo_intelligence/services.json
            .repo_intelligence/database.json
            .repo_intelligence/packages.json
        Creates the directory if it doesn't exist.
        """
```

---

## `aica.repo_intelligence.indexer`

### `CodeIndexer`

```python
class CodeIndexer:
    def index(self, workspace_path: Path) -> dict:
        """Parse Python source files under workspace_path using AST.

        Returns index dict:
            'files'     (list[str])  — relative file paths
            'lines'     (int)        — total line count
            'classes'   (list[dict]) — {name, file, methods, line}
            'functions' (list[dict]) — {name, file, line}

        Writes result to <workspace_path>/.aica/index.json.
        """
```

---

## `aica.core.logging.logger`

### `get_logger`

```python
def get_logger(name: str) -> structlog.BoundLogger:
    """Return a structlog bound logger for the given module name.

    Args:
        name: Dot-separated module path, e.g. 'llm.ollama', 'agent.review'.

    Returns:
        Configured BoundLogger. Output format:
        - JSON in production (AICA_DEBUG=false)
        - Human-readable console in debug mode (AICA_DEBUG=true)
    """
```

### `setup_logging`

```python
def setup_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """Configure structlog processors and output format.
    Called once at CLI startup via the global Typer callback.
    """
```

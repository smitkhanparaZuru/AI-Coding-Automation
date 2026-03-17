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
        """Initialise with all 17 detectors."""

    def scan(self, repo_path: Path) -> dict:
        """Run all detectors against `repo_path` and return merged results.

        Returns dict containing:
            'repo_path'        (str)   — absolute repo path
            'framework'        (str)   — detected framework
            'language'         (str)   — primary language
            'app_router'       (bool)  — Next.js App Router detected
            'next_version'     (str)   — Next.js version string
            'package_manager'  (str)   — npm|pnpm|yarn|bun
            'src_structure'    (dict)  — directory map {name: rel_path}
            'config_files'     (dict)  — {key: filename}
            'root_dirs'        (list)  — top-level directory names
            'has_src_prefix'   (bool)  — src/ prefix present
            'routes'           (list)  — route dicts
            'components'       (list)  — component dicts
            'services'         (list)  — service dicts
            'database'         (list)  — database dicts
            'packages'         (dict)  — categorised packages
            'stores'           (list)  — Zustand store dicts
            'trpc_routers'     (list)  — tRPC router dicts
            'i18n'             (dict)  — i18n configuration
            'auth'             (dict)  — auth configuration
            'server_modules'   (list)  — server module dicts
            'agent_runtime'    (dict)  — LLM and SSO providers
            'env_vars'         (dict)  — env var categories
            'hooks'            (list)  — custom hook dicts
            'scripts'          (list)  — automation script dicts
            'libs'             (list)  — library dicts
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

        Returns summary dict (same schema as from_scan_data).
        """

    @classmethod
    def from_scan_data(cls, scan_data: dict) -> dict:
        """Derive summary directly from in-memory scan result dict.
        No disk I/O — caller is responsible for persisting via OutputWriter.

        Returns:
            'framework'             (str)       — framework name
            'language'              (str)       — primary language
            'routes_count'          (int)       — number of routes
            'components_count'      (int)       — number of components
            'services_count'        (int)       — number of services
            'database'              (str|None)  — ORM name or None
            'db_models_count'       (int)       — number of DB models
            'stores_count'          (int)       — number of Zustand store modules
            'trpc_routers_count'    (int)       — number of tRPC router files
            'trpc_procedures_count' (int)       — total tRPC procedures
            'i18n_source_lang'      (str|None)  — source locale code
            'i18n_namespace_count'  (int)       — number of i18n namespaces
            'auth_providers'        (list[str]) — detected auth provider names
            'server_modules_count'  (int)       — number of server modules
            'ai_providers_count'    (int)       — number of LLM providers
            'sso_providers_count'   (int)       — number of SSO providers
            'hooks_count'           (int)       — number of custom React hooks
            'scripts_count'         (int)       — number of automation scripts
            'env_vars_total'        (int)       — total environment variables
            'libs_count'            (int)       — number of integration libraries
        """
```

---

## `aica.repo_intelligence.scanner.writers`

### `OutputWriter`

```python
class OutputWriter:
    def write(self, data: dict | list, repo_path: Path, filename: str) -> Path:
        """Write JSON-serialized data to <repo_path>/.repo_intelligence/<filename>.

        Creates .repo_intelligence/ directory if it does not exist.
        Logs the output path and byte size.

        Returns:
            Path to the written file.
        """
```

---

## `aica.repo_intelligence.ast`

Tree-sitter based TypeScript/TSX AST extraction pipeline.

### `parse_file` / `parse_code`

```python
from aica.repo_intelligence.ast.parser import parse_file, parse_code

def parse_file(file_path: str | Path) -> Tree:
    """Read and parse a .ts or .tsx file. Grammar is auto-selected from extension.
    Raises FileNotFoundError if the file does not exist.
    """

def parse_code(code: str, lang: str = "typescript") -> Tree:
    """Parse a source string. lang must be 'typescript' or 'tsx'."""
```

### `ASTExtractorRunner`

```python
from aica.repo_intelligence.ast.runner import ASTExtractorRunner

class ASTExtractorRunner:
    def run(self, repo_path: Path) -> dict:
        """Walk all .ts/.tsx files under repo_path and run all 7 extractors.

        Excluded directories: node_modules, .next, dist, build, out, .git,
        .aica, .repo_intelligence.

        Returns dict with keys (all values are lists of dicts):
            'imports'    — import statements
            'functions'  — function declarations
            'exports'    — export statements
            'calls'      — call expressions (flat list)
            'hooks'      — React hook invocations
            'components' — React component definitions
            'types'      — TypeScript interfaces and type aliases
        """
```

### `ASTWriter`

```python
from aica.repo_intelligence.ast.writer import ASTWriter

class ASTWriter:
    def write(self, data: list, repo_path: Path, filename: str) -> Path:
        """Write JSON-serialized extractor results to
        <repo_path>/.repo_intelligence/ast/<filename>.
        Creates directory if needed. Returns written Path.
        """
```

### Extractor functions

All extractors follow the contract: `extract(tree: Tree, source: str, file_path: str) -> list[dict]`.

```python
from aica.repo_intelligence.ast.extractors import (
    extract_imports,
    extract_functions,
    extract_exports,
    extract_calls,
    extract_hooks,
    extract_components,
    extract_types,
    build_call_graph,
)
```

**`extract_imports`** — output schema per entry:

| Field         | Type         | Description                               |
| ------------- | ------------ | ----------------------------------------- |
| `file`        | `str`        | POSIX-relative path                       |
| `source`      | `str`        | module specifier                          |
| `import_kind` | `str`        | `"relative"` \| `"alias"` \| `"external"` |
| `default`     | `str\|None`  | default binding name                      |
| `named`       | `list[dict]` | `[{"name": str, "alias": str\|None}]`     |
| `namespace`   | `str\|None`  | `* as X` binding                          |
| `type_only`   | `bool`       | `import type { ... }`                     |
| `side_effect` | `bool`       | `import './styles.css'`                   |
| `line`        | `int`        | 1-based line number                       |

**`extract_functions`** — output schema per entry:

| Field      | Type        | Description                                              |
| ---------- | ----------- | -------------------------------------------------------- |
| `file`     | `str`       | POSIX-relative path                                      |
| `name`     | `str\|None` | `None` for anonymous arrows                              |
| `kind`     | `str`       | `"function"` \| `"arrow"` \| `"method"` \| `"generator"` |
| `async`    | `bool`      |                                                          |
| `params`   | `list[str]` | parameter names (type annotations stripped)              |
| `line`     | `int`       | 1-based line number                                      |
| `exported` | `bool`      | directly wrapped in `export_statement`                   |

**`extract_exports`** — output schema per entry:

| Field        | Type        | Description                                                         |
| ------------ | ----------- | ------------------------------------------------------------------- |
| `file`       | `str`       | POSIX-relative path                                                 |
| `name`       | `str\|None` | public binding; `"default"` for default exports                     |
| `local_name` | `str\|None` | original local symbol                                               |
| `kind`       | `str`       | `"named"` \| `"default"` \| `"re-export"` \| `"namespace-reexport"` |
| `type_only`  | `bool`      | `export type { ... }`                                               |
| `source`     | `str\|None` | from-clause specifier for re-exports                                |
| `line`       | `int`       | 1-based line number                                                 |

**`extract_calls`** — output schema per entry:

| Field           | Type        | Description                                     |
| --------------- | ----------- | ----------------------------------------------- |
| `file`          | `str`       | POSIX-relative path                             |
| `caller`        | `str\|None` | enclosing named function; `None` = module-level |
| `callee`        | `str`       | called function name                            |
| `callee_object` | `str\|None` | receiver for method calls                       |
| `kind`          | `str`       | `"call"` \| `"new"`                             |
| `line`          | `int`       | 1-based line number                             |

**`build_call_graph(calls: list[dict]) -> list[dict]`** — group flat call rows by file then by caller:

```python
# Input: flat list from extract_calls
# Output:
[
  {
    "file": "src/foo.ts",
    "functions": [
      {"name": "myFn" | None, "calls": [...]}
    ]
  }
]
```

**`extract_hooks`** — output schema per entry:

| Field        | Type        | Description                 |
| ------------ | ----------- | --------------------------- |
| `file`       | `str`       | POSIX-relative path         |
| `name`       | `str`       | hook name (e.g. `useState`) |
| `caller`     | `str\|None` | enclosing named function    |
| `args_count` | `int`       | number of call arguments    |
| `line`       | `int`       | 1-based line number         |

**`extract_components`** — output schema per entry:

| Field      | Type        | Description                              |
| ---------- | ----------- | ---------------------------------------- |
| `file`     | `str`       | POSIX-relative path                      |
| `name`     | `str`       | component name (PascalCase)              |
| `kind`     | `str`       | `"function"` \| `"arrow"` \| `"class"`   |
| `props`    | `list[str]` | destructured prop names from first param |
| `exported` | `bool`      | directly wrapped in `export_statement`   |
| `line`     | `int`       | 1-based line number                      |

**`extract_types`** — output schema per entry:

| Field      | Type        | Description                                       |
| ---------- | ----------- | ------------------------------------------------- |
| `file`     | `str`       | POSIX-relative path                               |
| `name`     | `str`       | interface or type alias name                      |
| `kind`     | `str`       | `"interface"` \| `"type"`                         |
| `exported` | `bool`      | immediate parent is `export_statement`            |
| `members`  | `list[str]` | property/method names (`[]` for non-object types) |
| `line`     | `int`       | 1-based line number                               |

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

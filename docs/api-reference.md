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

---

## Usage Examples

### LLMProvider — Generate Text

```python
from aica.core.llm.factory import LLMProvider

# Initialize with Ollama
provider = LLMProvider(provider="ollama", model="codellama")

# Synchronous generation
prompt = "Write a Python function to calculate factorial"
response = provider.generate(prompt)
print(response)

# Streaming generation
for chunk in provider.stream(prompt):
    print(chunk, end="", flush=True)
```

### LLMProvider — Async Usage

```python
import asyncio
from aica.core.llm.factory import LLMProvider

async def main():
    provider = LLMProvider(provider="openrouter", model="openai/gpt-4o-mini")

    # Async generation
    response = await provider.async_generate("Explain async/await in Python")
    print(response)

    # Async streaming
    async for chunk in provider.async_stream("Write a haiku about coding"):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

### LLMProvider — Custom Provider

```python
from aica.core.llm.factory import LLMProvider
from aica.core.llm.base import BaseLLMProvider
from typing import Iterator, AsyncIterator

class MyCustomProvider(BaseLLMProvider):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    def generate(self, prompt: str, **kwargs) -> str:
# Call your API and return result
        return f"Response from {self.model}: {prompt}"

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        # Yield tokens as they arrive
        for token in prompt.split():
            yield token + " "

    async def async_generate(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)

    async def async_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        for token in self.stream(prompt, **kwargs):
            yield token

# Register and use
LLMProvider.register("mycustom", MyCustomProvider)
provider = LLMProvider(provider="mycustom", model="my-model-v1")
print(provider.generate("Hello"))
```

### RepositoryScanner — Scan a Codebase

```python
from pathlib import Path
from aica.repo_intelligence.scanner.core import scan_repository
from aica.repo_intelligence.scanner.writers import OutputWriter

# Scan a repository
repo_path = Path("/path/to/nextjs-app")
scan_data = scan_repository(str(repo_path))

# Access results
print(f"Framework: {scan_data['framework']}")
print(f"Routes found: {len(scan_data['routes'])}")
print(f"Components found: {len(scan_data['components'])}")
print(f"Zustand stores: {len(scan_data['stores'])}")

# Write results to disk
writer = OutputWriter()
writer.write(scan_data['routes'], repo_path, "routes.json")
writer.write(scan_data['components'], repo_path, "components.json")
writer.write(scan_data, repo_path, "structure.json")
```

### RepositoryScanner — Generate Summary

```python
from pathlib import Path
from aica.repo_intelligence.scanner.summarizer import RepoSummaryGenerator
from aica.repo_intelligence.scanner.core import scan_repository

repo_path = Path("/path/to/nextjs-app")

# Option 1: From existing artifacts on disk
summarizer = RepoSummaryGenerator()
summary = summarizer.generate(repo_path)

# Option 2: From in-memory scan data
scan_data = scan_repository(str(repo_path))
summary = RepoSummaryGenerator.from_scan_data(scan_data)

# Access summary
print(f"Total routes: {summary['routes_count']}")
print(f"Total components: {summary['components_count']}")
print(f"Database ORM: {summary['database']}")
print(f"Auth providers: {summary['auth_providers']}")
```

### ASTExtractorRunner — Extract AST Data

```python
from pathlib import Path
from aica.repo_intelligence.ast.runner import ASTExtractorRunner
from aica.repo_intelligence.ast.writer import ASTWriter
from aica.repo_intelligence.ast.extractors import build_call_graph

repo_path = Path("/path/to/typescript-project")

# Run all extractors
runner = ASTExtractorRunner()
ast_data = runner.run(repo_path)

# Access results
print(f"Functions found: {len(ast_data['functions'])}")
print(f"Imports found: {len(ast_data['imports'])}")
print(f"Components found: {len(ast_data['components'])}")

# Build call graph
call_graph = build_call_graph(ast_data['calls'])

# Write to disk
writer = ASTWriter()
writer.write(ast_data['imports'], repo_path, "imports.json")
writer.write(ast_data['functions'], repo_path, "functions.json")
writer.write(call_graph, repo_path, "call_graph.json")
```

### AST Extractors — Use Individual Extractors

```python
from pathlib import Path
from aica.repo_intelligence.ast.parser import parse_file
from aica.repo_intelligence.ast.extractors import (
    extract_functions,
    extract_imports,
    extract_components,
    extract_hooks,
)

# Parse a single file
file_path = Path("src/components/Button.tsx")
tree = parse_file(file_path)
source_code = file_path.read_text()

# Extract specific data
functions = extract_functions(tree, source_code, str(file_path))
imports = extract_imports(tree, source_code, str(file_path))
components = extract_components(tree, source_code, str(file_path))
hooks = extract_hooks(tree, source_code, str(file_path))

print(f"Functions in {file_path.name}:")
for fn in functions:
    print(f"  - {fn['name']} ({fn['kind']}, line {fn['line']})")

print(f"\nImports:")
for imp in imports:
    print(f"  - {imp['source']} ({imp['import_kind']})")

print(f"\nComponents:")
for comp in components:
    print(f"  - {comp['name']} with props: {comp['props']}")
```

### Neo4j — Build Dependency Graph

```python
from pathlib import Path
from aica.memory.graph_store.graph_builder import build_dependency_graph

repo_path = Path("/path/to/nextjs-app")

# Build the graph (requires Neo4j running and configured)
summary = build_dependency_graph(repo_path)

# Access summary
print(f"Nodes created:")
print(f"  Files: {summary.files}")
print(f"  Functions: {summary.functions}")
print(f"  Components: {summary.components}")
print(f"  Types: {summary.types}")
print(f"  Hooks: {summary.hooks}")

print(f"\nEdges created:")
print(f"  Import edges: {summary.import_edges}")
print(f"  Call edges: {summary.call_edges}")
print(f"  Hook usage edges: {summary.hook_usage_edges}")
```

### Neo4j — Query the Graph

```python
from aica.memory.graph_store.neo4j_client import Neo4jClient

# Connect to Neo4j
with Neo4jClient(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your_password"
) as client:
    # Find all components using useState
    query = """
        MATCH (comp:Component)-[:USES_HOOK]->(hook:Hook {name: 'useState'})
        RETURN comp.name, comp.file
        ORDER BY comp.name
    """
    result = client.run_query(query)

    print("Components using useState:")
    for record in result:
        print(f"  - {record['comp.name']} ({record['comp.file']})")

    # Find circular dependencies
    query = """
        MATCH path = (f:File)-[:IMPORTS*2..5]->(f)
        RETURN [node IN nodes(path) | node.path] AS cycle
        LIMIT 10
    """
    result = client.run_query(query)

    print("\nCircular dependencies:")
    for record in result:
        print(f"  → {' → '.join(record['cycle'])}")
```

### Neo4j — Batch Operations

```python
from aica.memory.graph_store.neo4j_client import Neo4jClient

with Neo4jClient() as client:  # Uses env vars for connection
    # Batch create nodes
    files_data = [
        {"path": "src/app.ts"},
        {"path": "src/utils.ts"},
        {"path": "src/types.ts"},
    ]

    query = """
        UNWIND $batch AS item
        MERGE (f:File {path: item.path})
        RETURN count(f) AS created
    """

    result = client.run_batch(query, files_data)
    print(f"Created {result[0]['created']} files")

    # Transaction support
    def create_nodes(tx):
        tx.run("CREATE (f:File {path: $path})", path="src/new.ts")
        tx.run("CREATE (f:File {path: $path})", path="src/another.ts")

    client.with_transaction(create_nodes)
```

### ExecutionRunner — Run Shell Commands

```python
from aica.execution.runner import ExecutionRunner
from aica.execution.terminal.runner import run_command

# Simple execution
runner = ExecutionRunner()
result = runner.run("echo 'Hello World'")

if result.success:
    print(f"Output: {result.stdout}")
else:
    print(f"Error: {result.stderr}")
    print(f"Exit code: {result.returncode}")

# With working directory
result = runner.run("npm test", cwd="/path/to/project")

# Convenience function with timeout
result = run_command("pytest tests/ -v", timeout=300, cwd="/path/to/project")
print(f"Tests {'passed' if result.success else 'failed'}")
```

### Orchestrator — Register and Run Agents

```python
from aica.core.orchestrator import Orchestrator
from aica.core.agent import BaseAgent

# Define custom agent
class CodeReviewAgent(BaseAgent):
    name = "code-review"
    description = "Review code for best practices"

    def run(self, task: str) -> str:
        return f"Reviewed: {task}\n✓ No issues found"

# Register and use
orchestrator = Orchestrator()
orchestrator.register(CodeReviewAgent())

result = orchestrator.run("code-review", "Check src/app.ts for security issues")
print(result)

# List available agents
print("Available agents:", orchestrator.agents)
```

### TaskPlanner — Generate Execution Plans

```python
from aica.core.planner import TaskPlanner

planner = TaskPlanner()
plan = planner.plan("Add pagination to the user list API endpoint")

print(f"Task: {plan['task']}")
print(f"Status: {plan['status']}")
print("\nSteps:")
for step in plan['steps']:
    print(f"  {step['step']}. {step['name']}: {step['description']}")
```

### Memory Store — Use In-Memory Storage

```python
from aica.memory.store import InMemoryStore

store = InMemoryStore()

# Store data
store.set("user:123", {"name": "Alice", "role": "admin"})
store.set("cache:result", [1, 2, 3, 4, 5])

# Retrieve data
user = store.get("user:123")
print(f"User: {user['name']}")

# List keys
print(f"All keys: {store.keys()}")

# Delete and clear
store.delete("cache:result")
store.clear()
```

### Logging — Use Structured Logging

```python
from aica.core.logging.logger import get_logger

log = get_logger("mymodule.myfeature")

# Log with context
log.info("processing_started", file="src/app.ts", lines=1234)

# Log errors
try:
    raise ValueError("Invalid configuration")
except Exception as e:
    log.error("processing_failed", error=str(e), file="src/app.ts")

# Log with structured data
log.debug(
    "function_analyzed",
    name="getData",
    params=["id", "options"],
    async_=True,
    line=42
)
```

---

## Next Steps

- **[CLI Reference](cli.md)** — Command-line usage
- **[Configuration Reference](configuration.md)** — Environment variables
- **[Extending AICA](extending.md)** — Add custom agents, detectors, tools
- **[Tutorials](tutorials.md)** — Step-by-step guides
- **[Neo4j Graph Guide](neo4j-graph.md)** — Dependency graph queries

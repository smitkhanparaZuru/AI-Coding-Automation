# Developer Extension Guide

AICA is designed for extension. Every major subsystem exposes an ABC (Abstract Base Class) that you subclass to add new capabilities without modifying core code.

---

## Table of Contents

- [Adding a new LLM Provider](#adding-a-new-llm-provider)
- [Adding a new Agent](#adding-a-new-agent)
- [Adding a new Tool](#adding-a-new-tool)
- [Swapping the Memory Backend](#swapping-the-memory-backend)
- [Logging conventions](#logging-conventions)
- [Error handling patterns](#error-handling-patterns)
- [Settings access pattern](#settings-access-pattern)

---

## Adding a new LLM Provider

Subclass `BaseLLMProvider` and implement all four methods (sync, async, stream, async stream). Then register it with the factory.

```python
# aica/core/llm/my_provider.py
from collections.abc import AsyncIterator, Iterator
from aica.core.llm.base import BaseLLMProvider
from aica.core.llm.exceptions import LLMConnectionError, LLMTimeoutError

class MyProvider(BaseLLMProvider):
    """Custom LLM provider for MyService."""

    def __init__(self, model: str, timeout: int = 60, **kwargs):
        self.model = model
        self._timeout = timeout

    def generate(self, prompt: str, **kwargs) -> str:
        # Call your API synchronously, return full response string
        response = self._call_api(prompt)
        return response

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        # Yield tokens as they arrive
        for chunk in self._call_api_streaming(prompt):
            yield chunk

    async def async_generate(self, prompt: str, **kwargs) -> str:
        # Async variant
        return await self._async_call_api(prompt)

    async def async_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        # Async streaming variant
        async for chunk in self._async_call_api_streaming(prompt):
            yield chunk
```

Register your provider with the factory (do this at app startup, e.g. in `cli.py` callback):

```python
from aica.core.llm.factory import LLMProvider
from aica.core.llm.my_provider import MyProvider

LLMProvider.register("myprovider", MyProvider)
```

Then set in your `.env`:

```env
AICA_LLM_PROVIDER=myprovider
```

### Retry behaviour

Raise the appropriate exception type so the factory's retry logic applies correctly:

| Exception            | Retried? | When to raise                                      |
| -------------------- | -------- | -------------------------------------------------- |
| `LLMConnectionError` | **Yes**  | Network failure, 5xx responses, connection refused |
| `LLMRateLimitError`  | **Yes**  | HTTP 429 Too Many Requests                         |
| `LLMTimeoutError`    | **Yes**  | Request exceeded timeout                           |
| `LLMAuthError`       | **No**   | HTTP 401/403 — wrong API key                       |

```python
from aica.core.llm.exceptions import LLMAuthError, LLMConnectionError, LLMRateLimitError

# Example: map HTTP status codes to exceptions
if response.status_code == 401:
    raise LLMAuthError("Invalid API key")
elif response.status_code == 429:
    raise LLMRateLimitError("Rate limit exceeded")
elif response.status_code >= 500:
    raise LLMConnectionError(f"Server error: {response.status_code}")
```

---

## Adding a new Agent

Subclass `BaseAgent`, set `name` and `description`, implement `run()`, and register with the `Orchestrator`.

```python
# aica/core/agents/my_agent.py
from aica.core.agent import BaseAgent
from aica.core.llm.factory import LLMProvider
from aica.core.logging.logger import get_logger

class CodeReviewAgent(BaseAgent):
    name = "code-review"
    description = "Reviews code for quality, security, and best practices"

    def __init__(self) -> None:
        self._llm = LLMProvider()
        self._log = get_logger("agent.code-review")

    def run(self, task: str) -> str:
        self._log.info("review.started", task_length=len(task))
        prompt = f"Review the following code and provide actionable feedback:\n\n{task}"
        result = self._llm.generate(prompt)
        self._log.info("review.completed")
        return result
```

Register with the orchestrator:

```python
from aica.core.orchestrator import Orchestrator
from aica.core.agents.my_agent import CodeReviewAgent

orchestrator = Orchestrator()
orchestrator.register(CodeReviewAgent())

# Dispatch
result = orchestrator.run("code-review", task="def add(a, b): return a + b")
```

### Agent naming conventions

- Use kebab-case for `name`: `"code-review"`, `"doc-generator"`, `"test-writer"`
- Keep `description` to a single sentence
- Use `internal_` prefix for private helper methods that are not part of the public API

---

## Adding a new Tool

Subclass `BaseTool`, set `name` and `description`, implement `execute()`:

```python
# aica/tools/file_reader.py
from pathlib import Path
from aica.tools.base import BaseTool

class FileReaderTool(BaseTool):
    name = "file-reader"
    description = "Reads the contents of a file from the workspace"

    def execute(self, *, file_path: str, encoding: str = "utf-8") -> str:
        """Read and return file contents.

        Args:
            file_path: Absolute or relative path to the file.
            encoding: File encoding (default utf-8).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return path.read_text(encoding=encoding)
```

Tools are invoked explicitly by agents or directly:

```python
from aica.tools.file_reader import FileReaderTool

tool = FileReaderTool()
content = tool.execute(file_path="/projects/app/src/index.ts")
```

### Tool design guidelines

- Use keyword-only arguments (`*`) in `execute()` for clarity
- Raise standard Python exceptions (`FileNotFoundError`, `ValueError`, etc.) — do not swallow errors
- Keep tools stateless; instantiate them fresh or as singletons
- Never call LLM APIs inside a tool directly — tools are pure utilities

---

## Adding a new Scanner Detector

AICA's repository scanner uses a pluggable detector pattern. Each detector analyzes one aspect of the codebase (routes, components, stores, etc.). To add a new detector:

### Step 1: Create the Detector

Subclass the implicit detector interface and implement the `detect()` method:

```python
# aica/repo_intelligence/scanner/detectors/graphql.py
from pathlib import Path
from aica.core.logging.logger import get_logger

log = get_logger("repo.detector.graphql")

class GraphQLDetector:
    """Detects GraphQL schema files and resolvers."""

    def detect(self, repo_path: Path) -> dict:
        """Scan for GraphQL schemas (.graphql, .gql) and resolvers.

        Returns:
            {
                "schemas": [{"name": str, "file": str, "types": int}],
                "resolvers": [{"name": str, "file": str, "operations": list[str]}]
            }
        """
        log.info("graphql.detection.started", repo_path=str(repo_path))

        schemas = []
        resolvers = []

        # Look for schema files
        schema_patterns = ["**/*.graphql", "**/*.gql"]
        for pattern in schema_patterns:
            for schema_file in repo_path.glob(pattern):
                # Skip excluded dirs
                if self._should_exclude(schema_file):
                    continue

                # Parse schema (basic detection)
                content = schema_file.read_text()
                type_count = content.count("type ") + content.count("interface ")

                schemas.append({
                    "name": schema_file.stem,
                    "file": str(schema_file.relative_to(repo_path)).replace("\\", "/"),
                    "types": type_count,
                })

        # Look for resolvers (conventionally in src/resolvers/ or src/graphql/)
        resolver_dirs = [
            repo_path / "src" / "resolvers",
            repo_path / "resolvers",
            repo_path / "src" / "graphql" / "resolvers",
        ]

        for resolver_dir in resolver_dirs:
            if not resolver_dir.is_dir():
                continue

            for resolver_file in resolver_dir.glob("**/*.ts"):
                content = resolver_file.read_text()

                # Detect exported resolver functions/objects
                operations = []
                if "Query:" in content:
                    operations.append("Query")
                if "Mutation:" in content:
                    operations.append("Mutation")
                if "Subscription:" in content:
                    operations.append("Subscription")

                if operations:
                    resolvers.append({
                        "name": resolver_file.stem,
                        "file": str(resolver_file.relative_to(repo_path)).replace("\\", "/"),
                        "operations": operations,
                    })

        log.info(
            "graphql.detection.completed",
            schemas_count=len(schemas),
            resolvers_count=len(resolvers),
        )

        return {
            "schemas": schemas,
            "resolvers": resolvers,
        }

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from scanning."""
        excluded = {"node_modules", ".next", "dist", "build", "out", ".git"}
        return any(part in excluded for part in path.parts)
```

### Step 2: Register in RepositoryScanner

Add your detector to `RepositoryScanner` in `aica/repo_intelligence/scanner/core.py`:

```python
# aica/repo_intelligence/scanner/core.py
from aica.repo_intelligence.scanner.detectors.graphql import GraphQLDetector

class RepositoryScanner:
    def __init__(self) -> None:
        self._detectors = {
            "framework": FrameworkDetector(),
            "structure": StructureDetector(),
            # ... existing detectors ...
            "graphql": GraphQLDetector(),  # <- Add your detector
        }

    def scan(self, repo_path: Path) -> dict:
        result = {"repo_path": str(repo_path.resolve())}

        for name, detector in self._detectors.items():
            log.info(f"scanner.detector.{name}.started")
            detector_result = detector.detect(repo_path)

            if name == "graphql":
                result["graphql"] = detector_result  # Merge into top-level
            else:
                result.update(detector_result)  # Or merge keys directly

            log.info(f"scanner.detector.{name}.completed")

        return result
```

### Step 3: Update OutputWriter

Write your detector results to a dedicated JSON file:

```python
# In aica/interfaces/cli.py, scan_repo command

# After running scanner
scan_data = scanner.scan(target)

# Write all outputs including new detector
if "graphql" in scan_data:
    writer.write(scan_data["graphql"], target, "graphql.json")
```

### Step 4: Add Tests

Create comprehensive tests in `tests/test_graphql_detector.py`:

```python
import pytest
from pathlib import Path
from aica.repo_intelligence.scanner.detectors.graphql import GraphQLDetector

def test_detect_graphql_schemas(tmp_path: Path):
    """Test detection of .graphql schema files."""
    # Create test schema
    schema_file = tmp_path / "schema.graphql"
    schema_file.write_text("""
        type User {
            id: ID!
            name: String!
        }

        type Query {
            getUser(id: ID!): User
        }
    """)

    detector = GraphQLDetector()
    result = detector.detect(tmp_path)

    assert len(result["schemas"]) == 1
    assert result["schemas"][0]["name"] == "schema"
    assert result["schemas"][0]["types"] == 2  # User + Query

def test_detect_graphql_resolvers(tmp_path: Path):
    """Test detection of resolver files."""
    # Create resolver directory
    resolvers_dir = tmp_path / "src" / "resolvers"
    resolvers_dir.mkdir(parents=True)

    # Create resolver file
    resolver_file = resolvers_dir / "users.ts"
    resolver_file.write_text("""
        export const resolvers = {
            Query: {
                getUser: async (parent, { id }, context) => { ... }
            },
            Mutation: {
                createUser: async (parent, { input }, context) => { ... }
            }
        };
    """)

    detector = GraphQLDetector()
    result = detector.detect(tmp_path)

    assert len(result["resolvers"]) == 1
    assert result["resolvers"][0]["name"] == "users"
    assert "Query" in result["resolvers"][0]["operations"]
    assert "Mutation" in result["resolvers"][0]["operations"]

def test_excludes_node_modules(tmp_path: Path):
    """Test that node_modules is excluded from scanning."""
    # Create schema in node_modules (should be ignored)
    node_modules = tmp_path / "node_modules" / "some-package"
    node_modules.mkdir(parents=True)
    (node_modules / "schema.graphql").write_text("type Ignored { }")

    detector = GraphQLDetector()
    result = detector.detect(tmp_path)

    assert len(result["schemas"]) == 0
```

Run tests:

```bash
pytest tests/test_graphql_detector.py -v
```

### Detector Design Guidelines

1. **Output Schema**
   - Return a dict or list of dicts
   - Use consistent key names: `name`, `file`, `line`, `type`, etc.
   - File paths should be POSIX-relative to repo root: `src/schema.graphql` not `src\\schema.graphql`

2. **Performance**
   - Avoid unnecessary file reads; use glob patterns efficiently
   - Cache expensive operations if detector is called multiple times
   - Log start/completion with counts

3. **Exclusions**
   - Always exclude: `node_modules`, `.next`, `dist`, `build`, `out`, `.git`, `.repo_intelligence`
   - Use a helper method like `_should_exclude()` for consistency

4. **Error Handling**
   - Log warnings for parse errors but continue scanning
   - Never raise exceptions for missing directories — return empty results
   - Use try-except for file I/O, log errors, return partial results

5. **Testing**
   - Test with `tmp_path` fixtures (pytest)
   - Cover: found items, excluded items, empty directories, malformed files
   - Verify output schema matches documentation

### Example: Minimal Detector

```python
# aica/repo_intelligence/scanner/detectors/docker.py
from pathlib import Path

class DockerDetector:
    """Detects Docker configuration files."""

    def detect(self, repo_path: Path) -> dict:
        docker_files = []

        # Look for Dockerfile variants
        for dockerfile in repo_path.glob("**/Dockerfile*"):
            if "node_modules" in dockerfile.parts:
                continue

            docker_files.append({
                "name": dockerfile.name,
                "file": str(dockerfile.relative_to(repo_path)).replace("\\", "/"),
            })

        # Look for docker-compose files
        for compose_file in repo_path.glob("**/docker-compose*.{yml,yaml}"):
            if "node_modules" in compose_file.parts:
                continue

            docker_files.append({
                "name": compose_file.name,
                "file": str(compose_file.relative_to(repo_path)).replace("\\", "/"),
            })

        return {"docker": docker_files}
```

---

## Swapping the Memory Backend

The `InMemoryStore` is a dict-backed in-memory implementation suitable for development. For persistent memory (SQLite, Redis, etc.), subclass `MemoryStore`:

```python
# aica/memory/sqlite_store.py
import sqlite3
from typing import Any
from aica.memory.store import MemoryStore

class SQLiteMemoryStore(MemoryStore):
    """Persistent memory backend using SQLite."""

    def __init__(self, db_path: str = ".aica/memory.db") -> None:
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT)"
            )

    def get(self, key: str) -> Any | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT value FROM memory WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: Any) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory (key, value) VALUES (?, ?)", (key, str(value))
            )

    def delete(self, key: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM memory WHERE key=?", (key,))

    def clear(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM memory")

    def keys(self) -> list[str]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT key FROM memory").fetchall()
        return [row[0] for row in rows]
```

Swap in usage:

```python
# Before
from aica.memory.store import InMemoryStore
memory = InMemoryStore()

# After
from aica.memory.sqlite_store import SQLiteMemoryStore
memory = SQLiteMemoryStore(db_path=".aica/memory.db")
```

No agent code changes needed — they depend only on the `MemoryStore` ABC.

---

## Logging conventions

AICA uses `structlog` for structured logging. **Never use** `print()`, `logging.getLogger()`, or `console.log()`.

```python
from aica.core.logging.logger import get_logger

log = get_logger("agent.my-agent")   # module.submodule format

# Structured log events with key-value context
log.info("task.started", task=task_name, agent="my-agent")
log.debug("llm.request", prompt_length=len(prompt), model=model_name)
log.warning("retry.attempt", attempt=2, error=str(exc))
log.error("task.failed", error=str(exc), task=task_name)
```

### Logger naming

Use dot-separated namespaces:

| Scope             | Format           | Example                        |
| ----------------- | ---------------- | ------------------------------ |
| LLM providers     | `llm.<provider>` | `llm.ollama`, `llm.openrouter` |
| Agents            | `agent.<name>`   | `agent.code-review`            |
| CLI commands      | `cli`            | `cli`                          |
| Repo intelligence | `repo.<module>`  | `repo.indexer`, `repo.scanner` |
| Tools             | `tool.<name>`    | `tool.file-reader`             |

### What to log (and what not to)

| ✅ Log                       | ❌ Never log                                |
| ---------------------------- | ------------------------------------------- |
| Task names and IDs           | API keys / tokens                           |
| Token counts, prompt lengths | User passwords                              |
| Operation durations          | Full prompt/response content containing PII |
| Error types and messages     | `SecretStr` field values                    |
| File paths and line counts   | Stack traces containing secrets             |

---

## Error handling patterns

### LLM errors

```python
from aica.core.llm.exceptions import LLMAuthError, LLMConnectionError, LLMError

try:
    result = llm.generate(prompt)
except LLMAuthError:
    # Configuration problem — do NOT retry, surface to user
    raise
except LLMConnectionError as exc:
    # Transient — factory automatically retries up to AICA_LLM_MAX_RETRIES
    log.warning("llm.connection_error", error=str(exc))
    raise
except LLMError as exc:
    # Unknown LLM error
    log.error("llm.error", error=str(exc))
    raise
```

### Command execution errors

Always check `RunResult.success` before using stdout:

```python
from aica.execution.runner import ExecutionRunner

runner = ExecutionRunner()
result = runner.run("pytest tests/", cwd="/projects/app")

if not result.success:
    log.error(
        "command.failed",
        command=result.command,
        returncode=result.returncode,
        stderr=result.stderr[:200],  # truncate for log safety
    )
    raise RuntimeError(f"Command failed (exit {result.returncode}): {result.stderr}")

output = result.stdout  # safe to use
```

### Timeout handling

Use `TerminalRunner` when you need timeout control:

```python
from aica.execution.terminal.runner import TerminalRunner

runner = TerminalRunner(timeout=30, cwd="/projects/app")
result = runner.run("npm test")

if result.returncode == -1:
    # Timeout occurred — result.stderr contains the timeout message
    log.warning("command.timeout", command="npm test")
```

---

## Settings access pattern

Always use the singleton accessor:

```python
from aica.config.settings import get_settings

def my_function() -> None:
    settings = get_settings()              # cached singleton
    model = settings.ollama_model          # access any field
    timeout = settings.llm_timeout

    # For SecretStr fields, only unwrap when constructing HTTP requests:
    if settings.openrouter_api_key:
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"
        }
```

**Rules:**

- Never instantiate `Settings()` directly — always use `get_settings()`
- Never pass settings objects across module boundaries — call `get_settings()` locally
- Never log a settings object that contains `SecretStr` fields

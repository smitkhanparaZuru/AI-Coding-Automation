# AICA — Coding Guidelines & Architecture Patterns

AICA is a Python 3.11+ AI coding automation engine with a modular architecture, CLI-first design, and pluggable LLM backends. Follow these guidelines when contributing code, adding features, or extending the system.

---

## Core Architecture Principles

### 1. Module Organization & Structure

```
aica/
├── config/         # Pydantic Settings with AICA_ prefix
├── core/           # Agent, orchestrator, planner, LLM providers
├── execution/      # Command runners with captured output
├── interfaces/     # CLI via Typer
├── memory/         # Pluggable memory stores
├── repo_intelligence/  # Scanner + AST + graph builders
└── tools/          # Extensible tool system
```

**Key rules:**

- **Core modules** contain abstract base classes and orchestration logic
- **Repo intelligence** is read-only; never modifies target repositories
- **Execution layer** handles all subprocess calls with safety wrappers
- **Config** uses Pydantic Settings v2 with `AICA_` environment variable prefix

### 2. Import Organization (Strict Order)

Always organize imports in this sequence:

```python
from __future__ import annotations  # ALWAYS first line

# 1. Standard library
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

# 2. Third-party libraries
from pydantic import BaseModel
from rich.console import Console

# 3. Internal AICA imports (grouped by module)
from aica.config.settings import Settings
from aica.core.logging import get_logger
from aica.core.llm.base import BaseLLMProvider

# 4. Relative imports (only within same package)
from .helpers import parse_json
```

**Critical rules:**

- **Always** start with `from __future__ import annotations` (enables forward references)
- Use absolute imports for all cross-module references: `from aica.core.logging import get_logger`
- Relative imports (`.helpers`) only within the same package directory
- Group imports by category with blank lines between groups

### 3. Abstract Base Classes & Extensibility

AICA uses ABC patterns for all pluggable components:

```python
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """All agents inherit from this base."""
    name: str
    description: str

    @abstractmethod
    def run(self, task: str) -> str:
        """Execute a task and return the result."""
        ...
```

**When extending AICA:**

- Subclass `BaseLLMProvider` for new LLM backends
- Subclass `BaseAgent` for new agent types
- Subclass `MemoryStore` for persistent memory backends
- Subclass `BaseTool` for new automation capabilities

**ABC conventions:**

- Use `@abstractmethod` for required implementations
- Document extension points in class docstrings
- Use `...` (Ellipsis) for abstract method bodies, never `pass`

### 4. Type Safety & Type Hints

```python
from pathlib import Path
from collections.abc import Iterator, AsyncIterator

def process_file(file_path: Path, *, encoding: str = "utf-8") -> dict:
    """Process a file and extract metadata."""
    ...

def stream_tokens(prompt: str) -> Iterator[str]:
    """Yield tokens as they arrive."""
    ...

async def async_stream(prompt: str) -> AsyncIterator[str]:
    """Async generator for streaming tokens."""
    ...
```

**Type hint rules:**

- Use type hints for **all** function parameters and return types
- Use `Path` for file paths, not `str`
- Use `collections.abc` for iterators, not `typing.Iterator` (Python 3.11+)
- Use `dict` not `Dict`, `list` not `List` (builtin generics in Python 3.11+)
- Never use bare `object` — prefer `dict`, `list[dict]`, or Pydantic models

### 5. Logging with Structlog

Always use structured logging via `get_logger()`, never `print()` or stdlib `logging`:

```python
from aica.core.logging import get_logger

log = get_logger("detector.mydetector")

# ✅ Good — structured key-value pairs
log.info("detection.started", repo_path=str(repo_path))
log.debug("files.found", count=len(files), pattern="*.ts")
log.error("scan.failed", error=str(e), path=str(repo_path))

# ❌ Bad — never use these
print("Starting detection...")           # No print statements
logging.info("Detection started")         # No stdlib logging
log.info(f"Found {count} files")          # Don't format in message
```

**Logging conventions:**

- Logger names use dotted notation: `"detector.mydetector"`, `"scanner.core"`
- Event names use dot-separated format: `"detection.started"`, `"files.found"`
- Always pass variables as keyword arguments, never in formatted strings
- Convert `Path` objects to strings: `path=str(file_path)`

### 6. Configuration via Pydantic Settings

```python
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AICA_", env_file=".env")

    llm_provider: str = Field(default="ollama")
    openrouter_api_key: SecretStr | None = Field(default=None)
    log_level: str = Field(default="INFO")
```

**Config rules:**

- All settings use `AICA_` environment variable prefix
- Use `SecretStr` for API keys and passwords (masked in logs)
- Provide sensible defaults with `Field(default=...)`
- Load from `.env` file via `env_file=".env"`
- Never hardcode secrets or URLs in source files

### 7. Detector Pattern (Repository Intelligence)

All detectors follow this interface:

```python
from pathlib import Path
from aica.core.logging import get_logger

log = get_logger("detector.mydetector")

class MyDetector:
    """Detect X in a Next.js repository."""

    def detect(self, repo_path: Path) -> list[dict] | dict:
        """Scan repo_path and return structured metadata.

        Returns:
            List of dicts for multiple items (routes, components)
            or single dict for singleton data (framework, structure).
        """
        log.info("detection.started", path=str(repo_path))

        # Scan logic here
        results = []

        log.debug("detection.completed", count=len(results))
        return results
```

**Detector conventions:**

- Return `list[dict]` for collections (routes, components, services)
- Return `dict` for singleton metadata (framework info, structure)
- Always log start/completion with counts
- Never modify the repository — detectors are read-only
- Handle missing files/directories gracefully (return empty list/dict, log warning)

### 8. LLM Provider Pattern

New LLM providers must implement these four methods:

```python
from aica.core.llm.base import BaseLLMProvider
from collections.abc import Iterator, AsyncIterator

class MyProvider(BaseLLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url

    def generate(self, prompt: str, **kwargs: object) -> str:
        """Synchronous complete generation."""
        ...

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Synchronous streaming generation."""
        ...

    async def async_generate(self, prompt: str, **kwargs: object) -> str:
        """Async complete generation."""
        ...

    async def async_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """Async streaming generation."""
        ...
```

**LLM provider rules:**

- Register in `factory._REGISTRY` with a unique name
- Implement retry logic with exponential backoff (use `tenacity`)
- Raise specific exceptions from `llm.exceptions` (`LLMConnectionError`, `LLMAuthError`, etc.)
- Never log API keys or secrets
- Use `httpx` for HTTP clients, not `requests` (supports async)

### 9. Error Handling

```python
from aica.core.llm.exceptions import LLMConnectionError, LLMTimeoutError

try:
    response = provider.generate(prompt)
except LLMConnectionError as e:
    log.error("llm.connection_failed", error=str(e))
    raise
except LLMTimeoutError as e:
    log.warning("llm.timeout", error=str(e), retrying=True)
    # Implement retry logic
```

**Error handling conventions:**

- Use specific exception types from `aica.core.llm.exceptions`
- Always log errors with structured context before re-raising
- Use `try/except/finally` for cleanup (close files, connections)
- Catch specific exceptions, not bare `except:`

### 10. Docstrings & Documentation

Use Google-style docstrings for all public APIs:

```python
def process_file(file_path: Path, *, encoding: str = "utf-8") -> dict:
    """Process a file and extract metadata.

    Args:
        file_path: Absolute path to the file.
        encoding: File encoding (default: utf-8).

    Returns:
        Dictionary with keys: 'name', 'size', 'lines'.

    Raises:
        FileNotFoundError: If file_path does not exist.

    Example:
        >>> result = process_file(Path("data.json"))
        >>> print(result["lines"])
        42
    """
```

**Documentation rules:**

- All public functions/classes must have docstrings
- Use `Args:`/`Returns:`/`Raises:` sections consistently
- Include examples for complex APIs
- Private functions (starting with `_`) can have brief one-line docstrings

---

## Naming Conventions

| Element           | Convention       | Example                      |
| ----------------- | ---------------- | ---------------------------- |
| Modules           | snake_case       | `llm_provider.py`            |
| Classes           | PascalCase       | `BaseLLMProvider`            |
| Functions/Methods | snake_case       | `detect()`, `generate()`     |
| Constants         | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_URL` |
| Private methods   | `_` prefix       | `_internal_helper()`         |
| Type variables    | PascalCase + `T` | `ConfigT`, `ProviderT`       |

---

## Testing Requirements

### Test File Structure

```python
# tests/test_mydetector.py
from pathlib import Path
import pytest

from aica.repo_intelligence.scanner.detectors.mydetector import MyDetector


def test_detector_finds_items(tmp_path: Path) -> None:
    """Test detector finds expected items."""
    # Setup test files
    (tmp_path / "package.json").write_text('{"name": "test"}')

    # Run detector
    detector = MyDetector()
    result = detector.detect(tmp_path)

    # Assert results
    assert isinstance(result, list)
    assert len(result) > 0


def test_detector_handles_missing_files(tmp_path: Path) -> None:
    """Test detector gracefully handles missing files."""
    detector = MyDetector()
    result = detector.detect(tmp_path)

    assert result == []  # Empty list for missing data
```

**Testing conventions:**

- Test file names: `test_<module>.py`
- Function names: `test_<feature>_<scenario>()`
- Use `pytest` fixtures: `tmp_path`, `monkeypatch`
- Use descriptive docstrings in test functions
- Aim for >80% code coverage on new code
- Run tests with `pytest tests/ -v` before committing

---

## Development Workflow

### Before Committing

```bash
# 1. Run tests
pytest tests/ -v

# 2. Check coverage
pytest tests/ --cov=aica --cov-report=term-missing

# 3. Run linter
ruff check aica/

# 4. Format code
ruff format aica/

# 5. Type check
mypy aica/
```

All checks must pass before submitting pull requests.

### Adding New Features

1. **Detectors**: Add to `repo_intelligence/scanner/detectors/`, follow detector pattern above
2. **LLM Providers**: Add to `core/llm/`, implement `BaseLLMProvider`, register in `factory.py`
3. **Agents**: Add to `core/`, implement `BaseAgent`, register in `orchestrator.py`
4. **CLI Commands**: Add to `interfaces/cli.py` using `@app.command()` decorator
5. **Tests**: Add corresponding test file in `tests/` with >80% coverage

### Output Files & Artifacts

AICA writes analysis results to `.repo_intelligence/` (never commit these):

```
.repo_intelligence/
├── structure.json        # Full scan results
├── routes.json          # Route list
├── components.json      # Component list
├── services.json        # Service list
├── database.json        # Database schemas
├── packages.json        # Package catalog
└── repo_summary.json    # High-level summary
```

**Never**:

- Commit `.repo_intelligence/` to git
- Modify files in target repositories during scanning
- Rely on these files existing (always generate fresh)

---

## Common Gotchas

### ❌ Don't Do This

```python
# ❌ Using print instead of logging
print("Scanning repository...")

# ❌ Using stdlib logging
import logging
logging.info("Detection started")

# ❌ Relative imports across packages
from ..core.logging import get_logger

# ❌ Missing type hints
def process_data(data):
    return data

# ❌ Hardcoded paths or URLs
base_url = "http://localhost:11434"

# ❌ Bare except clauses
try:
    risky_operation()
except:
    pass
```

### ✅ Do This Instead

```python
# ✅ Use structured logging
from aica.core.logging import get_logger
log = get_logger("mymodule")
log.info("scan.started", repo_path=str(repo_path))

# ✅ Use absolute imports
from aica.core.logging import get_logger

# ✅ Always add type hints
def process_data(data: dict) -> dict:
    return data

# ✅ Use config for URLs
from aica.config.settings import get_settings
settings = get_settings()
base_url = settings.ollama_base_url

# ✅ Catch specific exceptions
from aica.core.llm.exceptions import LLMConnectionError
try:
    risky_operation()
except LLMConnectionError as e:
    log.error("operation.failed", error=str(e))
    raise
```

---

## Quick Reference Commands

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_llm_factory.py -v

# Check coverage
pytest tests/ --cov=aica --cov-report=html

# Lint code
ruff check aica/

# Format code
ruff format aica/

# Type check
mypy aica/

# Run CLI
aica --help
aica scan-repo --verbose
aica index-code
aica build-graph
```

---

## Questions or Issues?

- Read the full documentation in `docs/`
- Check existing detectors in `repo_intelligence/scanner/detectors/` for patterns
- Review tests in `tests/` for usage examples
- See `CONTRIBUTING.md` for pull request process

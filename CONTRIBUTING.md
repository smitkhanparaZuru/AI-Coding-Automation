# Contributing to AICA

Thank you for your interest in contributing to AICA! This guide will help you get started.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Adding New Features](#adding-new-features)
- [Reporting Bugs](#reporting-bugs)

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

---

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/AI-Coding-Automation.git
   cd AI-Coding-Automation
   ```
3. **Add upstream remote:**
   ```bash
   git remote add upstream https://github.com/original-org/AI-Coding-Automation.git
   ```
4. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-new-feature
   ```

---

## Development Setup

### Prerequisites

- Python 3.11 or 3.12
- pip (latest version)
- Docker (for Neo4j tests)
- Ollama (optional, for local LLM testing)

### Install in Editable Mode

```bash
pip install -e ".[dev]"
```

This installs AICA with all development dependencies:

- `pytest` — testing framework
- `pytest-cov` — code coverage
- `ruff` — linter and formatter
- `mypy` — static type checker

### Verify Installation

```bash
aica version
# aica 0.1.0

python -m pytest tests/ -v
# All tests should pass
```

---

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_llm_factory.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=aica --cov-report=term-missing
```

**Coverage threshold:** Aim for >80% coverage on new code.

### Run Type Checking

```bash
mypy aica/
```

### Run Linting

```bash
ruff check aica/
```

### Run Formatting

```bash
ruff format aica/
```

---

## Code Style

AICA follows these style guidelines:

### Python Style

- **PEP 8** compliance (enforced by `ruff`)
- **Line length:** 100 characters (configured in `pyproject.toml`)
- **Import order:** External → Internal → Relative, sorted alphabetically
- **Type hints:** Use for all function signatures (parameters and return types)
- **Docstrings:** Google style for public APIs

### Example Function

```python
from pathlib import Path
from aica.core.logging.logger import get_logger

log = get_logger("mymodule")

def process_file(file_path: Path, *, encoding: str = "utf-8") -> dict:
    """Process a file and extract metadata.

    Args:
        file_path: Absolute path to the file.
        encoding: File encoding (default: utf-8).

    Returns:
        Dictionary with keys: 'name', 'size', 'lines'.

    Raises:
        FileNotFoundError: If file_path does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    log.info("file.processing", path=str(file_path))
    content = file_path.read_text(encoding=encoding)

    return {
        "name": file_path.name,
        "size": file_path.stat().st_size,
        "lines": len(content.splitlines()),
    }
```

### Naming Conventions

| Element   | Convention               | Example              |
| --------- | ------------------------ | -------------------- |
| Modules   | snake_case               | `llm_provider.py`    |
| Classes   | PascalCase               | `LLMProvider`        |
| Functions | snake_case               | `run_command()`      |
| Constants | UPPER_SNAKE_CASE         | `MAX_RETRIES`        |
| Private   | \_prefix                 | `_internal_method()` |
| Type Vars | PascalCase with T suffix | `ConfigT`            |

### Logging

Always use `structlog` via `get_logger()`:

```python
from aica.core.logging.logger import get_logger

log = get_logger("detector.mydetector")

# ✅ Good
log.info("detection.started", repo_path=str(repo_path))
log.debug("files.found", count=len(files), pattern="*.ts")

# ❌ Bad
print("Starting detection...")   # Never use print()
logging.info("Files found")      # Never use stdlib logging
```

---

## Pull Request Process

### Before Submitting

1. **Sync with upstream:**

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks:**

   ```bash
   ruff check aica/
   ruff format aica/ --check
   mypy aica/
   pytest tests/ --cov=aica
   ```

3. **Update documentation** if you changed:
   - Public APIs → update `docs/api-reference.md`
   - CLI commands → update `docs/cli.md`
   - Configuration → update `docs/configuration.md`
   - New features → add entry to `CHANGELOG.md`

### Submitting the PR

1. **Push your branch:**

   ```bash
   git push origin feature/my-new-feature
   ```

2. **Open a Pull Request** on GitHub

3. **Fill out the PR template:**
   - **Description:** What does this PR do?
   - **Related Issues:** Link to issue number (e.g., #42)
   - **Type:** Bug fix | Feature | Documentation | Refactor
   - **Breaking Changes:** Yes/No (explain if yes)
   - **Checklist:**
     - [ ] Tests added/updated
     - [ ] Documentation updated
     - [ ] CHANGELOG.md entry added
     - [ ] All tests pass
     - [ ] Ruff and mypy checks pass

### Review Process

- Maintainers will review within 3-5 business days
- Address review feedback by pushing new commits
- Once approved, a maintainer will merge your PR

---

## Commit Message Guidelines

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation change
- `style`: Code style (formatting, no logic change)
- `refactor`: Code restructuring (no behavior change)
- `test`: Test addition or update
- `chore`: Build, tooling, dependencies

### Scope

- `llm`: LLM providers
- `cli`: CLI commands
- `scanner`: Repository scanner
- `ast`: AST extraction
- `graph`: Neo4j graph building
- `config`: Settings and configuration
- `docs`: Documentation

### Examples

```
feat(scanner): add GraphQL detector

Adds a new detector for GraphQL schema files (.graphql, .gql)
and resolver directories. Outputs to graphql.json.

Closes #123
```

```
fix(llm): retry on 429 rate limit errors

Previously only 5xx errors were retried. This adds 429 to the
retry logic with exponential backoff.

Fixes #456
```

---

## Adding New Features

### Adding a New Detector

See [docs/extending.md](docs/extending.md#adding-a-new-scanner-detector) for full guide.

**Quick checklist:**

1. Create `aica/repo_intelligence/scanner/detectors/mydetector.py`
2. Implement `detect(repo_path: Path) -> dict`
3. Register in `RepositoryScanner` (`scanner/core.py`)
4. Add output writer in `cli.py`
5. Write tests in `tests/test_mydetector.py`
6. Update `docs/cli.md` output files section

### Adding a New AST Extractor

1. Create `aica/repo_intelligence/ast/extractors/my_extractor.py`
2. Implement `extract(tree: Tree, source: str, file_path: str) -> list[dict]`
3. Add to `ASTExtractorRunner` in `ast/runner.py`
4. Write tests in `tests/test_my_extractor.py`
5. Update `docs/api-reference.md` with output schema

### Adding a New CLI Command

1. Add command function in `aica/interfaces/cli.py`
2. Use `@app.command(name="my-command")` decorator
3. Add docstring (shown in `--help`)
4. Log start/completion with `get_logger("cli")`
5. Write tests in `tests/test_cli.py`
6. Document in `docs/cli.md`

---

## Reporting Bugs

### Before Reporting

1. **Search existing issues** to avoid duplicates
2. **Update to latest version:** `pip install --upgrade .`
3. **Try minimal reproduction** to isolate the issue

### Bug Report Template

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Run command '...'
2. With configuration '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Environment**
- AICA version: [e.g., 0.1.0]
- Python version: [e.g., 3.11.5]
- OS: [e.g., Ubuntu 22.04, macOS 14.0, Windows 11]
- LLM Provider: [Ollama / OpenRouter]
- Neo4j version: [if applicable]

**Logs** Debug logs (if available):
```

AICA_LOG_LEVEL=DEBUG aica [command] 2>&1 | tee debug.log

```

**Additional context**
Any other relevant information.
```

---

## Questions?

- **GitHub Discussions:** Ask questions and share ideas
- **GitHub Issues:** Report bugs or request features
- **Documentation:** Check [docs/](docs/) for detailed guides

---

Thank you for contributing to AICA!

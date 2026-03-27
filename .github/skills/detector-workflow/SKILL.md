---
name: detector-workflow
description: 'Complete workflow for creating, testing, and integrating repository scanner detectors in AICA. Use when: adding new detector, implementing detection logic, integrating with scanner, writing detector tests, following detector development best practices.'
argument-hint: 'Describe the detector to create (e.g., "middleware detector", "API routes detector")'
---

# Detector Development Workflow

Complete step-by-step guide for creating production-ready detectors in AICA's repository intelligence system.

## When to Use

- Adding a new detector for Next.js features (routes, components, hooks, middleware, etc.)
- Implementing detection logic for framework-specific patterns
- Integrating detectors into the scanner pipeline
- Following AICA detector conventions and best practices

## Prerequisites

- Understanding of the target feature to detect (Next.js routes, components, etc.)
- Familiarity with `pathlib.Path` and file system operations
- Basic knowledge of AICA's logging system

## Workflow Steps

### 1. Plan Detection Strategy

**Define what to detect:**

- What files/patterns indicate the feature exists?
- What metadata should be extracted?
- Should it return `list[dict]` (multiple items) or `dict` (singleton)?

**Example patterns:**

- Routes: `app/**/page.tsx`, `pages/**/*.tsx`
- Components: `components/**/*.tsx`, server/client components
- Middleware: `middleware.ts`, route-specific middleware
- Hooks: `use*.ts` files or hook exports

**Metadata to extract:**

- File paths (always relative to repo root)
- Type classifications (e.g., route type, component type)
- Configuration data (exports, metadata objects)
- Dependencies or imports

### 2. Create Detector File

**Location:** `aica/repo_intelligence/scanner/detectors/{name}.py`

**Template:**

```python
"""Detector for [feature description]."""

from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("detector.{name}")


class {Name}Detector:
    """Detect [feature] in a Next.js repository.

    Returns:
        list[dict]: List of detected [items] with metadata.
        Each dict contains:
        - path: Relative path from repo root
        - [other fields as needed]
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Scan repo_path and return [feature] metadata.

        Args:
            repo_path: Absolute path to repository root.

        Returns:
            List of dicts with detected [items].
        """
        log.info("detection.started", path=str(repo_path))

        results = []

        # Detection logic here
        # Use repo_path.rglob("pattern") for recursive search
        # Use Path.relative_to(repo_path) for relative paths

        log.debug("detection.completed", count=len(results))
        return results
```

**Critical conventions:**

- Logger name: `"detector.{name}"` (e.g., `"detector.middleware"`)
- Return relative paths: `str(file_path.relative_to(repo_path))`
- Always log start/completion with counts
- Handle missing files gracefully (return empty list, log warning)
- Never modify the repository

### 3. Implement Detection Logic

**Common patterns:**

```python
# Recursive glob for specific files
for file_path in repo_path.rglob("middleware.ts"):
    rel_path = str(file_path.relative_to(repo_path))
    results.append({"path": rel_path, "type": "middleware"})

# Check specific directories
app_dir = repo_path / "app"
if app_dir.exists():
    for page_file in app_dir.rglob("page.tsx"):
        # Extract route from file path
        route = str(page_file.parent.relative_to(app_dir))
        results.append({"path": str(page_file.relative_to(repo_path)), "route": route})

# Read file content for metadata
if file_path.exists():
    content = file_path.read_text(encoding="utf-8")
    # Parse exports, metadata, etc.
```

**Error handling:**

```python
try:
    content = file_path.read_text(encoding="utf-8")
except Exception as e:
    log.warning("file.read_failed", path=str(file_path), error=str(e))
    continue
```

### 4. Integrate with Scanner

**Location:** `aica/repo_intelligence/scanner/core.py`

**Add import:**

```python
from aica.repo_intelligence.scanner.detectors.{name} import {Name}Detector
```

**Add to `scan_repository()` function:**

```python
# [Feature] detection
{name}_detector = {Name}Detector()
structure["{name}s"] = {name}_detector.detect(repo_path)
log.debug("scan.{name}_completed", count=len(structure["{name}s"]))
```

**Verify integration:**

- Key name matches detector output type (plural for lists)
- Log message follows pattern: `"scan.{name}_completed"`
- Result is stored in the structure dict

### 5. Create Test File

**Location:** `tests/test_{name}_detector.py`

**Template:**

```python
"""Tests for {Name}Detector."""

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.{name} import {Name}Detector


def test_detector_finds_{items}(tmp_path: Path) -> None:
    """Test detector finds expected {items}."""
    # Setup: Create test files
    (tmp_path / "expected-file.ts").write_text("content")

    # Execute
    detector = {Name}Detector()
    result = detector.detect(tmp_path)

    # Assert
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["path"] == "expected-file.ts"


def test_detector_handles_missing_files(tmp_path: Path) -> None:
    """Test detector gracefully handles missing files."""
    detector = {Name}Detector()
    result = detector.detect(tmp_path)

    assert result == []  # Empty list for missing data


def test_detector_extracts_metadata(tmp_path: Path) -> None:
    """Test detector extracts correct metadata."""
    # Setup with specific content
    file_path = tmp_path / "test.ts"
    file_path.write_text("export default function() {}")

    # Execute
    detector = {Name}Detector()
    result = detector.detect(tmp_path)

    # Assert metadata fields
    assert result[0]["path"] == "test.ts"
    # Add assertions for other metadata fields
```

**Coverage requirements:**

- ✅ Finds expected items
- ✅ Handles missing files/directories
- ✅ Extracts correct metadata
- ✅ Returns correct data structure
- Aim for >80% code coverage

### 6. Run Tests

```bash
# Run specific test file
pytest tests/test_{name}_detector.py -v

# Check coverage
pytest tests/test_{name}_detector.py --cov=aica.repo_intelligence.scanner.detectors.{name} --cov-report=term-missing

# Run all tests
pytest tests/ -v
```

**Must pass before committing:**

- All tests pass
- Coverage >80%
- No linting errors: `ruff check aica/`
- Type checks pass: `mypy aica/`

### 7. Test Integration

**Manual testing:**

```bash
# Run full scan
aica scan-repo --verbose

# Check output
cat .repo_intelligence/{name}s.json
```

**Verify:**

- Output file exists and contains expected data
- Log messages appear with correct counts
- No errors or warnings in logs
- Relative paths are correct

### 8. Documentation

**Add example to detector docstring:**

```python
class {Name}Detector:
    """Detect [feature] in a Next.js repository.

    Example output:
        [
            {
                "path": "app/middleware.ts",
                "type": "global",
                ...
            }
        ]
    """
```

**Update relevant docs:**

- Add detector to `docs/extending.md` if documenting all detectors
- Update scanner documentation with new output field

## Quality Checklist

Before considering the detector complete:

- [ ] Detection logic follows existing detector patterns
- [ ] Returns correct data structure (`list[dict]` or `dict`)
- [ ] All paths are relative to repo root
- [ ] Logging uses structured format with logger name `"detector.{name}"`
- [ ] Handles missing files/directories gracefully
- [ ] Integrated into `scanner/core.py`
- [ ] Test file created with >80% coverage
- [ ] All tests pass
- [ ] No linting errors (`ruff check`)
- [ ] Type checks pass (`mypy`)
- [ ] Manual integration test successful
- [ ] Example output documented in docstring

## Common Pitfalls

❌ **Absolute paths in output:**

```python
results.append({"path": str(file_path)})  # Wrong!
```

✅ **Relative paths:**

```python
results.append({"path": str(file_path.relative_to(repo_path))})  # Correct
```

❌ **Using print() or stdlib logging:**

```python
print(f"Found {len(results)} items")  # Wrong!
```

✅ **Structured logging:**

```python
log.debug("detection.completed", count=len(results))  # Correct
```

❌ **Bare except clauses:**

```python
try:
    content = file.read_text()
except:  # Wrong!
    pass
```

✅ **Specific exceptions with logging:**

```python
try:
    content = file_path.read_text(encoding="utf-8")
except Exception as e:
    log.warning("file.read_failed", path=str(file_path), error=str(e))
    continue
```

## Related Resources

- [Existing Detectors](../../aica/repo_intelligence/scanner/detectors/) - Browse for patterns
- [Scanner Core](../../aica/repo_intelligence/scanner/core.py) - Integration examples
- [Test Examples](../../tests/) - Test patterns and fixtures
- [Coding Guidelines](../../.github/copilot-instructions.md) - AICA conventions

## Example Invocation

When you need to create a detector, invoke this skill:

```
/detector-workflow Create a detector for Next.js middleware files
```

The skill will guide you through all steps from planning to integration.

---
name: pre-release-checklist
description: 'Quality gates and validation checklist before releasing AICA features. Use when: preparing to commit, before creating PR, pre-merge validation, ensuring code quality, verifying all tests pass.'
argument-hint: 'Optional: specific area to validate (e.g., "detector changes", "new provider")'
---

# Pre-Release Checklist

Comprehensive quality gates to ensure code is ready for commit, PR, or release.

## When to Use

- Before committing changes to version control
- Before creating a pull request
- Before merging to main/master branch
- After completing any feature or bug fix
- When ensuring code meets AICA quality standards

## Quick Checklist

Run through this checklist before any commit or PR:

```bash
# 1. Run all tests
pytest tests/ -v

# 2. Check code coverage
pytest tests/ --cov=aica --cov-report=term-missing

# 3. Lint code
ruff check aica/

# 4. Format code
ruff format aica/

# 5. Type check
mypy aica/

# 6. Check for circular dependencies
pnpm run lint:circular  # If using pnpm
# OR manually check import structure

# 7. Verify no secrets in code
git diff | grep -E "(api_key|password|secret|token)" --color

# 8. Run integration tests (if applicable)
pytest tests/ -v -m integration
```

## Detailed Validation Steps

### 1. Test Validation

#### Run Unit Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_myfeature.py -v

# Tests for specific module
pytest tests/test_detector_*.py -v

# Stop on first failure (fast feedback)
pytest tests/ -x
```

**Expected output:**

```
========================= test session starts =========================
collected 247 items

tests/test_agent.py ....                                        [  2%]
tests/test_detector.py .....                                     [  4%]
...
========================= 247 passed in 12.34s ========================
```

**What to check:**

- ✅ All tests pass (no failures, no errors)
- ✅ No skipped tests (unless intentional)
- ✅ No warnings about deprecated APIs
- ✅ Test execution time is reasonable

#### Check Code Coverage

```bash
# Generate coverage report
pytest tests/ --cov=aica --cov-report=term-missing

# Generate HTML report for details
pytest tests/ --cov=aica --cov-report=html
# Then open htmlcov/index.html
```

**Target coverage:**

- New code: **>80% coverage required**
- Modified code: Should not decrease overall coverage
- Critical paths: **>90% coverage recommended**

**What to check:**

- ✅ New files have adequate test coverage
- ✅ Modified functions are tested
- ✅ Edge cases and error paths tested
- ✅ No untested critical code paths

#### Integration Tests

```bash
# Run integration tests (requires services running)
pytest tests/ -v -m integration

# Skip integration tests
pytest tests/ -v -m "not integration"
```

**What to check:**

- ✅ Database connections work (Neo4j, if applicable)
- ✅ External API calls succeed (with valid credentials)
- ✅ File system operations complete
- ✅ CLI commands execute successfully

### 2. Code Quality Validation

#### Linting

```bash
# Check for linting errors
ruff check aica/

# Fix auto-fixable issues
ruff check --fix aica/

# Check tests too
ruff check tests/
```

**Common issues to fix:**

- Unused imports
- Undefined variables
- Line too long (>88 chars for code, >120 for comments)
- Missing docstrings
- Incorrect import order

**Expected output:**

```
All checks passed!
```

#### Code Formatting

```bash
# Check if formatting is needed
ruff format --check aica/

# Apply formatting
ruff format aica/

# Format tests
ruff format tests/
```

**What to check:**

- ✅ Consistent indentation (4 spaces)
- ✅ Proper line breaks
- ✅ Sorted imports
- ✅ No trailing whitespace

#### Type Checking

```bash
# Run mypy on source code
mypy aica/

# Check specific module
mypy aica/core/llm/

# Strict mode (more thorough)
mypy --strict aica/
```

**What to fix:**

- Type hint errors
- Missing return type annotations
- Incompatible types
- Missing imports for types

**Expected output:**

```
Success: no issues found in 156 source files
```

### 3. Dependency Validation

#### Check Circular Dependencies

```bash
# If project uses pnpm
pnpm run lint:circular

# Manual check with pydeps (install if needed)
pip install pydeps
pydeps aica --show-cycles

# Check specific module
pydeps aica.core --show-cycles
```

**What to check:**

- ✅ No circular import chains
- ✅ Clean module hierarchy
- ✅ Proper separation of concerns

#### Verify Dependencies

```bash
# Check requirements are satisfied
pip check

# Verify pinned versions
pip list --format=freeze

# Check for security vulnerabilities
pip-audit  # Install with: pip install pip-audit
```

### 4. Security Validation

#### Check for Secrets

```bash
# Scan for common secret patterns
git diff | grep -E "(api_key|password|secret|token|AWS|sk-)" --color

# Check for hardcoded URLs (should use config)
git diff | grep -E "https?://" --color

# Verify .env files not committed
git status | grep ".env"
```

**What to verify:**

- ✅ No API keys in code
- ✅ No passwords or tokens
- ✅ No hardcoded credentials
- ✅ URLs come from configuration
- ✅ `.env` files are gitignored

#### Check Logging Safety

```bash
# Search for potential secret logging
grep -r "log.*api_key" aica/
grep -r "log.*password" aica/
grep -r "print(" aica/  # Should use structured logging
```

**What to fix:**

- No logging of API keys or secrets
- No `print()` statements (use `log` instead)
- Mask sensitive data in logs

### 5. Documentation Validation

#### Check Docstrings

```bash
# Verify docstrings exist
python -c "
import ast
import sys
from pathlib import Path

missing = []
for file in Path('aica').rglob('*.py'):
    if file.name.startswith('_') and file.name != '__init__.py':
        continue
    tree = ast.parse(file.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if not node.name.startswith('_') and not ast.get_docstring(node):
                missing.append(f'{file}:{node.name}')

if missing:
    print('Missing docstrings:')
    for item in missing[:10]:
        print(f'  - {item}')
    sys.exit(1)
"
```

**What to check:**

- ✅ All public classes have docstrings
- ✅ All public functions have docstrings
- ✅ Docstrings use Google style format
- ✅ Parameters and returns documented

#### Update Documentation

**Files to check:**

- `README.md` - Updated with new features
- `CHANGELOG.md` - Changes documented
- `docs/*.md` - Relevant docs updated
- Detector/provider examples added

### 6. Git Validation

#### Review Changes

```bash
# See what's changed
git status

# Review diff
git diff

# Check staged changes
git diff --staged

# View commit history
git log --oneline -n 5
```

**What to verify:**

- ✅ Only intended files modified
- ✅ No debug code left in
- ✅ No commented-out code (remove or document why)
- ✅ Commit message is descriptive

#### Commit Message Guidelines

**Format:**

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting changes
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**

```bash
git commit -m "feat(detector): add middleware detector for Next.js"

git commit -m "fix(llm): handle timeout errors in OpenRouter provider"

git commit -m "docs: update graph schema extension guide"

git commit -m "test: add integration tests for Neo4j client"
```

### 7. Build Validation

#### Test Clean Install

```bash
# Create fresh virtual environment
python -m venv test_env
source test_env/bin/activate  # Linux/Mac
# OR
test_env\Scripts\activate  # Windows

# Install package
pip install -e .

# Run tests
pytest tests/ -v

# Deactivate and cleanup
deactivate
rm -rf test_env
```

**What to verify:**

- ✅ Package installs without errors
- ✅ All dependencies resolve
- ✅ Tests pass in clean environment
- ✅ CLI commands work: `aica --help`

#### Test Entry Points

```bash
# Verify CLI is accessible
aica --help

# Test main commands
aica scan-repo --help
aica index-code --help
aica build-graph --help

# Smoke test (if repo available)
aica scan-repo --verbose
```

### 8. Performance Validation

#### Check Test Performance

```bash
# Run with timing info
pytest tests/ -v --durations=10

# Profile slow tests
pytest tests/ --profile
```

**What to check:**

- ✅ No tests taking >5 seconds (unless integration)
- ✅ Total test suite runs in reasonable time (<2 minutes for unit tests)
- ✅ No obvious performance regressions

#### Memory Usage

```bash
# Run with memory profiling (install memory_profiler)
python -m memory_profiler your_module.py

# Check for memory leaks in long-running operations
```

## Feature-Specific Checklists

### For New Detectors

- [ ] Detector file created in `aica/repo_intelligence/scanner/detectors/`
- [ ] Follows detector pattern (returns `list[dict]` or `dict`)
- [ ] Returns relative paths from repo root
- [ ] Uses structured logging with `get_logger("detector.name")`
- [ ] Handles missing files gracefully
- [ ] Integrated in `scanner/core.py`
- [ ] Test file created with >80% coverage
- [ ] Example output documented in docstring
- [ ] Manual testing completed

### For New LLM Providers

- [ ] Provider implements all four methods (generate, stream, async_generate, async_stream)
- [ ] Registered in `llm/factory.py`
- [ ] Settings added to `config/settings.py`
- [ ] Error handling for auth, connection, timeout
- [ ] Retry logic with exponential backoff
- [ ] API keys not logged
- [ ] Test file with unit and integration tests
- [ ] Environment variables documented

### For Graph Schema Changes

- [ ] Node/relationship types added to `schema.py`
- [ ] Node builder methods created
- [ ] Integrated with `graph_builder.py`
- [ ] Tests for node creation and relationships
- [ ] Manual testing with Neo4j Browser
- [ ] Example Cypher queries documented
- [ ] No duplicate nodes created

### For CLI Changes

- [ ] Command added to `interfaces/cli.py`
- [ ] Help text is clear and complete
- [ ] Arguments validated properly
- [ ] Error messages are user-friendly
- [ ] Logging shows progress
- [ ] Manual testing completed
- [ ] Documentation updated

## Automated Pre-Commit Hook

**Create `.git/hooks/pre-commit`:**

```bash
#!/bin/bash
set -e

echo "🔍 Running pre-commit checks..."

# 1. Run tests
echo "Running tests..."
pytest tests/ -x -q || { echo "❌ Tests failed"; exit 1; }

# 2. Lint
echo "Linting code..."
ruff check aica/ || { echo "❌ Linting failed"; exit 1; }

# 3. Format check
echo "Checking formatting..."
ruff format --check aica/ || { echo "❌ Formatting needed"; exit 1; }

# 4. Type check
echo "Type checking..."
mypy aica/ || { echo "❌ Type checking failed"; exit 1; }

# 5. Check for secrets
echo "Checking for secrets..."
if git diff --cached | grep -qE "(sk-|api_key.*=.*['\"][a-zA-Z0-9]{20,})"; then
    echo "❌ Possible secret detected in staged files"
    exit 1
fi

echo "✅ All checks passed! Proceeding with commit."
```

**Make executable:**

```bash
chmod +x .git/hooks/pre-commit
```

## Quality Gates for PR Approval

Before approving a PR, verify:

### Code Quality

- [ ] All tests pass in CI
- [ ] Code coverage >80% for new code
- [ ] No linting errors
- [ ] Type checking passes
- [ ] No circular dependencies

### Security

- [ ] No hardcoded secrets or credentials
- [ ] Sensitive data not logged
- [ ] Dependencies have no known vulnerabilities
- [ ] Input validation added where needed

### Documentation

- [ ] README updated (if public API changed)
- [ ] CHANGELOG.md updated
- [ ] Docstrings added for public APIs
- [ ] Example usage provided

### Testing

- [ ] Unit tests cover new functionality
- [ ] Edge cases tested
- [ ] Error paths tested
- [ ] Integration tests added (if applicable)

### Architecture

- [ ] Follows AICA conventions
- [ ] Proper use of logging (structlog)
- [ ] Type hints on all functions
- [ ] No violations of ABC patterns

## Common Issues and Fixes

### Tests Failing

```bash
# Run with verbose output
pytest tests/test_failing.py -vv

# Run with print statements visible
pytest tests/test_failing.py -s

# Drop into debugger on failure
pytest tests/test_failing.py --pdb

# Re-run only failed tests
pytest --lf
```

### Import Errors

```bash
# Verify package is installed in editable mode
pip install -e .

# Check PYTHONPATH
echo $PYTHONPATH

# Verify imports work
python -c "import aica; print(aica.__version__)"
```

### Type Checking Errors

```bash
# Show error context
mypy aica/ --show-error-context

# Ignore specific errors (temporary)
mypy aica/ --disable-error-code=<code>

# Check specific file
mypy aica/specific/file.py
```

## Related Resources

- [AICA Coding Guidelines](../../.github/copilot-instructions.md)
- [Testing Documentation](../../docs/testing.md)
- [Contributing Guide](../../CONTRIBUTING.md)
- [CI/CD Configuration](../../.github/workflows/)

## Example Invocation

```
/pre-release-checklist Validate changes before committing detector
```

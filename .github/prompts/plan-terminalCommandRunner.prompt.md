# Plan: Task 1.6 — Terminal Command Runner

**TL;DR**: Create `aica/execution/terminal/` submodule with a `TerminalRunner` class and `run_command()` convenience function. Reuses the existing `RunResult` dataclass (it already has `success`, `stdout`, `stderr`) and adds the missing pieces: timeout handling, structlog logging, and OS-level error wrapping.

---

## Phase 1 — Create submodule files

### 1. Create `aica/execution/terminal/runner.py` — core implementation

- Import `RunResult` from `aica.execution.runner` (reuse, no duplication)
- Import `get_logger` from `aica.core.logging.logger`
- `TerminalRunner` class with `__init__(timeout=60, cwd=None)` and `run(command, *, cwd=None, timeout=None) -> RunResult`
  - `subprocess.run(..., shell=True, capture_output=True, text=True, timeout=...)`
  - Catches `subprocess.TimeoutExpired` → returns `RunResult(returncode=-1, stderr="Command timed out after {n}s", ...)`
  - Catches broad `Exception` for OS-level failures → `RunResult(returncode=-1, ...)`
  - `structlog` logs: `info` for command/returncode, `warning` on timeout, `debug` for truncated stdout/stderr
- Module-level `run_command(command, *, timeout=60, cwd=None) -> RunResult` — one-liner wrapping `TerminalRunner`

### 2. Create `aica/execution/terminal/__init__.py`

- Exports: `run_command`, `TerminalRunner`, re-exports `RunResult`

---

## Phase 2 — Wire exports

### 3. Update `aica/execution/__init__.py`

- Add `TerminalRunner` and `run_command` to package exports alongside existing `ExecutionRunner`, `RunResult`

---

## Phase 3 — Tests

### 4. Create `tests/test_terminal_runner.py`

- `run_command("echo hello")` → `success=True`, stdout contains `"hello"`
- Failing command (`exit 1`) → `success=False`
- Mock `subprocess.run` raising `TimeoutExpired` → `success=False`, `"timed out"` in stderr
- `TerminalRunner` with explicit `cwd`

---

## Relevant files

- `aica/execution/runner.py` — `RunResult` and `ExecutionRunner` to reuse (not modify)
- `aica/execution/__init__.py` — update exports only
- `aica/core/logging/logger.py` — `get_logger(name)` pattern to follow

---

## Return shape

`RunResult` already satisfies the requirement:

```python
@dataclass
class RunResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0
```

Maps to:

```json
{
  "success": true,
  "stdout": "...",
  "stderr": "...",
  "command": "npm run build",
  "returncode": 0
}
```

---

## Decisions

- `shell=True` — intentional, matches existing codebase convention for dev-supplied commands
- Default timeout: `60s` — consistent with `llm_timeout=60` in settings, no new config field needed
- Sync (not async) — matches existing `ExecutionRunner` pattern in `execution/runner.py`
- `stdout`/`stderr` logged at `debug` level, truncated to 500 chars to avoid log bloat
- **Out of scope**: async variant, retry logic, command whitelisting

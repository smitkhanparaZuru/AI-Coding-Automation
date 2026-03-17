# Plan: Logging System (Task 1.4)

**TL;DR**: Create `aica/core/logging/logger.py` as the single source of truth. Absorb `setup_logging()` from the existing `aica/logging.py` (which becomes a shim). Add named `get_logger()` calls to all key modules using structlog's existing pipeline.

---

## Phase 1 — Core Logging Module

### Step 1 — Create `aica/core/logging/__init__.py`

Re-exports `get_logger` and `setup_logging` so callers can do `from aica.core.logging import get_logger`.

### Step 2 — Create `aica/core/logging/logger.py`

Two functions:

- `setup_logging(log_level, debug)` — moved verbatim from `aica/logging.py`. Keeps existing `structlog.configure()` with ConsoleRenderer (debug) / JSONRenderer (prod).
- `get_logger(name: str) -> structlog.stdlib.BoundLogger` — thin factory: `return structlog.get_logger(name)`. The `add_logger_name` processor already included in the pipeline surfaces `name` as `logger=` in every log line.

### Step 3 — Update `aica/logging.py` to a shim

Replace body with `from aica.core.logging.logger import get_logger, setup_logging`. No CLI import changes needed.

---

## Phase 2 — Instrumentation

### Step 4 — `aica/interfaces/cli.py`

- Module-level: `log = get_logger("cli")`
- Each command logs `cli.<command>.start` (with key args) and `cli.<command>.done` (with key result fields)

### Step 5 — `aica/repo_intelligence/analyzer.py`

- `log = get_logger("repo.analyzer")`
- `analyze()`: `analyze.start` (path) → `analyze.done` (file_count, is_git) at INFO; `analyze.path_not_found` at DEBUG

### Step 6 — `aica/repo_intelligence/indexer.py`

- `log = get_logger("repo.indexer")`
- `index()`: `index.start` → per-file `index.file` at DEBUG → `index.syntax_error` at WARNING → `index.done` at INFO with totals

### Step 7 — `aica/core/agent.py`

- `log = get_logger("agent")` as a class attribute on `BaseAgent` — subclasses inherit it automatically via `self.log`

### Step 8 — `aica/core/orchestrator.py`

- `log = get_logger("orchestrator")`
- `register()`: `agent.registered` (name) · `run()`: `task.dispatched` → `task.completed` → `agent.not_found` at ERROR before raise

### Step 9 — `aica/core/planner.py`

- `log = get_logger("planner")`
- `plan()`: `plan.created` (task, steps count) at INFO

---

## Files Changed

| File                                 | Action                          |
| ------------------------------------ | ------------------------------- |
| `aica/core/logging/__init__.py`      | NEW                             |
| `aica/core/logging/logger.py`        | NEW — absorbs `aica/logging.py` |
| `aica/logging.py`                    | Updated to thin shim            |
| `aica/interfaces/cli.py`             | Instrumented                    |
| `aica/repo_intelligence/analyzer.py` | Instrumented                    |
| `aica/repo_intelligence/indexer.py`  | Instrumented                    |
| `aica/core/agent.py`                 | `log` class attribute added     |
| `aica/core/orchestrator.py`          | Instrumented                    |
| `aica/core/planner.py`               | Instrumented                    |

---

## Verification

1. `aica status` — structured output appears with `logger=cli` field
2. `aica scan-repo` — `analyze.start` + `analyze.done` events
3. `aica index-code` — `index.start`, `index.file` (debug), `index.done`
4. `AICA_DEBUG=true aica status` — human-readable ConsoleRenderer
5. `pytest tests/` — all existing tests pass

---

## Key Decisions

- `get_logger(name)` is a pure thin wrapper — no `.bind()` needed, `add_logger_name` processor already in the pipeline
- `aica/logging.py` kept as a backward-compat shim — CLI import `from aica.logging import setup_logging` continues working unchanged
- No changes to the `structlog.configure()` pipeline
- Per-file debug logs in indexer are DEBUG-level only — no production noise

# Plan: AICA CLI Expansion (4 New Commands + Logging)

Add `scan-repo`, `index-code`, `plan-task`, and `run-task` to the existing `aica` CLI. Each command is a thin wrapper in `cli.py` that delegates to a dedicated service module. Logging via `structlog` is wired up in a Typer callback.

---

## Phase 1 — New Service Modules _(parallel, no dependencies)_

### 1. Create `aica/logging.py`

- Function `setup_logging(log_level: str, debug: bool) -> None` using `structlog`
- Configures stdlib integration, timestamped output
- Respects the `debug` flag for verbose formatting

### 2. Create `aica/repo_intelligence/indexer.py`

- Class `CodeIndexer` with method `index(path: Path) -> dict`
- `rglob("*.py")` to walk Python files, `ast.parse` to extract class/function names per file
- Counts: total files, total lines, total classes, total functions
- Creates `.aica/` dir inside the workspace, writes output to `.aica/index.json`
- Returns the full index dict

### 3. Create `aica/core/planner.py`

- Class `TaskPlanner` with method `plan(task: str) -> dict`
- Returns a deterministic stub:
  ```python
  {"task": task, "status": "planned", "steps": [...]}
  ```
- Steps (placeholder for future LLM): Analyse → Design → Implement → Verify → Document

---

## Phase 2 — Export Updates _(depends on Phase 1)_

### 4. Update `aica/repo_intelligence/__init__.py`

- Add `CodeIndexer` to exports

### 5. Update `aica/core/__init__.py`

- Add `TaskPlanner` to exports

---

## Phase 3 — Expand CLI _(depends on Phase 1 & 2)_

### 6. Update `aica/interfaces/cli.py`

**Callback**

- Add `@app.callback(invoke_without_command=True)` that loads settings and calls `setup_logging(settings.log_level, settings.debug)`

**`scan-repo` command**

- `--path` option (default: `settings.workspace_dir`)
- Calls `RepoAnalyzer().analyze(path)`
- Prints a rich Panel with repo metadata (path, exists, is_git, file_count)

**`index-code` command**

- `--path` option (default: `settings.workspace_dir`)
- Calls `CodeIndexer().index(path)`
- Prints a rich Table summary (files, lines, classes, functions)
- Confirms the `.aica/index.json` output path

**`plan-task` command**

- Positional argument: `task: str`
- Calls `TaskPlanner().plan(task)`
- Prints a rich Panel with the step list

**`run-task` command**

- Positional argument: `command: str`
- Optional `--cwd` option
- Calls `ExecutionRunner().run(command, cwd)`
- Prints stdout and stderr in rich Panels
- Colors exit code green (success) or red (failure)

---

## Phase 4 — Tests _(depends on Phase 3)_

### 7. Update `tests/test_cli.py`

| Test                             | Assertion                                                     |
| -------------------------------- | ------------------------------------------------------------- |
| `test_scan_repo_exits_zero`      | `exit_code == 0` with `["scan-repo", "--path", "."]`          |
| `test_scan_repo_shows_path`      | resolved path appears in output                               |
| `test_index_code_exits_zero`     | `exit_code == 0` with `["index-code", "--path", "."]`         |
| `test_index_code_creates_output` | `"index.json"` in output                                      |
| `test_plan_task_exits_zero`      | `exit_code == 0` with `["plan-task", "refactor auth module"]` |
| `test_plan_task_shows_steps`     | `"Implement"` in output                                       |
| `test_run_task_exits_zero`       | `exit_code == 0` with `["run-task", "echo hello"]`            |
| `test_run_task_shows_stdout`     | `"hello"` in output                                           |

---

## Relevant Files

| File                                 | Role                                                              |
| ------------------------------------ | ----------------------------------------------------------------- |
| `aica/interfaces/cli.py`             | Main CLI — add callback + 4 commands                              |
| `aica/repo_intelligence/analyzer.py` | `RepoAnalyzer.analyze()` — reused as-is                           |
| `aica/execution/runner.py`           | `ExecutionRunner.run()` — reused as-is                            |
| `aica/config/settings.py`            | `get_settings()` — provides `workspace_dir`, `log_level`, `debug` |
| `aica/repo_intelligence/__init__.py` | Update exports                                                    |
| `aica/core/__init__.py`              | Update exports                                                    |
| `tests/test_cli.py`                  | Add 8 new test cases                                              |

## New Files

- `aica/logging.py`
- `aica/repo_intelligence/indexer.py`
- `aica/core/planner.py`

---

## Verification

```bash
# All existing + 8 new tests pass
pytest tests/ -v

# All 5 commands listed with descriptions
aica --help

# Repo metadata in rich panel
aica scan-repo --path .

# Summary table printed, .aica/index.json created on disk
aica index-code --path .

# Structured plan stub displayed
aica plan-task "implement user auth"

# stdout shows hello
aica run-task "echo hello"

# No lint errors
ruff check aica/
```

---

## Out of Scope

- LLM integration (Phase 2 roadmap)
- Persistent task sessions
- Changes to `pyproject.toml` (Typer already declared in dependencies)
- Changes to the `version` command (already exists)

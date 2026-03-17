# Plan: Task 2.8 — CLI Integration (scan-repo)

Update the `aica scan-repo` command to run the full deep scanner, write all intelligence files, and display a concise Rich summary panel. Keep `scan-next` (detailed tables) unchanged.

---

## Phase 1: Update CLI command

**File:** `aica/interfaces/cli.py` — `scan_repo()` function (lines ~80–107)

Replace the body with:

1. Resolve target path (keep existing `--path` option + `settings.workspace_dir` fallback)
2. Call `scan_repository(str(target))` — same import already at top of file
3. Handle `"error" in data` → `console.print` + `raise typer.Exit(code=1)`
4. Write all 7 intelligence files via `OutputWriter().write(...)`:
   - `routes.json`, `components.json`, `services.json`, `database.json`, `packages.json`, `structure.json`, `repo_summary.json`
5. Generate summary with `RepoSummaryGenerator.from_scan_data(data)` (already imported)
6. Print Rich Panel titled "Repository scan complete" with a 2-col table:
   - Routes detected: `len(data["routes"])`
   - Components detected: `len(data["components"])`
   - Services detected: `len(data["services"])`
   - Database: `summary["database"] or "—"`
7. `log.info("cli.scan_repo.done", ...)` with counts

Remove the `RepoAnalyzer` import if it becomes unused (check other commands first; it's only used in scan_repo currently).

---

## Phase 2: Shared fixtures — conftest.py (new file)

**New file:** `tests/conftest.py`

Move `nextjs_repo` fixture from `tests/test_scanner.py` to `tests/conftest.py`. Pytest auto-discovers conftest.py — no imports needed in test files.

Remove `nextjs_repo` definition from `tests/test_scanner.py` (other fixtures `routes_repo`, `services_repo`, `empty_repo` stay in test_scanner.py since they're only used there).

---

## Phase 3: Update tests/test_cli.py

**File:** `tests/test_cli.py`

1. Update `test_scan_repo_exits_zero()`:
   - Add `nextjs_repo: Path` parameter (from conftest.py)
   - Pass `str(nextjs_repo)` as `--path` instead of `"."`

2. Update `test_scan_repo_shows_path()`:
   - Rename to `test_scan_repo_shows_summary_panel()`
   - Check `"scan complete"` or `"Routes detected"` in output (not "Path")

3. Add 4 new tests:
   - `test_scan_repo_shows_routes_count(nextjs_repo)` — "Routes detected" in output
   - `test_scan_repo_shows_components_count(nextjs_repo)` — "Components detected" in output
   - `test_scan_repo_writes_intelligence_files(nextjs_repo)` — verifies `structure.json` and `repo_summary.json` written to `nextjs_repo/.repo_intelligence/`
   - `test_scan_repo_error_on_missing_path()` — invoke with invalid path, check `exit_code == 1`

---

## Relevant files

- `aica/interfaces/cli.py` — replace `scan_repo()` body; remove `RepoAnalyzer` import if unused
- `aica/repo_intelligence/__init__.py` — check if `RepoAnalyzer` re-export is still needed elsewhere
- `tests/conftest.py` — NEW: `nextjs_repo` shared fixture
- `tests/test_scanner.py` — remove `nextjs_repo` fixture definition only
- `tests/test_cli.py` — update 2 existing tests + add 4 new tests

---

## Verification

1. `pytest tests/test_cli.py -v` — all tests pass, including 4 new
2. `pytest tests/test_scanner.py -v` — no regression (conftest fixture still works via auto-discovery)
3. `pytest tests/ -v` — full suite green
4. Manual: `aica scan-repo --path <nextjs-repo-path>` shows "Repository scan complete" panel with correct counts and writes `.repo_intelligence/*.json` files

---

## Decisions

- `scan-next` command retained unchanged (different audience — shows detailed tables with routes/components)
- Output: Rich Panel with a 2-col table (consistent with `status`, `index-code`, `summarize-repo`)
- `RepoAnalyzer` will be removed from `scan_repo()` and its import dropped if not used elsewhere
- No new settings — scanner uses `workspace_dir` as default path (same as current)

## Scope boundary

- Only `scan-repo` command is changed; `scan-next`, `summarize-repo`, and all other commands are untouched
- No LLM/AI involvement in scanning (pure static analysis, same as current `scan-next`)

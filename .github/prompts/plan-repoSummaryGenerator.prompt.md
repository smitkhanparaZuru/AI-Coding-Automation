# Plan: Task 2.7 — Repo Summary Generator

Generate a high-level `repo_summary.json` by combining the individual scanner
output files. Expose via `summarize-repo` CLI command and auto-generate at the
end of `scan-next`.

## Steps

### Phase 1 — Core Generator

1. Create `aica/repo_intelligence/scanner/summarizer.py`
   - `RepoSummaryGenerator` class with two public interfaces:
     - `generate(repo_path: Path) -> dict` — reads from existing
       `.repo_intelligence/*.json` files on disk (routes, components, services,
       database, structure). Writes `repo_summary.json` via `OutputWriter`.
     - `from_scan_data(scan_data: dict) -> dict` — classmethod; derives the same
       shape from an already-scanned in-memory dict (used by `scan-next`).
   - Output shape:
     ```
     {
       "framework": str,       # from structure.json / scan_data["framework"]
       "language": str,        # from structure.json / scan_data["language"]
       "routes_count": int,    # len(routes.json)
       "components_count": int,# len(components.json)
       "services_count": int,  # len(services.json)
       "database": str | null  # database.json[0]["orm"] or null
     }
     ```
   - Logger name: `"repo.scanner.summarizer"`
   - Gracefully handles missing JSON files (defaults to 0 / null / "unknown")
   - Uses `OutputWriter().write(summary, repo_path, "repo_summary.json")`

2. Update `aica/repo_intelligence/scanner/__init__.py`
   - Add `RepoSummaryGenerator` to imports and `__all__`

### Phase 2 — CLI Integration

3. Modify `aica/interfaces/cli.py`  
   a. **Auto-generation in `scan-next`**: After writing `pkg_path`, call
   `RepoSummaryGenerator.from_scan_data(data)` → write via `OutputWriter`
   → print saved path (mirrors how routes/components/services/database/packages
   are each printed after their `OutputWriter().write(...)` call)
   b. **New `summarize-repo` command**: reads existing JSON files from
   `.repo_intelligence/`, calls `RepoSummaryGenerator().generate(target)`,
   displays a Rich panel, prints saved path. Exits with code 1 if the
   `.repo_intelligence/` dir doesn't exist yet.

### Phase 3 — Tests

4. Create `tests/test_summarizer.py`
   - Fixture: minimal `.repo_intelligence/` dir with mock JSON files
     (routes, components, services, database, structure)
   - `test_generate_reads_json_files`: call `generate(repo_path)` → assert all
     fields correct
   - `test_generate_missing_files_graceful`: missing files yield zeros / null
   - `test_from_scan_data_classmethod`: call with sample dict → assert counts
   - `test_from_scan_data_no_database`: empty database list → `null`
   - `test_summarize_repo_cli_command`: use `CliRunner` to invoke `summarize-repo`
     with pre-populated `.repo_intelligence/` dir
   - `test_scan_next_auto_generates_summary`: invoke `scan-next` → assert
     `repo_summary.json` is written to `.repo_intelligence/`

## Relevant Files

- `aica/repo_intelligence/scanner/summarizer.py` — NEW
- `aica/repo_intelligence/scanner/__init__.py` — add export
- `aica/interfaces/cli.py` — add `summarize-repo` + auto-generate in `scan-next`
- `tests/test_summarizer.py` — NEW
- Reference: `aica/repo_intelligence/scanner/writers.py` — `OutputWriter.write()`
- Reference: `aica/interfaces/cli.py` lines ~200-260 — pattern for writing + printing each artifact

## Verification

1. `pytest tests/test_summarizer.py -v` — all new tests pass
2. `pytest tests/ -v` — no regressions in existing tests
3. Manual: `aica scan-next --path <nextjs-repo>` → `.repo_intelligence/repo_summary.json` created
4. Manual: `aica summarize-repo --path <nextjs-repo>` → summary panel printed, file written

## Decisions

- `database` field is `null` (Python `None` → JSON `null`) when no ORM detected
- Both `summarize-repo` command (reads from disk JSON) AND auto-generation in
  `scan-next` (in-memory) are implemented
- No extra top-level fields beyond the 6 in the example (framework, language,
  routes_count, components_count, services_count, database)

## Out of Scope

- Re-scanning the repo inside `summarize-repo` (reads existing JSON only)
- Adding package count or other fields beyond the example spec

# Plan: Phase 2 Task 2.1 — Repo Scanner Core

**TL;DR**: Build a `RepositoryScanner` at `aica/repo_intelligence/scanner/` that detects Next.js/TypeScript/App Router and maps source structure, writing `structure.json` to `.repo_intelligence/` inside the scanned repo. Add a `scan-next` CLI command. Wire in a `TsAstRunner` stub as the injection point for Phase 2.2 AST-based detectors.

---

## Steps

### Phase A — Module skeleton _(parallel)_

1. Create `aica/repo_intelligence/scanner/__init__.py` — exports `scan_repository`, `RepositoryScanner`
2. Create `aica/repo_intelligence/scanner/detectors/__init__.py` — empty package marker

### Phase B — Detectors _(parallel, no deps)_

3. Create **`detectors/framework.py`** — `FrameworkDetector.detect(repo_path: Path) -> dict`:
   - Reads `package.json` → finds `next` in deps/devDeps → extracts version
   - Checks `tsconfig.json` presence → `language: "TypeScript"`
   - Checks `src/app/` or `app/` for `page.tsx`/`layout.tsx` → `app_router: bool`
   - Detects package manager from lockfile: `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`
4. Create **`detectors/structure.py`** — `StructureDetector.detect(repo_path: Path) -> dict`:
   - Lists top-level dirs
   - Probes known src dirs (`app`, `components`, `lib`, `services`, `hooks`, `utils`, `types`, `store`, `features`, `db`) — in both root and `src/`
   - Detects config files: `tsconfig.json`, `next.config.{js,ts,mjs}`, `drizzle.config.ts`, `.env*`, `.eslintrc*`, `tailwind.config.*`

### Phase C — Core orchestrator _(depends on 3, 4)_

5. Create **`core.py`** — `RepositoryScanner.scan(repo_path: Path) -> dict` merges both detectors. Module-level `scan_repository(repo_path: str) -> dict` wraps it.

### Phase D — Output writer _(depends on 5)_

6. Create **`writers.py`** — `OutputWriter.write(data, repo_path, filename)` → writes to `{repo_path}/.repo_intelligence/{filename}` (JSON indent=2, creates dir)

### Phase E — TypeScript AST hook _(parallel with D)_

7. Create **`ts_ast.py`** — `TsAstRunner` stub: `is_available(repo_path)` checks `node` in PATH, `run_extractor(repo_path, script) -> dict | None` runs Node via subprocess. Not used in Task 2.1 — injection point for Phase 2.2 component/service detectors.

### Phase F — CLI integration _(depends on 5, 6)_

8. Add `scan-next` command to `aica/interfaces/cli.py`:
   - `--path` (optional, defaults to `settings.workspace_dir`)
   - Calls `scan_repository()` → `OutputWriter().write(data, path, "structure.json")`
   - Rich output: framework panel + src_structure table + config files table

### Phase G — Tests _(depends on all above)_

9. Create `tests/test_scanner.py` with `tmp_path` fixtures:
   - `test_detect_framework_nextjs()` — validates framework/version/language/app_router
   - `test_detect_framework_missing_package_json()` — graceful fallback
   - `test_detect_structure_src_prefix()` — validates `src/` prefix handling
   - `test_scan_repository_integration()` — full scan on fixture
   - `test_output_writer()` — validates JSON file written and parseable
   - `test_cli_scan_next()` — via Typer's `CliRunner`

---

## Output: `structure.json`

```json
{
  "framework": "Next.js",
  "language": "TypeScript",
  "app_router": true,
  "next_version": "16.x",
  "package_manager": "pnpm",
  "src_structure": {
    "app": "src/app/",
    "components": "src/components/",
    "services": "src/services/"
  },
  "config_files": {
    "package_json": "package.json",
    "tsconfig": "tsconfig.json",
    "next_config": "next.config.ts",
    "drizzle_config": "drizzle.config.ts",
    "env_files": [".env", ".env.local"]
  },
  "root_dirs": ["src", "public", ".github"]
}
```

---

## Relevant Files

| File                                                    | Action                                            |
| ------------------------------------------------------- | ------------------------------------------------- |
| `aica/repo_intelligence/scanner/__init__.py`            | Create                                            |
| `aica/repo_intelligence/scanner/core.py`                | Create — `RepositoryScanner`, `scan_repository()` |
| `aica/repo_intelligence/scanner/writers.py`             | Create — `OutputWriter`                           |
| `aica/repo_intelligence/scanner/ts_ast.py`              | Create — `TsAstRunner` stub                       |
| `aica/repo_intelligence/scanner/detectors/__init__.py`  | Create (empty)                                    |
| `aica/repo_intelligence/scanner/detectors/framework.py` | Create — `FrameworkDetector`                      |
| `aica/repo_intelligence/scanner/detectors/structure.py` | Create — `StructureDetector`                      |
| `aica/interfaces/cli.py`                                | Modify — add `scan-next` command                  |
| `tests/test_scanner.py`                                 | Create — full test suite                          |
| `aica/repo_intelligence/analyzer.py`                    | **Unchanged** — existing `scan-repo` preserved    |

---

## Decisions & Scope Boundaries

- **Included**: `structure.json` + framework detection only (Task 2.1)
- **Excluded now**: `routes.json`, `components.json`, `services.json`, `database.json`, `packages.json`, `repo_summary.json` — Phase 2.2+
- `TsAstRunner` is stubbed but not connected — provides the subprocess interface for Phase 2.2 AST detectors without blocking now
- `scan-repo` CLI command and `RepoAnalyzer` are **not touched**
- `package_manager` detection via lockfile presence (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, else npm)

---

## Further Consideration

The `TsAstRunner` for Phase 2.2 will need a bundled Node.js extractor script (e.g., a small `.js` in `aica/repo_intelligence/scanner/scripts/`). Should this be committed as a static asset, or generated on-the-fly? Worth deciding before Phase 2.2 begins.

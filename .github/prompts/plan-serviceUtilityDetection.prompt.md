# Plan: Task 2.4 — Service/Utility Detection

## TL;DR

Add a `ServiceDetector` that mirrors the existing `ComponentDetector` pattern. It scans `services/`, `lib/`, and `utils/` directories for `.ts`/`.tsx` files, extracts exported functions and class names using regex, and saves results to `.repo_intelligence/services.json`. Wire it into `RepositoryScanner`, `scan_next` CLI, and cover it with tests.

---

## Steps

### Phase 1 — New Detector

1. Create `aica/repo_intelligence/scanner/detectors/services.py`
   - Class `ServiceDetector` with `detect(repo_path: Path) -> list[dict]`
   - Scan dirs: `services/`, `lib/`, `utils/` (with `src/` prefix preference, same pattern as `_locate_tsx_files` in ComponentDetector)
   - File extensions: `.ts` and `.tsx` (use glob `**/*.ts` + `**/*.tsx`)
   - Regex to extract:
     - `service` name: from PascalCase class names (`export class AuthService`) OR stem of file titlecased (fallback)
     - `file`: relative posix path
     - `exported_functions`: list of all `export [async] function fnName(` and `export const fnName =` matches (camelCase or any valid identifier, not just PascalCase)
   - Output schema per entry:
     ```json
     {"service": "AuthService", "file": "services/auth.service.ts", "exported_functions": ["login", "logout"]}
     ```
   - Logger: `get_logger("repo.scanner.detectors.services")`

### Phase 2 — Wire into RepositoryScanner

2. Edit `aica/repo_intelligence/scanner/core.py`
   - Import `ServiceDetector`
   - Instantiate `self._services = ServiceDetector()` in `__init__`
   - Call `services_list = self._services.detect(repo_path)` in `scan()`
   - Add `"services": services_list` to the result dict
   - Add `services=len(services_list)` to the done log call

### Phase 3 — CLI Integration

3. Edit `aica/interfaces/cli.py` (the `scan_next` command)
   - After the components block: add a Services table (columns: `Service`, `File`, `Exported Functions`)
   - Write `services.json` via `OutputWriter().write(services, target, "services.json")`
   - Log + print path confirmation

### Phase 4 — Tests

4. Add tests to `tests/test_scanner.py` (or a new `tests/test_service_detector.py` — prefer existing file given pattern)
   - Fixture: service files in `services/`, `src/lib/`, `utils/`
   - Tests:
     - `test_service_detector_class_export` — class-based service name extracted
     - `test_service_detector_function_exports` — exported_functions list populated
     - `test_service_detector_src_prefix_preferred` — `src/services/` takes precedence
     - `test_service_detector_multiple_dirs` — both services/ and lib/ scanned
     - `test_service_detector_empty_repo` — returns []
     - `test_scan_repository_includes_services` — integration: `data["services"]` present
     - `test_cli_scan_next_writes_services_json` — CLI writes `.repo_intelligence/services.json`

---

## Relevant Files

- `aica/repo_intelligence/scanner/detectors/components.py` — template for `_locate_tsx_files`, `_extract_components`, `_make_entry` patterns
- `aica/repo_intelligence/scanner/detectors/routes.py` — template for http method regex (reuse function export regex style)
- `aica/repo_intelligence/scanner/core.py` — add `ServiceDetector` wiring
- `aica/interfaces/cli.py` — add services table + `OutputWriter` call in `scan_next`
- `tests/test_scanner.py` — add new test cases here

## New File

- `aica/repo_intelligence/scanner/detectors/services.py` (create)

---

## Verification

1. Run `pytest tests/test_scanner.py -v` — all new tests pass, no regressions
2. Run `pytest tests/ -v` — full suite passes
3. Manually verify output schema matches `{"service": "...", "file": "...", "exported_functions": [...]}`
4. Check `.repo_intelligence/services.json` is written by `scan-next` CLI

---

## Decisions

- Scan dirs: `services/`, `lib/`, `utils/` (as specified in task)
- Service name: first exported class name (PascalCase), fallback to file stem titlecased
- Exported functions: all named non-PascalCase exports (function or const arrow) — distinguishes services from components
- File extensions: `.ts` and `.tsx` (lib/utils may have `.tsx` helper components)
- Deduplication: keyed by `(service_name, file)` to avoid duplicates
- src/ prefix: same precedence logic as ComponentDetector — `src/<dir>` wins over `<dir>`

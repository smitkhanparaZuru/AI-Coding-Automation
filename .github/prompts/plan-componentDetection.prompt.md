# Task 2.3 — Component Detection

## Overview

Add a regex-based `ComponentDetector` that scans `components/` and `app/**/` for exported React function components, extracts name + file + props, and writes `.repo_intelligence/components.json`. Wired into `RepositoryScanner` and the `scan-next` CLI command.

## Decisions

- `props` is always present — `[]` when none detectable (consistent schema)
- App dir scope: ALL `.tsx` files included (page, layout, error, etc. are all components)
- CLI: `scan-next` extended to display a components table + write `components.json`
- Regex-only approach — consistent with all existing detectors; no Node.js required

---

## Phase 1 — `ComponentDetector` _(new file, independent)_

**1.** Create `aica/repo_intelligence/scanner/detectors/components.py` with class `ComponentDetector`:

- `detect(repo_path: Path) -> list[dict]` — main entry point
- `_locate_tsx_files(repo_path)` — globs `*.tsx` from `components/` (src-prefixed or root) **and** `app/` (src-prefixed or root)
- `_extract_components(file_path, repo_path)` — parses a single file for all exported components
- `_extract_props(content, component_name)` — extracts prop names from the matched interface/type

Regex patterns inside the module:

- `_RE_NAMED_EXPORT_FN` — `export [default] function ComponentName(`
- `_RE_CONST_EXPORT` — `export const ComponentName [: React.FC<...>] = (`
- `_RE_LOCAL_FN_DECL` — local `function ComponentName(` to pair with a later `export default ComponentName`
- `_RE_DEFAULT_EXPORT_ID` — `export default ComponentName`
- `_RE_PROPS_INTERFACE` — `interface ComponentNameProps { ... }` (DOTALL)
- `_RE_PROPS_TYPE` — `type ComponentNameProps = { ... }` (DOTALL)
- `_RE_PROP_NAME` — individual prop names within interface/type body

**Component name rule**: first character uppercase (PascalCase = React component). Any export containing a lowercase-start identifier is skipped.

Output shape per component:

```json
{ "name": "UserCard", "file": "src/components/UserCard.tsx", "props": ["userId", "name"] }
```

---

## Phase 2 — Wire into `RepositoryScanner` _(depends on Phase 1)_

**2.** Modify `aica/repo_intelligence/scanner/core.py`:

- Import `ComponentDetector`; add `self._components = ComponentDetector()` in `__init__`
- In `scan()`, call `components_list = self._components.detect(repo_path)` and add `"components": components_list` to the merged result dict
- Add `components=len(components_list)` to the done log

---

## Phase 3 — `OutputWriter` type hint fix _(independent)_

**3.** Modify `aica/repo_intelligence/scanner/writers.py`:

- Change `write(self, data: dict, ...)` to `data: dict | list` — routes already passes a list; make the type honest

---

## Phase 4 — CLI `scan-next` integration _(depends on Phase 2)_

**4.** Modify `aica/interfaces/cli.py` in `scan_next()`:

- Extract `components = data.get("components", [])` from scan result
- Add Rich table (columns: `Name`, `File`, `Props`) using the same pattern as the routes table (lines 244–261)
- Call `OutputWriter().write(components, target, "components.json")` and print the path

---

## Phase 5 — Tests _(new file, finalize after all phases)_

**5.** Create `tests/test_component_detector.py`:

| Test                                            | What it covers                                              |
| ----------------------------------------------- | ----------------------------------------------------------- |
| `test_detect_named_export_function_component`   | `export function UserCard(` → found                         |
| `test_detect_default_export_function_component` | `export default function Hero(` → found                     |
| `test_detect_arrow_function_component`          | `export const Button = (` → found                           |
| `test_detect_default_export_of_identifier`      | `function Card() {}; export default Card;` → found          |
| `test_detect_ignores_lowercase_name`            | `export function helper()` → not a component                |
| `test_detect_props_from_interface`              | `interface UserCardProps { id: string; }` → `props: ["id"]` |
| `test_detect_props_always_empty_list_when_none` | no detectable props → `props: []`                           |
| `test_detect_scans_components_dir`              | file in `src/components/` is found                          |
| `test_detect_scans_app_dir`                     | file nested in `src/app/` is found                          |
| `test_detect_empty_repo`                        | no tsx files → returns `[]`                                 |
| `test_detect_multiple_components_in_file`       | two exports in one file → two entries                       |
| `test_cli_scan_next_writes_components_json`     | end-to-end CLI test via `CliRunner`                         |

---

## Relevant Files

- `aica/repo_intelligence/scanner/detectors/components.py` — **CREATE** (primary)
- `aica/repo_intelligence/scanner/core.py` — add `ComponentDetector`, wire into `scan()`
- `aica/repo_intelligence/scanner/writers.py` — update `write()` type hint
- `aica/interfaces/cli.py` — extend `scan_next()` (follow routes table pattern, lines 244–261)
- `tests/test_component_detector.py` — **CREATE**

## Verification

1. `pytest tests/test_component_detector.py -v` — all new tests green
2. `pytest tests/ -v` — no regressions in existing suite
3. `aica scan-next --path <nextjs-repo>` — Components panel shown, `components.json` written
4. Inspect `.repo_intelligence/components.json` — bare list of `{name, file, props}` objects

## Exclusions

- No TypeScript AST / Node.js bridge
- No JSX return-value analysis
- No new abstractions beyond the detector class itself

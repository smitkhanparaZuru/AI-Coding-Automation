# Plan: Task 2.6 — Dependency Analysis

**TL;DR:** Add a new `PackageDetector` that reads `package.json` and classifies all deps into 5 buckets (framework, ui, database, auth, state). Wire it into the existing `RepositoryScanner` pipeline so `scan-next` also writes `.repo_intelligence/packages.json`.

---

## Steps

### Phase 1 — `PackageDetector` (new file, self-contained)

1. Create `aica/repo_intelligence/scanner/detectors/packages.py`
   - Class `PackageDetector` with `detect(repo_path: Path) -> dict`
   - Reads all 3 dep sections from `package.json` (same approach as `database.py` — `dependencies`, `devDependencies`, `peerDependencies`)
   - Maintains 5 catalog sets (prefix-matched for scoped packages like `@radix-ui/*`):
     - **FRAMEWORK**: `next`, `react`, `vue`, `nuxt`, `svelte`, `remix`, `astro`, `gatsby`, `@angular/core`
     - **UI**: `tailwindcss`, `@mui/material`, `antd`, `@chakra-ui/react`, `@mantine/core`, `@radix-ui/`, `framer-motion`, `styled-components`, `@emotion/react`, `shadcn-ui`
     - **DATABASE**: `@prisma/client`, `prisma`, `drizzle-orm`, `mongoose`, `typeorm`, `sequelize`, `pg`, `mysql2`, `better-sqlite3`, `@planetscale/database`, `@vercel/postgres`
     - **AUTH**: `next-auth`, `@auth/core`, `@clerk/nextjs`, `lucia`, `@supabase/auth-helpers-nextjs`, `firebase-admin`, `passport`
     - **STATE**: `zustand`, `redux`, `@reduxjs/toolkit`, `jotai`, `recoil`, `mobx`, `valtio`, `@tanstack/react-query`, `swr`, `xstate`
   - `framework` → single string (first match) or `null`; all others → sorted list of matched package names
   - Missing/corrupt `package.json` → returns empty structure gracefully
   - Output: `{"framework": "next", "ui": [...], "database": [...], "auth": [...], "state": [...]}`

### Phase 2 — Register in `core.py` _(depends on Phase 1)_

2. Import `PackageDetector` in `aica/repo_intelligence/scanner/core.py`
3. Add to `RepositoryScanner.__init__` and call `detect()` in `scan()` — merge under key `"packages"` in the returned dict

### Phase 3 — CLI output _(depends on Phase 2)_

4. In `aica/interfaces/cli.py` `scan-next`:
   - Write `packages.json` via existing `OutputWriter` (same pattern as `database.json`, `routes.json`)
   - Add a Rich panel/table displaying the packages summary

### Phase 4 — Tests _(parallel with 1–3, finalize after)_

5. Create `tests/test_package_detector.py` with fixtures:
   - `empty_repo` (no `package.json`), `nextjs_pkg_repo` (full stack), `react_only_repo`, `corrupt_json_repo`, `devdeps_repo`
   - Unit tests per category + missing file + devDeps coverage
   - Integration: `scan_repository()` returns `"packages"` key
   - CLI: `scan-next` writes `packages.json` with correct schema

---

## Relevant Files

- `aica/repo_intelligence/scanner/detectors/packages.py` — **NEW** (main)
- `aica/repo_intelligence/scanner/detectors/database.py` — reference for `package.json` reading pattern
- `aica/repo_intelligence/scanner/core.py` — add `PackageDetector` registration
- `aica/interfaces/cli.py` — add `packages.json` write + display
- `aica/repo_intelligence/scanner/writers.py` — reused as-is
- `tests/test_package_detector.py` — **NEW** test file

---

## Verification

1. `pytest tests/test_package_detector.py -v` — all new tests pass
2. `pytest tests/ -v` — no regressions
3. Manual: `aica scan-next --path <repo>` → `.repo_intelligence/packages.json` matches example schema
4. `ruff check aica/` and `mypy aica/` — clean

---

## Decisions

- `framework` is a **single string** (first match wins), matching the example output; `null` if none detected
- Package name is the **raw npm name** (`"next"` not `"Next.js"`)
- All 5 keys always present in output, even if empty list/null
- `"state"` key is included (mentioned in requirements; follows same pattern as other array fields)
- Reads `dependencies` + `devDependencies` + `peerDependencies` — consistent with `database.py`

---

## Further Considerations

1. **`@radix-ui/` prefix matching**: Many projects install individual `@radix-ui/react-*` packages. The detector should treat any package starting with `@radix-ui/` as a UI library hit, rather than listing each one individually. Should we collapse them to a canonical `"@radix-ui"` entry or list each? Recommendation: **collapse to `"@radix-ui"`** to keep output compact.
2. **`"framework"` overlap with `FrameworkDetector`**: The existing `FrameworkDetector` already detects the framework and writes it to `structure.json`. The new `packages.json` will have a `framework` field too but with the raw package name (`"next"` vs `"Next.js"`). This is intentional — `packages.json` is dependency-focused with raw npm names. No concerns unless consumers expect consistency.

# Plan: Task 2.2 — Next.js Route Detection

**TL;DR**: Add a `RouteDetector` that walks `app/` (or `src/app/`), classifies `page.tsx`/`route.ts` files into typed route records, extracts HTTP methods via Python regex, and handles all Next.js routing conventions. The existing `scan-next` command writes results to `.repo_intelligence/routes.json` and displays a Rich table.

---

## Steps

### Phase 1 — `RouteDetector` (new file)

1. Create `aica/repo_intelligence/scanner/detectors/routes.py` — class `RouteDetector` with a single `detect(repo_path: Path) -> list[dict]` method
2. Locate app dir: probe `src/app/` first, then `app/` (mirrors pattern in `FrameworkDetector`)
3. Glob `**/page.tsx` → `type: "page"`, glob `**/route.ts` → `type: "api"`
4. **Path-to-route algorithm** — for each matched file, compute URL from path segments relative to app dir, classifying each segment:
   - `@slot` → `type: "parallel"`, `slot: "@modal"`, _skip from URL_
   - Matches `^(\(\.+\))+(.+)$` (intercepted route prefix) → `type: "intercepted"`, use captured tail as URL segment
   - Matches `^\([^)]+\)$` (route group) → _skip from URL_
   - Everything else → add to URL as-is (including `[param]`, `[...slug]`)
5. **HTTP method extraction** (route.ts only) — regex scan on raw file content for two patterns:
   - `export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b`
   - `export\s+const\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*=`
   - Deduplicate, sort in canonical order: `GET → POST → PUT → PATCH → DELETE → HEAD → OPTIONS`

### Phase 2 — `RepositoryScanner` integration _(depends on Phase 1)_

6. In `core.py`: instantiate `RouteDetector` in `__init__`, call `self._routes.detect(repo_path)` in `scan()`, add `"routes": routes_list` to the result dict, extend the `scanner.done` log to include `routes=len(routes_list)`

### Phase 3 — CLI update _(depends on Phase 2)_

7. In `cli.py` `scan_next()`: after the config-files table, extract routes from `data["routes"]`, render a Rich table with columns **Route | Type | Methods | File**, call `OutputWriter().write(routes, target, "routes.json")`, and print the output path

### Phase 4 — Tests _(finalise after Phases 1–3)_

8. Add `routes_repo` fixture to `tests/test_scanner.py` creating:
   - `src/app/page.tsx`, `src/app/dashboard/page.tsx` — simple pages
   - `src/app/(auth)/login/page.tsx` — route group (stripped)
   - `src/app/users/[id]/page.tsx` — dynamic segment
   - `src/app/@modal/photo/[id]/page.tsx` — parallel route slot
   - `src/app/feed/(.)photo/[id]/page.tsx` — intercepted route
   - `src/app/api/users/route.ts` (exports GET + POST), `src/app/api/posts/route.ts` (exports GET)
9. Add 9 test cases covering each route type, method extraction, empty-dir graceful handling, and CLI end-to-end (routes.json written + table displayed)

---

## Relevant Files

| File                                                 | Action                                         |
| ---------------------------------------------------- | ---------------------------------------------- |
| `aica/repo_intelligence/scanner/detectors/routes.py` | NEW — `RouteDetector`                          |
| `aica/repo_intelligence/scanner/core.py`             | EDIT — add `RouteDetector`, log routes count   |
| `aica/interfaces/cli.py`                             | EDIT — routes Rich table + `routes.json` write |
| `tests/test_scanner.py`                              | EDIT — new fixture + 9 test cases              |

---

## Output Schema

```json
[
  {
    "route": "/dashboard",
    "type": "page",
    "file": "app/dashboard/page.tsx"
  },
  {
    "route": "/api/users",
    "type": "api",
    "methods": ["GET", "POST"],
    "file": "app/api/users/route.ts"
  },
  {
    "route": "/",
    "type": "parallel",
    "slot": "@modal",
    "file": "app/@modal/page.tsx"
  },
  {
    "route": "/photo/[id]",
    "type": "intercepted",
    "file": "app/feed/(.)photo/[id]/page.tsx"
  }
]
```

---

## Verification

1. `pytest tests/test_scanner.py -v` — all existing + new tests pass (no regressions)
2. `aica scan-next --path <nextjs-repo>` — routes table appears in terminal, `.repo_intelligence/routes.json` is created
3. Inspect `routes.json` — each entry matches the schema from the task spec
4. Manually verify route groups are stripped, `[id]` is preserved, `@modal` emits `type: "parallel"`

---

## Decisions

- Dynamic segments stay as Next.js style (`/users/[id]`, not `/users/:id`)
- `scan-next` extended (no new command) → writes both `structure.json` and `routes.json`
- Routes stored under `"routes"` key in scanner result but written to a _separate_ `routes.json` (not merged into `structure.json`)
- HTTP methods extracted via pure Python regex — no Node.js subprocess
- Parallel routes (`@slot`) and intercepted routes (`(.)prefix`) are detected per user choice

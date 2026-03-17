# Task 2.5 — Database Layer Detection

Add a `DatabaseDetector` that identifies Prisma, Drizzle, and TypeORM from `package.json` deps, extracts models (with fields), and writes a **list of dicts** (one per ORM) to `.repo_intelligence/database.json`.

---

## Steps

### Phase 1 — Detector

1. **Create `aica/repo_intelligence/scanner/detectors/database.py`**
   - `DatabaseDetector.detect(repo_path) -> list[dict]` — one entry per detected ORM
   - Three private methods: `_detect_prisma()`, `_detect_drizzle()`, `_detect_typeorm()`
   - Regex-based extraction for all three ORMs. Extraction per ORM:
     - **Prisma**: parse `prisma/schema.prisma` for `model Name { ... }` blocks → field names via `^\s+(\w+)\s+\w+` (skipping `@@` directives)
     - **Drizzle**: scan `db/`, `drizzle/`, `src/db/`, `src/drizzle/` for `.ts` files; find `pgTable|mysqlTable|sqliteTable` calls; use brace-counting (same pattern as `ComponentDetector._find_props_body`) to extract field keys
     - **TypeORM**: scan `src/entities/`, `src/entity/`, `entities/` for `@Entity()` classes; extract `@Column`/`@PrimaryColumn`/`@PrimaryGeneratedColumn` decorated fields
   - Output per entry:
     ```json
     { "orm": "Prisma", "schema": "prisma/schema.prisma", "models": [{"name": "User", "fields": ["id", "email"]}] }
     ```
   - Returns `[]` if nothing detected. Logger: `get_logger("repo.scanner.detectors.database")`

### Phase 2 — Wire into `core.py` (depends on Phase 1)

2. **Modify `aica/repo_intelligence/scanner/core.py`**
   - Import + instantiate `DatabaseDetector`
   - Call `database_list = self._database.detect(repo_path)` and add `"database": database_list` to result
   - Add `database=len(database_list)` to the `log.info("scanner.done", ...)` call

### Phase 3 — CLI (depends on Phase 2)

3. **Modify `aica/interfaces/cli.py`** (`scan_next` command, after services section)
   - Render a Rich table: columns `ORM`, `Schema`, `Models`
   - Write `OutputWriter().write(database, target, "database.json")`

### Phase 4 — Tests (parallel with Phase 1–3)

4. **Create `tests/test_database_detector.py`**
   - Fixtures: `prisma_repo`, `drizzle_repo`, `typeorm_repo`, `empty_repo`
   - Tests: no-ORM empty list, Prisma/Drizzle/TypeORM detection, model+field extraction, multi-ORM, integration (`scan_repository` includes `"database"` key), CLI writes `database.json`

---

## Relevant Files

- `aica/repo_intelligence/scanner/detectors/database.py` — **CREATE** (new detector)
- `aica/repo_intelligence/scanner/detectors/components.py` — reference brace-counting pattern for Drizzle field extraction
- `aica/repo_intelligence/scanner/core.py` — wire up detector
- `aica/interfaces/cli.py` — display panel + write output
- `tests/test_database_detector.py` — **CREATE** (new test file)

---

## Decisions

- **Output is a list** to support multi-ORM repos — one dict per detected ORM
- **Names + fields** extracted per model
- Supported ORMs: **Prisma, Drizzle, TypeORM** only
- `schema` for TypeORM is `null` (entities are scattered, no single schema file)
- `schema` for Drizzle = the config file path (e.g. `drizzle.config.ts`)
- **Package.json deps are authoritative** — directory heuristics only used if a matching dep is found first (no false positives)

---

## Expected Output Schema

```json
[
  {
    "orm": "Prisma",
    "schema": "prisma/schema.prisma",
    "models": [
      {"name": "User", "fields": ["id", "email", "name"]},
      {"name": "Post", "fields": ["id", "title", "authorId"]}
    ]
  },
  {
    "orm": "Drizzle",
    "schema": "drizzle.config.ts",
    "models": [
      {"name": "users", "fields": ["id", "email", "name"]},
      {"name": "posts", "fields": ["id", "title", "userId"]}
    ]
  },
  {
    "orm": "TypeORM",
    "schema": null,
    "models": [
      {"name": "User", "fields": ["id", "email", "name"]},
      {"name": "Post", "fields": ["id", "title", "authorId"]}
    ]
  }
]
```

---

## Verification

1. `pytest tests/test_database_detector.py -v` — all new tests pass
2. `pytest tests/test_scanner.py -v` — no regressions
3. `pytest tests/ -v` — full suite green
4. `aica scan-next --path <prisma-repo>` shows Database panel and writes `database.json`
5. Confirm `.repo_intelligence/database.json` is valid JSON with correct schema

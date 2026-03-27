# Phase 4 — Dependency Graph (Neo4j): Full Design

## What We're Actually Building

The existing pipeline produces 7 flat JSON files (imports, functions, calls, exports, hooks, components, types) + scanner data (routes, services, stores). Phase 4 ingests all of this and writes it into a **live Neo4j graph** where every node is a code entity and every edge is a code relationship — making the entire codebase queryable in O(1) graph hops instead of scanning files.

---

## Enhancements to the Original Proposal

These go beyond what was described and make the system significantly more powerful:

**Architecture additions:**

1. **`GraphQueryEngine`** — A query API layer on top of Neo4j that the AI agent can call directly (not raw Cypher). Methods like `find_change_impact(file)`, `find_call_chain(from_fn, to_fn)`, `most_called_functions()`. This is what makes it repo-aware AI.
2. **`USES_HOOK` relationship** — Currently the proposal only has `CALLS`. React hooks are a distinct relationship type that enables "find all components using `useAuth`" queries.
3. **Dead export detection** — Exports that are never imported anywhere. Cypher is perfect for this: `MATCH (e:Export) WHERE NOT ()-->(e) RETURN e`. Invaluable for cleanup.
4. **Circular import detection** — Cypher's path-finding handles this natively. Catching these prevents runtime errors.
5. **Batch `MERGE` operations** — Not inserting one node at a time. Group by type, send batches of 500. Critical for repos with 10k+ functions.
6. **`GraphSummary` dataclass** — The pipeline returns a structured object, not just a printout. Other code (AI agents, CLI) can consume the counts programmatically.
7. **Both local + cloud Neo4j** — URI scheme determines behavior: `bolt://` for local Docker, `neo4j+s://` for AuraDB. One env var change, no code change.
8. **Incremental rebuild** — Clear only nodes belonging to a specific file, then re-insert. Avoids rebuilding the entire graph on every small file change.

**New node types beyond original:**

- `Hook` — distinct from Function, enables hook-specific queries
- `Module` — external packages (react, lodash) as their own nodes
- `Route` — Next.js routes from scanner data
- `Service` — backend service modules from scanner data
- `Store` — Zustand stores from scanner data

**New relationship types beyond original:**

- `USES_HOOK` — Component/Function → Hook
- `HAS_ROUTE` — File → Route
- `HAS_STORE` — File → Store
- `BELONGS_TO` — Service/Store → File (reverse direction for traversal)

---

## Graph Schema

```
File ──IMPORTS──▶ File (internal) / Module (external)
File ──DEFINES──▶ Function / Component / Type / Hook
Function ──CALLS──▶ Function
Component ──USES_HOOK──▶ Hook
File ──HAS_ROUTE──▶ Route
File ──HAS_STORE──▶ Store
```

---

## Folder Result

```
aica/memory/graph_store/
  __init__.py
  neo4j_client.py      ← 4.1
  schema.py            ← 4.2
  node_builder.py      ← 4.3
  import_builder.py    ← 4.4
  call_builder.py      ← 4.5
  scanner_builder.py   ← 4.6
  graph_builder.py     ← 4.7 (pipeline)
  queries.py           ← 4.8 (AI query API)
```

---

## Sub-Plans (implement in order)

Each sub-plan is a self-contained implementation unit. After each one is approved, it is planned + implemented separately before moving to the next.

---

### Sub-Plan 4.1 — Neo4j Client + Settings

**New files:**

- `aica/memory/graph_store/__init__.py`
- `aica/memory/graph_store/neo4j_client.py`
  - `Neo4jClient(uri, user, password, database)` — reads from `get_settings()` if not passed
  - `connect()` — verifies connectivity
  - `close()` — tears down driver
  - `run_query(cypher: str, params: dict) -> list[dict]`
  - `run_batch(queries: list[tuple[str, dict]]) -> None` — single transaction
  - Context manager: `__enter__` / `__exit__`
  - Transaction wrapper: `with_transaction(fn)`
  - Error hierarchy: `GraphConnectionError`, `GraphQueryError`, `GraphAuthError`
- `tests/test_neo4j_client.py` — mock `neo4j` driver, test connect/query/error paths

**Settings additions** (`aica/config/settings.py`):

- `neo4j_uri: str` → `AICA_NEO4J_URI` (default `bolt://localhost:7687`)
- `neo4j_user: str` → `AICA_NEO4J_USER` (default `neo4j`)
- `neo4j_password: SecretStr` → `AICA_NEO4J_PASSWORD`
- `neo4j_database: str` → `AICA_NEO4J_DATABASE` (default `neo4j`)

**URI scheme behavior:**

- `bolt://` → local Docker, no TLS
- `neo4j+s://` → AuraDB cloud, TLS enforced by driver

---

### Sub-Plan 4.2 — Graph Schema & Constraints

**New file:** `aica/memory/graph_store/schema.py`

```python
class NodeLabel(str, Enum):
    FILE = "File"
    FUNCTION = "Function"
    COMPONENT = "Component"
    HOOK = "Hook"
    TYPE = "Type"
    MODULE = "Module"      # external packages
    ROUTE = "Route"
    SERVICE = "Service"
    STORE = "Store"

class RelType(str, Enum):
    IMPORTS = "IMPORTS"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
    EXPORTS = "EXPORTS"
    USES_HOOK = "USES_HOOK"
    HAS_ROUTE = "HAS_ROUTE"
    HAS_STORE = "HAS_STORE"
    BELONGS_TO = "BELONGS_TO"
```

- `CONSTRAINT_QUERIES` — `CREATE CONSTRAINT IF NOT EXISTS` for each node type's natural key
  - `File.path` (unique)
  - `Function.id` = `"{file}::{name}::{line}"` (unique)
  - `Component.id` = `"{file}::{name}"` (unique)
  - `Hook.name` (unique)
  - `Module.name` (unique)
  - `Route.route` (unique)
  - `Store.store` (unique)
- `setup_schema(client: Neo4jClient)` — runs all constraints idempotently
- `tests/test_graph_schema.py`

---

### Sub-Plan 4.3 — File, Function, Component, Type, Hook Nodes

**New file:** `aica/memory/graph_store/node_builder.py`

Builders (all use batched `MERGE` of 500 at a time):

- `build_file_nodes(client, functions, components, types, hooks)` — creates unique `File` nodes from all entity lists
- `build_function_nodes(client, functions: list[dict])` — creates `Function` nodes + `DEFINES` edges
- `build_component_nodes(client, components: list[dict])` — creates `Component` nodes + `DEFINES` edges
- `build_type_nodes(client, types: list[dict])` — creates `Type` nodes + `DEFINES` edges
- `build_hook_nodes(client, hooks: list[dict])` — creates `Hook` nodes (deduped by name) + `DEFINES` edges for callers
- `tests/test_node_builder.py`

**Cypher pattern used:**

```cypher
UNWIND $batch AS row
MERGE (f:Function {id: row.id})
SET f += row.props
WITH f, row
MATCH (file:File {path: row.file})
MERGE (file)-[:DEFINES]->(f)
```

---

### Sub-Plan 4.4 — Import Relationships

**New file:** `aica/memory/graph_store/import_builder.py`

- `resolve_import_path(source: str, from_file: str, repo_root: Path) -> str | None`
  - `import_kind == "external"` → creates/merges `Module` node, skips File edge
  - `import_kind == "relative"` → resolves `./foo` to real `.ts`/`.tsx` path
  - `import_kind == "alias"` → resolves `@/` prefix to `src/` prefix
- `insert_import_edges(client, imports: list[dict], repo_root: Path)`
  - Batched `MERGE (a:File)-[:IMPORTS]->(b:File)` for internal
  - Batched `MERGE (a:File)-[:IMPORTS]->(m:Module)` for external
- `tests/test_import_builder.py` — covers relative, alias, and external resolution

---

### Sub-Plan 4.5 — Call Graph Relationships

**New file:** `aica/memory/graph_store/call_builder.py`

- Builds a lookup: `{function_name → list[Function.id]}` from all known functions
- `insert_call_edges(client, calls: list[dict], functions: list[dict])`
  - For each call site in `calls` (flat list from `extract_calls`):
    - Find enclosing function by matching file + containment (line range)
    - Resolve callee to a `Function` node by name
    - Unresolvable callees: `log.warning("call_builder.unresolved_callee", ...)`, skip
  - Batched `MERGE (a:Function)-[:CALLS]->(b:Function)`
- `insert_hook_usage_edges(client, hooks: list[dict])`
  - Each hook call site links its caller (Function/Component) to the Hook node:
  - `MERGE (caller)-[:USES_HOOK]->(hook:Hook {name: row.hook_name})`
- `tests/test_call_builder.py`

---

### Sub-Plan 4.6 — Scanner Data (Routes, Services, Stores)

**New file:** `aica/memory/graph_store/scanner_builder.py`

Reads from `.repo_intelligence/` JSON files (already written by `scan-repo`):

- `build_route_nodes(client, routes: list[dict])`
  - `MERGE (r:Route {route: row.route}) SET r += {type, methods, tier}`
  - `MERGE (f:File {path: row.file})-[:HAS_ROUTE]->(r)`
- `build_service_nodes(client, services: list[dict])`
  - `MERGE (s:Service {name: row.service})`
  - `MERGE (f:File)-[:BELONGS_TO]->(s)`
- `build_store_nodes(client, stores: list[dict])`
  - `MERGE (st:Store {store: row.store})`
  - `MERGE (f:File)-[:HAS_STORE]->(st)`
- `tests/test_scanner_builder.py`

---

### Sub-Plan 4.7 — Pipeline Orchestrator + CLI

**New file:** `aica/memory/graph_store/graph_builder.py`

```python
@dataclass
class GraphSummary:
    files: int
    functions: int
    components: int
    types: int
    hooks: int
    routes: int
    services: int
    stores: int
    import_edges: int
    call_edges: int
    hook_edges: int

def build_dependency_graph(repo_path: Path) -> GraphSummary:
    # 1. Load all AST JSONs from repo_path/.repo_intelligence/ast/
    # 2. Load scanner JSONs from repo_path/.repo_intelligence/
    # 3. Connect to Neo4j via Neo4jClient (from settings)
    # 4. setup_schema(client)
    # 5. build_file_nodes / build_function_nodes / etc.
    # 6. insert_import_edges / insert_call_edges / insert_hook_usage_edges
    # 7. build_route_nodes / build_service_nodes / build_store_nodes
    # 8. Return GraphSummary
```

**CLI addition** (`aica/interfaces/cli.py`):

```
aica build-graph [--path PATH]
```

- Resolves path (defaults to `settings.workspace_dir`)
- Calls `build_dependency_graph(path)`
- Renders Rich `Panel` + `Table` with `GraphSummary` counts
- `tests/test_graph_builder.py` — integration level with mocked Neo4jClient

---

### Sub-Plan 4.8 — Query Helpers (AI Interface)

**New file:** `aica/memory/graph_store/queries.py`

```python
class GraphQueryEngine:
    def __init__(self, client: Neo4jClient): ...

    def find_dependents(self, function_name: str) -> list[dict]:
        """Which functions CALL this function?"""

    def find_dependencies(self, function_name: str) -> list[dict]:
        """What does this function CALL?"""

    def find_file_imports(self, file_path: str) -> list[dict]:
        """All files/modules imported by this file."""

    def find_change_impact(self, file_path: str, depth: int = 3) -> list[dict]:
        """All files that transitively import this file (impact of changing it)."""

    def detect_circular_imports(self) -> list[list[str]]:
        """Return all import cycles in the codebase."""

    def find_dead_exports(self) -> list[dict]:
        """Exported symbols never imported anywhere."""

    def find_call_chain(self, from_fn: str, to_fn: str) -> list[str] | None:
        """Shortest CALLS path between two functions."""

    def most_called_functions(self, limit: int = 10) -> list[dict]:
        """Functions with the most incoming CALLS edges."""

    def files_using_hook(self, hook_name: str) -> list[dict]:
        """All components/functions that USES_HOOK this hook."""
```

- `tests/test_graph_queries.py` — mock client returns, verify Cypher construction and result mapping

---

## Decisions Captured

- Neo4j: Both local Docker + AuraDB cloud; switch via `AICA_NEO4J_URI` env var (`bolt://` vs `neo4j+s://`)
- Graph builder reads from existing `.repo_intelligence/ast/*.json` files (does not re-run AST extraction)
- Scope: AST data (Files, Functions, Calls, Imports, Components, Types, Hooks) + Scanner data (Routes, Services, Stores)
- All node insertions use batched `MERGE` (batch size 500) to avoid duplicates and ensure performance
- Unresolvable references (calls, imports) are logged as warnings and skipped — never crash the pipeline
- `GraphSummary` dataclass returned from pipeline for programmatic use by agents

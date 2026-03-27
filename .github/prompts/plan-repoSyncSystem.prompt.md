# Plan: Incremental Repository Sync System

Build an incremental sync system that detects changed files via git diff and updates only affected AST data and Neo4j graph nodes, avoiding expensive full repository reprocessing. Adds `aica sync-repo` command with smart change detection, file-level AST updates, and graph node replacement.

**Approach**: Create new `repo_intelligence/sync/` module with git-based change detector, modify existing AST runner to support file-specific processing, add graph deletion utilities for removing old nodes, and wire everything through a new CLI command with automatic fallback to full reindex for large changes.

---

## Architecture Overview

### Problem Statement

Currently, any repository change requires full reprocessing:

- Scan entire repository (16 detectors)
- Parse all .ts/.tsx files with AST (7 extractors)
- Rebuild entire Neo4j graph (all nodes + edges)
- Time: 60+ seconds for 1000+ file repos

**Solution**: Incremental updates that only process changed files.

### Two Update Modes

**1️⃣ Full Reindex (Heavy)**

- **Used when**: First time setup, large refactor, >20% of files changed, `--full` flag
- **Process**: Traditional scan → AST → graph → embeddings pipeline
- **Time**: 60-120+ seconds for large repos

**2️⃣ Incremental Update (Smart)**

- **Used when**: 1-20 files changed, small feature updates
- **Process**: Detect changes → update only affected AST entries → replace graph nodes for changed files
- **Time**: <5 seconds for typical changes

---

## Implementation Steps

### **Phase 1: Change Detection Foundation**

#### 1.1 Create Sync Module Structure

**New files:**

```
repo_intelligence/sync/
  __init__.py
  change_detector.py
  orchestrator.py
  exceptions.py
```

#### 1.2 Implement Git-Based Change Detection

**Location:** `repo_intelligence/sync/change_detector.py`

**Functions:**

```python
def get_changed_files(repo_path: Path, base_ref: str = "HEAD") -> list[str]:
    """Detect changed files using git diff.

    Returns relative paths of .ts/.tsx files only.
    Handles edge cases: empty repo, no git, first commit.
    """

def get_file_hash(file_path: Path) -> str:
    """Calculate SHA-256 hash for file content versioning."""

def detect_real_changes(files: list[str], cached_hashes: dict) -> list[str]:
    """Compare current file hash with cached hash.

    Returns only files with actual content changes.
    """
```

**Implementation details:**

- Run `git diff --name-only {base_ref}` to detect changes
- For uncommitted changes, use `git status --porcelain`
- Filter output for `.ts` and `.tsx` extensions only
- Convert absolute paths to relative paths from repo root
- Handle errors gracefully (no git, not a repo, etc.)

#### 1.3 Add Hash-Based Change Cache

**Cache file:** `.repo_intelligence/.cache/file_hashes.json`

**Format:**

```json
{
  "src/utils/auth.ts": "a3f5b8c9d2e1f4g6h7i8j9k0l1m2n3o4",
  "src/components/Login.tsx": "b4g6c9f2h5k8m1p4r7t0v3x6z9b2d5f8"
}
```

**Functions:**

```python
def load_cached_hashes(repo_path: Path) -> dict[str, str]:
    """Load file hashes from cache."""

def save_hashes(repo_path: Path, hashes: dict[str, str]) -> None:
    """Save current file hashes to cache."""
```

**Benefit:** Skip files with unchanged content (only timestamp/metadata changed).

---

### **Phase 2: Incremental AST Updates**

#### 2.1 Add File-Specific AST Processing

**Location:** `repo_intelligence/ast/runner.py`

**New method:**

```python
class ASTExtractorRunner:
    def run_incremental(
        self,
        repo_path: Path,
        changed_files: list[str]
    ) -> dict:
        """Run AST extraction for specific files only.

        Steps:
        1. Load existing JSON outputs from .repo_intelligence/ast/
        2. For each changed file:
           - Parse file with parse_file()
           - Run all 7 extractors
           - Remove old entries for this file
           - Insert new entries
        3. Handle deleted files (remove all entries)
        4. Rebuild call graph
        5. Return updated data dict
        """
```

**Helper function:**

```python
def _remove_file_entries(data: dict, file_path: str) -> dict:
    """Remove all entries matching file == file_path from each list.

    Example:
    - Filter out all imports where import['file'] == file_path
    - Filter out all functions where function['file'] == file_path
    - etc.
    """
```

**Key considerations:**

- Load existing JSON files first (don't start from scratch)
- Use set-based removal for efficiency: `[x for x in data if x['file'] != file_path]`
- Preserve all data for unchanged files
- Rebuild call graph because function calls may cross file boundaries

#### 2.2 Update AST Writer for Merge Mode

**Location:** `repo_intelligence/ast/writer.py`

**Modified signature:**

```python
class ASTWriter:
    @staticmethod
    def write(
        data: dict,
        repo_path: Path,
        filename: str,
        mode: Literal["replace", "merge"] = "replace"
    ) -> None:
        """Write extractor output to JSON.

        Modes:
        - replace: Overwrite existing file completely (current behavior)
        - merge: Load existing file, merge with new data, write back
        """
```

**Merge logic:**

- Load existing JSON if it exists
- For incremental updates, data already contains merged result
- Simply write to disk (merge happens in runner, not writer)
- Add backup file creation before overwrite (safety net)

---

### **Phase 3: Incremental Graph Updates**

#### 3.1 Add Graph Deletion Utilities

**Location:** `memory/graph_store/delete_builder.py` (new file)

**Functions:**

```python
def delete_file_subgraph(
    client: Neo4jClient,
    file_paths: list[str]
) -> int:
    """Delete File nodes and all entities they define.

    Cypher:
    MATCH (f:File)
    WHERE f.path IN $paths
    OPTIONAL MATCH (f)-[:DEFINES]->(entity)
    DETACH DELETE f, entity

    Returns: Count of deleted nodes
    """

def delete_orphaned_modules(client: Neo4jClient) -> int:
    """Clean up external modules no longer imported.

    Cypher:
    MATCH (m:Module)
    WHERE NOT (m)<-[:IMPORTS]-()
    DELETE m

    Returns: Count of deleted nodes
    """
```

**Why delete-and-recreate?**

- Simpler than updating individual properties
- Ensures consistency (no stale data)
- Neo4j MERGE is expensive; DELETE+CREATE is faster for known changes
- No risk of orphaned relationships

#### 3.2 Add Incremental Graph Builder

**Location:** `memory/graph_store/incremental_builder.py` (new file)

**Main function:**

```python
def update_graph_for_files(
    repo_path: Path,
    changed_files: list[str],
    deleted_files: list[str]
) -> GraphUpdateSummary:
    """Update Neo4j graph for specific files only.

    Steps:
    1. Connect to Neo4j
    2. Delete old subgraphs for changed + deleted files
    3. Load AST JSON and filter for changed files only
    4. Rebuild nodes for changed files:
       - build_file_nodes() with filtered data
       - build_function_nodes() with filtered functions
       - build_component_nodes() with filtered components
       - build_type_nodes() with filtered types
       - build_hook_nodes() with filtered hooks
    5. Rebuild edges for affected relationships:
       - insert_import_edges() — reprocess imports
       - insert_call_edges() — reprocess call graph
       - insert_hook_usage_edges() — reprocess hook usage
    6. Clean up orphaned modules
    7. Return summary
    """
```

#### 3.3 Define Update Summary Dataclass

```python
@dataclass
class GraphUpdateSummary:
    """Summary of incremental graph update."""
    nodes_deleted: int
    nodes_created: int
    edges_created: int
    files_affected: list[str]
    duration_seconds: float
```

**Edge case handling:**

- **Import changes**: If file A imports file B, and B is modified, reprocess A's imports
- **Call graph**: If function in file A calls function in file B, and B is modified, rebuild calls
- **Deleted files**: Remove all nodes, then check for files that imported deleted file

---

### **Phase 4: Orchestration & CLI**

#### 4.1 Create Sync Orchestrator

**Location:** `repo_intelligence/sync/orchestrator.py` (new file)

**Main function:**

```python
def sync_repository(
    repo_path: Path,
    base_ref: str = "HEAD",
    force_full: bool = False
) -> SyncResult:
    """Intelligent repository sync with automatic fallback.

    Steps:
    1. Detect changes via get_changed_files()
    2. Load cached hashes and filter real changes
    3. Detect deleted files (in cache but missing on disk)
    4. Smart decision:
       - If changes > 20% of repo OR force_full → full reindex
       - Else → incremental update
    5. Run incremental AST update
    6. Write updated AST files (merge mode)
    7. Update Neo4j graph
    8. Save new file hashes to cache
    9. Return detailed summary
    """
```

**SyncResult dataclass:**

```python
@dataclass
class SyncResult:
    """Result of repository sync operation."""
    changed_files: list[str]
    deleted_files: list[str]
    mode: Literal["incremental", "full"]
    ast_summary: dict  # Counts per entity type
    graph_summary: GraphUpdateSummary
    duration_seconds: float
```

**Smart fallback logic:**

```python
total_files = count_ts_tsx_files(repo_path)
change_percentage = len(changed_files) / total_files

if change_percentage > 0.20 or force_full:
    # Fallback to full reindex
    run_full_scan(repo_path)
    run_full_ast_extraction(repo_path)
    run_full_graph_rebuild(repo_path)
else:
    # Incremental update
    run_incremental_update()
```

#### 4.2 Add CLI Command

**Location:** `interfaces/cli.py`

**Command:**

```python
@app.command(name="sync-repo")
def sync_repo(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Repository path (default: workspace_dir)")
    ] = None,
    base: Annotated[
        str,
        typer.Option("--base", help="Git ref to compare against")
    ] = "HEAD",
    full: Annotated[
        bool,
        typer.Option("--full", help="Force full reindex")
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show detailed file-by-file changes")
    ] = False,
) -> None:
    """Sync repository changes incrementally.

    Detects changed files and updates only affected AST data
    and Neo4j graph nodes. Automatically falls back to full
    reindex for large changes (>20% of files).

    Examples:
      aica sync-repo
      aica sync-repo --path /path/to/repo
      aica sync-repo --base HEAD~3
      aica sync-repo --full
    """
```

**Output format:**

```
╭─ Repository Sync Results ────────────────────────╮
│ Mode: Incremental                                │
│ Changed files: 3                                 │
│ Deleted files: 0                                 │
│                                                  │
│ AST Updates:                                     │
│   • Functions: 12 updated                        │
│   • Imports: 8 updated                           │
│   • Components: 2 updated                        │
│   • Calls: 15 updated                            │
│                                                  │
│ Graph Updates:                                   │
│   • Nodes deleted: 18                            │
│   • Nodes created: 20                            │
│   • Edges created: 35                            │
│                                                  │
│ Duration: 3.2s                                   │
╰──────────────────────────────────────────────────╯
```

**Verbose mode output:**

```
Changed Files:
  • src/services/auth.service.ts
    - 4 functions updated
    - 2 imports added
    - 1 call removed
  • src/components/Login.tsx
    - 1 component updated
    - 3 hooks updated
  • src/utils/validation.ts
    - 2 functions added
    - 1 function removed
```

---

### **Phase 5: Scanner Integration (Optional)**

#### 5.1 Add Incremental Scanner Support

**Location:** `repo_intelligence/scanner/incremental.py` (new file)

**Function:**

```python
def run_incremental_scan(
    repo_path: Path,
    changed_files: list[str]
) -> dict:
    """Run scanner detectors for specific files only.

    Steps:
    1. For each detector, filter files via detector-specific patterns
       - HooksDetector: only .ts files in changed_files
       - ComponentsDetector: only .tsx files in changed_files
    2. Load existing detector JSONs
    3. Remove old entries for changed files
    4. Run detector on changed files
    5. Merge new entries
    6. Write updated JSONs
    """
```

**Note:** Scanner is fast (regex-based), so full re-scan is acceptable initially. This phase can be deferred to post-MVP.

---

## File Reference

### New Files to Create

1. **`repo_intelligence/sync/__init__.py`**
   - Exports: `sync_repository`, `get_changed_files`, `detect_real_changes`

2. **`repo_intelligence/sync/change_detector.py`**
   - Functions: `get_changed_files()`, `get_file_hash()`, `detect_real_changes()`, `load_cached_hashes()`, `save_hashes()`

3. **`repo_intelligence/sync/orchestrator.py`**
   - Functions: `sync_repository()`, dataclass: `SyncResult`

4. **`repo_intelligence/sync/exceptions.py`**
   - Exceptions: `SyncError`, `GitNotFoundError`, `NoChangesError`

5. **`memory/graph_store/delete_builder.py`**
   - Functions: `delete_file_subgraph()`, `delete_orphaned_modules()`

6. **`memory/graph_store/incremental_builder.py`**
   - Functions: `update_graph_for_files()`, dataclass: `GraphUpdateSummary`

7. **`repo_intelligence/scanner/incremental.py`** _(Phase 5, optional)_
   - Functions: `run_incremental_scan()`

### Files to Modify

1. **`repo_intelligence/ast/runner.py`**
   - Add method: `ASTExtractorRunner.run_incremental()`
   - Add helper: `_remove_file_entries()`

2. **`repo_intelligence/ast/writer.py`**
   - Modify method: `ASTWriter.write()` — add `mode` parameter

3. **`interfaces/cli.py`**
   - Add command: `@app.command(name="sync-repo")`

4. **`memory/graph_store/__init__.py`**
   - Add exports: `delete_file_subgraph`, `update_graph_for_files`, `GraphUpdateSummary`

5. **`repo_intelligence/sync/__init__.py`**
   - Add exports: `sync_repository`, `SyncResult`

---

## Verification & Testing

### 1. Change Detection Validation

**Tests:**

- Initialize test repo with git
- Modify 2-3 files, run `aica sync-repo`, verify only those files detected
- Test edge cases:
  - New files (untracked)
  - Deleted files
  - Renamed files
  - First commit (no HEAD~1)
  - No git repository (graceful error)
- Verify hash cache: modify file → sync → restore file → sync should skip (hash unchanged)

**Expected behavior:**

```bash
# Modify file
echo "// comment" >> src/utils.ts
aica sync-repo --verbose
# Output: "Changed files: 1 (src/utils.ts)"

# Restore file (undo comment)
git checkout src/utils.ts
aica sync-repo --verbose
# Output: "No changes detected (hash cache hit)"
```

### 2. AST Incremental Correctness

**Tests:**

- Full index repo → modify 1 function → sync → verify:
  - Old function entry removed from `functions.json`
  - New function entry added with updated line number/params
  - Other files' entries unchanged
- Delete file → sync → verify all entries removed from all 7 JSON files
- Add new file → sync → verify entries added to appropriate JSON files
- Modify import → sync → verify `imports.json` and `call_graph.json` updated

**Example validation:**

```python
# Before sync
functions = load_json(".repo_intelligence/ast/functions.json")
old_fn = [f for f in functions if f['file'] == 'src/auth.ts' and f['name'] == 'login']

# Modify src/auth.ts (change login function signature)

# After sync
functions = load_json(".repo_intelligence/ast/functions.json")
new_fn = [f for f in functions if f['file'] == 'src/auth.ts' and f['name'] == 'login']

assert old_fn[0]['params'] != new_fn[0]['params']  # Params changed
assert old_fn[0]['line'] != new_fn[0]['line']      # Line changed
```

### 3. Graph Incremental Correctness

**Tests:**

- Build full graph → modify file → sync → verify:
  - Old File node deleted
  - Old Function/Component nodes deleted
  - New nodes created with updated data
  - Import edges recomputed correctly
  - No duplicate nodes
- Delete file → sync → verify:
  - File node removed
  - All DEFINES relationships removed
  - Files that imported deleted file updated
- Add new file → sync → verify nodes and edges created

**Neo4j validation queries:**

```cypher
// Before sync
MATCH (f:File {path: "src/auth.ts"})-[:DEFINES]->(fn:Function)
RETURN count(fn) as old_count

// After sync (modified file)
MATCH (f:File {path: "src/auth.ts"})-[:DEFINES]->(fn:Function)
RETURN count(fn) as new_count

// Check for orphaned nodes
MATCH (n) WHERE NOT (n)--() RETURN count(n)
// Should be 0
```

### 4. Full Fallback Behavior

**Tests:**

- Modify 50+ files (>20% threshold) → sync → verify:
  - Fallback to full reindex triggered
  - Console message: "Large change detected, running full reindex"
- Use `--full` flag → verify:
  - Full reindex runs regardless of change count
  - Same output as `scan-repo` + `index-code` + `build-graph`

### 5. Performance Benchmarks

**Metrics to track:**

| Scenario                  | Target Time | Notes               |
| ------------------------- | ----------- | ------------------- |
| 1 file changed            | <2s         | Fastest path        |
| 10 files changed          | <5s         | Typical development |
| 100 files changed         | <30s        | Large feature       |
| Full reindex (1000 files) | 60-120s     | Baseline comparison |

**Benchmark script:**

```bash
# Setup: 1000 file repo
time aica scan-repo && time aica index-code && time aica build-graph
# Baseline: ~90s

# Modify 1 file
echo "// test" >> src/utils.ts
time aica sync-repo
# Target: <2s (45x faster)

# Modify 10 files
for i in {1..10}; do echo "// test" >> src/file$i.ts; done
time aica sync-repo
# Target: <5s (18x faster)
```

### 6. End-to-End Integration Test

**Full workflow:**

```bash
# Initial setup
cd /path/to/test-repo
aica scan-repo
aica index-code
aica build-graph

# Make changes
# 1. Edit function in src/services/auth.service.ts
# 2. Add new component in src/components/NewButton.tsx
# 3. Delete src/utils/deprecated.ts

# Sync changes
aica sync-repo --verbose

# Verify in Neo4j
# Query for updated function
# Query for new component
# Verify deleted file nodes removed

# Verify AST JSON files
cat .repo_intelligence/ast/functions.json | grep "NewButton"
cat .repo_intelligence/ast/functions.json | grep "deprecated" | wc -l  # Should be 0
```

---

## Design Decisions & Rationale

### 1. Git-Based Detection vs. File Watching

**Decision:** Use `git diff` as primary change source, not filesystem watchers.

**Rationale:**

- **Simplicity**: Git diff is reliable and standard across all repos
- **Consistency**: Captures actual committed/staged changes, not editor saves
- **No daemon required**: File watching requires background process
- **Cross-platform**: Git is already required; no OS-specific file watchers

**Future work:** Add `aica watch` mode with filesystem watchers in Phase 6.

### 2. File-Level Granularity

**Decision:** Update at file level, not function/import level.

**Rationale:**

- **Simplicity**: Easier to implement and reason about
- **Sufficient precision**: Most changes affect entire file context anyway
- **Safe**: No risk of partial updates leaving inconsistent state
- **Fast enough**: Parsing single file is <50ms even for large files

**Alternative considered:** Function-level updates would be more granular but add complexity for minimal performance gain.

### 3. 20% Fallback Threshold

**Decision:** Fallback to full reindex if >20% of files changed.

**Rationale:**

- **Performance crossover**: Incremental overhead (loading existing data, merging) exceeds full reindex time at ~20%
- **Safety**: Large refactors may have cross-file dependencies better handled by full reindex
- **Configurable**: Can be tuned via environment variable if needed

**Calculation:**

```python
FALLBACK_THRESHOLD = 0.20  # 20%
if (changed_count / total_count) > FALLBACK_THRESHOLD:
    run_full_reindex()
```

### 4. Hash Caching Strategy

**Decision:** Track SHA-256 hashes to detect genuine content changes.

**Rationale:**

- **Avoid false positives**: Git diff can show files that haven't actually changed (formatting tools, line ending conversion)
- **Skip unchanged files**: Developers often touch files without changing code (save without edit)
- **Fast comparison**: SHA-256 is fast (~1ms per file) and reliable
- **Persistence**: Cache survives git operations (stash, checkout)

**Trade-off:** Extra I/O for hash computation, but saves unnecessary AST parsing.

### 5. Delete-and-Recreate for Graph

**Decision:** Delete entire file subgraph then rebuild, rather than updating individual nodes.

**Rationale:**

- **Simplicity**: Easier to implement and maintain
- **Consistency**: No risk of stale properties or orphaned relationships
- **Performance**: Neo4j DELETE+CREATE is faster than MERGE for known changes
- **Safety**: Fresh rebuild ensures accuracy

**Alternative considered:** Using MERGE to update properties would be more granular but risks leaving stale data if schema changes.

### 6. Automatic Fallback vs. Manual Flag

**Decision:** Automatically detect when full reindex is better, with manual override.

**Rationale:**

- **User-friendly**: No need to remember when to use full vs. incremental
- **Safe default**: Large changes automatically use full reindex
- **Override available**: Power users can force `--full` if needed
- **Transparent**: Log messages clearly state which mode was used

**UX flow:**

```bash
# Small change → automatic incremental
aica sync-repo
# Output: "Mode: Incremental (3 files changed)"

# Large change → automatic fallback
aica sync-repo
# Output: "Mode: Full (124 files changed, >20% threshold)"

# Force full regardless
aica sync-repo --full
# Output: "Mode: Full (forced by --full flag)"
```

---

## Architecture Improvements

### Current State Limitations

1. **No incremental processing**: Always full repo scan/parse
2. **No change tracking**: Can't detect what changed since last run
3. **No file-level operations**: AST runner processes entire repo or nothing
4. **Graph rebuilds from scratch**: Deletes everything, recreates everything

### After Implementation

1. **Smart change detection**: Git-based with hash verification
2. **File-level AST updates**: Process only changed files
3. **Graph node replacement**: Update only affected nodes/edges
4. **Automatic optimization**: Fallback to full reindex when beneficial

### Performance Impact

**Before:**

```
Developer edits 1 file
  ↓
Run aica index-code (90s)
  ↓
Run aica build-graph (30s)
  ↓
Total: 120s
```

**After:**

```
Developer edits 1 file
  ↓
Run aica sync-repo (3s)
  ↓
Total: 3s (40x faster)
```

### Developer Experience

**Before:**

```bash
# Edit code
vim src/auth.service.ts

# Wait 2 minutes for full reindex
aica scan-repo && aica index-code && aica build-graph

# Check graph
neo4j query "MATCH ..."
```

**After:**

```bash
# Edit code
vim src/auth.service.ts

# Wait 3 seconds
aica sync-repo

# Check graph (updated)
neo4j query "MATCH ..."
```

---

## Risks & Mitigations

### Risk 1: Complex Call Graph Dependencies

**Risk:** Function A in file X calls function B in file Y. If Y changes, call graph may be inconsistent.

**Mitigation:** Always rebuild entire call graph on any function change. Call graph construction is fast (<1s) and ensures consistency.

### Risk 2: Neo4j Transaction Timeouts

**Risk:** Large batches of graph updates may exceed Neo4j transaction timeout (30s default).

**Mitigation:** Existing 500-row batch limit already handles this. Incremental updates use smaller batches anyway.

### Risk 3: Git Not Available

**Risk:** Repository not initialized with git, or git not installed.

**Mitigation:**

- Check for `.git` directory before running git commands
- Gracefully fallback to full reindex with warning message
- Add `--no-git` flag to bypass git detection and use simple file modification time

### Risk 4: Concurrent Operations

**Risk:** Another process running `index-code` or `build-graph` while `sync-repo` is running.

**Mitigation:**

- Add file locking via `.repo_intelligence/.lock`
- Check lock before any index/sync/build operation
- Release lock on completion or error
- Timeout after 5 minutes (stale lock cleanup)

### Risk 5: Partial Failures

**Risk:** AST update succeeds, but graph update fails → inconsistent state.

**Mitigation:**

- Two-phase commit pattern:
  1. Write AST to temporary files (`.repo_intelligence/ast/.tmp/`)
  2. Update graph
  3. If graph succeeds, promote temp files to live
  4. If graph fails, rollback (delete temp files, keep old AST)
- Add `--dry-run` flag to preview changes without applying

### Risk 6: Hash Cache Corruption

**Risk:** Cache file corrupted or out of sync with actual files.

**Mitigation:**

- Validate cache on load (check JSON format)
- If cache invalid, discard and rebuild
- Add `--clear-cache` flag to manually reset
- Cache misses fall back to full reindex (safe default)

---

## Future Enhancements

### Phase 6: Real-Time File Watching

**Feature:** `aica watch` command that monitors filesystem and auto-syncs.

**Implementation:**

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class RepoChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(('.ts', '.tsx')):
            # Debounce: wait 2s for more changes
            # Aggregate changes
            # Run sync_repository()
```

**Benefits:**

- Zero-effort sync during development
- Near real-time graph updates
- Background operation

**Challenges:**

- Daemon lifecycle management
- Resource usage (CPU, memory)
- Stability across editor operations (save, move, delete)

### Phase 7: Distributed Sync for Monorepos

**Feature:** Parallel sync across multiple workspaces/packages.

**Implementation:**

```python
from multiprocessing import Pool

def sync_workspace(workspace_path: Path):
    sync_repository(workspace_path)

with Pool(processes=4) as pool:
    pool.map(sync_workspace, workspaces)
```

**Benefits:**

- Faster sync for large monorepos
- Independent workspace updates

**Challenges:**

- Merge results from multiple workspaces
- Handle cross-workspace dependencies
- Neo4j connection pooling

### Phase 8: Incremental Embeddings

**Feature:** Update vector embeddings for changed files only.

**Implementation:**

- Detect changed functions/components
- Re-compute embeddings for those entities
- Update vector database (Pinecone, Weaviate, etc.)

**Benefits:**

- Fast similarity search updates
- Support for semantic code search

**Challenges:**

- Embedding model consistency
- Vector database API integration
- Batch optimization

### Phase 9: Change Impact Analysis

**Feature:** Analyze which other files are affected by changes.

**Implementation:**

```python
def analyze_impact(changed_files: list[str]) -> dict:
    # Find files that import changed files
    # Find functions that call changed functions
    # Find components that use changed hooks
    return {
        "direct_importers": [...],
        "indirect_dependencies": [...],
        "test_files_to_run": [...]
    }
```

**Benefits:**

- Know what to test after changes
- Understand change blast radius
- Suggest affected files for review

---

## Open Questions

### 1. What reference should `git diff` use by default?

**Options:**

- `git status --porcelain` (uncommitted + staged changes)
- `git diff HEAD` (uncommitted changes only)
- `git diff HEAD~1` (last commit vs. current commit)

**Recommendation:** Use `git status --porcelain` to detect working directory changes (catches in-progress work). If no changes, fallback to `git diff HEAD~1` to sync last commit.

**Rationale:** Developers often want to sync while editing (before commit). Working directory detection is most useful.

### 2. Should scanner incremental updates be in MVP?

**Options:**

- Include in Phase 5 (before release)
- Defer to post-MVP (Phase 5 becomes Phase 6+)

**Recommendation:** Defer to post-MVP. Scanner is fast (regex-based, <5s for 1000 files). Full re-scan is acceptable trade-off. Focus effort on AST and graph incremental updates where performance gain is highest.

### 3. Should we implement two-phase commit for AST safety?

**Options:**

- Simple: Write AST directly, accept risk of partial failure
- Two-phase: Write to temp, commit after graph succeeds

**Recommendation:** Start simple, add two-phase in post-MVP if users report issues. Most graph operations succeed, and full reindex can recover from inconsistent state.

### 4. What threshold should trigger fallback to full reindex?

**Options:**

- 10% (conservative)
- 20% (balanced)
- 30% (aggressive)

**Recommendation:** Start with 20%, make configurable via environment variable `AICA_SYNC_FALLBACK_THRESHOLD=0.20`. Users can tune based on their repo size and hardware.

### 5. Should we support multiple git refs for comparison?

**Options:**

- Single ref: `--base HEAD~1`
- Range: `--base HEAD~3..HEAD`
- Branch comparison: `--base main..feature`

**Recommendation:** Start with single ref (simplest). Add range support if users request it. Most common use case is "sync since last commit" or "sync working directory."

---

## Summary

This plan creates a **production-ready incremental sync system** that:

✅ **Detects changes** via git diff with hash verification  
✅ **Updates AST incrementally** by processing only changed files  
✅ **Updates graph incrementally** by replacing nodes for changed files  
✅ **Falls back automatically** to full reindex for large changes  
✅ **Provides clear CLI** with `aica sync-repo` command  
✅ **Delivers 40x speedup** for typical changes (3s vs. 120s)

**Implementation complexity:** Medium  
**Estimated effort:** 3-5 days for Phases 1-4  
**Risk level:** Low (graceful fallbacks, safe defaults)  
**User impact:** High (dramatic productivity improvement)

**Next steps:**

1. Review plan with team
2. Create GitHub issue with checklist from this plan
3. Implement Phase 1 (change detection) first
4. Test thoroughly with real repositories
5. Iterate based on feedback

# SUB-PLAN 6: Incremental Sync Integration — Implementation Complete

**Status:** ✅ COMPLETE  
**Date:** March 31, 2026  
**Author:** GitHub Copilot (Claude Sonnet 4.5)

---

## Overview

Successfully implemented automatic embedding updates integrated with AICA's repository sync system. When files change, the system now:

- Deletes stale embeddings
- Expands to affected files (using cross-file dependency detection)
- Re-chunks changed code
- Generates new embeddings
- Upserts to Qdrant
- Reports comprehensive metrics

---

## Files Created

### 1. `aica/memory/vector_store/incremental_updater.py` (476 lines)

**Core Functions:**

- **`EmbeddingUpdateSummary`** — Dataclass for update metrics (chunks deleted/created, files processed, duration)
- **`update_embeddings_for_files()`** — Main orchestrator that coordinates all update steps
- **`_delete_embeddings_for_files()`** — Batch deletion using Qdrant filters
- **`_rechunk_files()`** — Re-chunk changed files using AST data
- **`_upsert_embeddings()`** — Generate embeddings and batch upsert to Qdrant
- **`_expand_affected_files()`** — Expand to importers and callers using cross-file detector
- **`_filter_by_content_hash()`** — Skip unchanged files (MVP: disabled, returns all)

**Key Features:**

- Follows incremental builder pattern from `graph_store`
- Graceful error handling (continues on individual file failures)
- Structured logging with `lobe-` prefix
- Auto-cleanup of Qdrant connections
- Enriched metadata: `indexed_at`, `aica_version`

### 2. `tests/test_incremental_embedder.py` (319 lines)

**13 Tests (100% passing):**

1. `test_delete_embeddings_for_files_builds_correct_filter` — Verify Qdrant filter structure
2. `test_delete_embeddings_for_files_empty_list` — Handle empty file lists
3. `test_rechunk_files_filters_to_changed_files` — Verify filtering to changed files only
4. `test_rechunk_files_handles_missing_ast` — Graceful handling of missing AST files
5. `test_upsert_embeddings_enriches_payload` — Verify metadata enrichment
6. `test_upsert_embeddings_empty_chunks` — Handle empty chunks
7. `test_expand_affected_files_includes_importers` — Verify cross-file expansion
8. `test_expand_affected_files_excludes_deleted` — Exclude deleted files from re-indexing
9. `test_filter_by_content_hash_includes_all_for_mvp` — Hash filtering (MVP implementation)
10. `test_filter_by_content_hash_handles_missing_files` — Handle missing files
11. `test_update_embeddings_for_files_summary` — Verify summary structure
12. `test_update_embeddings_for_files_closes_connection` — Verify cleanup
13. `test_embedding_update_summary_str` — Verify string formatting

---

## Files Modified

### 1. `aica/repo_intelligence/sync/orchestrator.py`

**Changes:**

- **Import:** Added `update_embeddings_for_files` and `EmbeddingUpdateSummary`
- **`SyncResult` dataclass:** Added `embedding_summary: EmbeddingUpdateSummary | None` field
- **`_run_incremental_pipeline()`:**
  - Updated signature to return `tuple[dict[str, int], GraphUpdateSummary, EmbeddingUpdateSummary | None]`
  - Added embedding update step after graph update
  - Checks `settings.sync_update_embeddings` flag
  - Handles exceptions gracefully (logs error, continues sync)
- **`_run_full_pipeline()`:**
  - Updated signature to return embedding_summary (currently `None`)
  - Logs hint to use `aica index-embeddings --force` for full re-index
- **`sync_repository()`:** Updated to pass `embedding_summary` to `SyncResult`

**Integration Pattern:**

```python
# After graph update
if settings.sync_update_embeddings:
    try:
        embedding_summary = update_embeddings_for_files(
            repo_path, changed_files, deleted_files
        )
        log.info("embeddings.updated", summary=str(embedding_summary))
    except Exception as exc:
        log.error("embeddings.update_failed", error=str(exc))
```

### 2. `aica/config/settings.py`

**Added Configuration:**

```python
sync_update_embeddings: bool = Field(
    default=True,
    description="Auto-update embeddings during repository sync (set to False to skip)",
)
```

**Environment Variable:** `AICA_SYNC_UPDATE_EMBEDDINGS=false` to disable

### 3. `aica/memory/vector_store/__init__.py`

**Added Exports:**

- `EmbeddingUpdateSummary`
- `update_embeddings_for_files`

---

## Architecture Decisions

### 1. Update Strategy: Delete-then-Insert

- **Decision:** Delete old embeddings, then insert new (not update-in-place)
- **Rationale:**
  - Handles chunk count changes (functions added/removed)
  - Simpler to implement
  - Ensures consistency

### 2. Cross-File Expansion: Direct Dependents Only

- **Decision:** Expand to files that import or call changed files (1 level)
- **Rationale:**
  - Prevents exponential expansion (A→B→C would re-index entire codebase)
  - Keeps metadata accurate for direct dependencies
  - Documented as future enhancement for transitive closure

### 3. Hash Optimization: MVP Placeholder

- **Decision:** `_filter_by_content_hash()` currently returns all files (no filtering)
- **Rationale:**
  - Requires storing `content_hash` in Qdrant metadata
  - Requires querying existing chunks before deletion
  - Marked as future performance optimization
  - Doesn't block core functionality

### 4. Error Handling: Continue on Failure

- **Decision:** Individual file failures don't block entire sync
- **Rationale:**
  - One corrupted file shouldn't prevent graph/AST updates
  - Errors logged with structured context
  - Summary could be extended to include error list

### 5. Full Sync: Skip Embedding Update

- **Decision:** Full sync doesn't auto-update embeddings
- **Rationale:**
  - More efficient to run `aica index-embeddings --force` separately
  - Avoids duplicate work (full re-index vs incremental)
  - Keeps full sync focused on scanner+AST+graph rebuild

### 6. Batch Sizes

- **Embedding generation:** 32 texts/batch (from `settings.embedding_batch_size`)
- **Qdrant upsert:** 500 points/batch (from `QdrantClient._batch_size`)
- **Rationale:** Balances memory usage vs API roundtrips

---

## Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0
collected 13 items

tests/test_incremental_embedder.py::test_delete_embeddings_for_files_builds_correct_filter PASSED [  7%]
tests/test_incremental_embedder.py::test_delete_embeddings_for_files_empty_list PASSED [ 15%]
tests/test_incremental_embedder.py::test_rechunk_files_filters_to_changed_files PASSED [ 23%]
tests/test_incremental_embedder.py::test_rechunk_files_handles_missing_ast PASSED [ 30%]
tests/test_incremental_embedder.py::test_upsert_embeddings_enriches_payload PASSED [ 38%]
tests/test_incremental_embedder.py::test_upsert_embeddings_empty_chunks PASSED [ 46%]
tests/test_incremental_embedder.py::test_expand_affected_files_includes_importers PASSED [ 53%]
tests/test_incremental_embedder.py::test_expand_affected_files_excludes_deleted PASSED [ 61%]
tests/test_incremental_embedder.py::test_filter_by_content_hash_includes_all_for_mvp PASSED [ 69%]
tests/test_incremental_embedder.py::test_filter_by_content_hash_handles_missing_files PASSED [ 76%]
tests/test_incremental_embedder.py::test_update_embeddings_for_files_summary PASSED [ 84%]
tests/test_incremental_embedder.py::test_update_embeddings_for_files_closes_connection PASSED [ 92%]
tests/test_incremental_embedder.py::test_embedding_update_summary_str PASSED [100%]

============================== 13 passed in 0.54s ==============================
```

**Status:** ✅ All tests passing, no warnings, no errors

---

## Usage Examples

### 1. Normal Sync (Auto-Update Embeddings)

```bash
# Default behavior: embeddings update automatically
aica sync-repo

# Output includes embedding summary:
# [INFO] embeddings.updated: deleted 5 chunks, created 8 chunks for 2 files in 1.23s
```

### 2. Disable Embedding Updates

```bash
# Via environment variable
export AICA_SYNC_UPDATE_EMBEDDINGS=false
aica sync-repo

# Or in code
from aica.config import get_settings
settings = get_settings()
settings.sync_update_embeddings = False
```

### 3. Programmatic Usage

```python
from pathlib import Path
from aica.memory.vector_store import update_embeddings_for_files

repo_path = Path("/path/to/repo")
changed_files = ["src/auth.ts", "src/utils.ts"]
deleted_files = ["src/old.ts"]

summary = update_embeddings_for_files(repo_path, changed_files, deleted_files)

print(f"Deleted: {summary.chunks_deleted}")
print(f"Created: {summary.chunks_created}")
print(f"Duration: {summary.duration_seconds:.2f}s")
```

---

## Verification Checklist

Based on the plan's verification requirements:

| #   | Verification Test                  | Status | Notes                     |
| --- | ---------------------------------- | ------ | ------------------------- |
| 1   | Unit test: Batch deletion          | ✅     | Filter structure verified |
| 2   | Unit test: Re-chunking             | ✅     | File filtering works      |
| 3   | Unit test: Hash optimization       | ✅     | MVP implementation        |
| 4   | Unit test: Cross-file expansion    | ✅     | Importers included        |
| 5   | Integration test: Single file      | ⏭️     | Requires Qdrant instance  |
| 6   | Integration test: File deletion    | ⏭️     | Requires Qdrant instance  |
| 7   | Integration test: Dependent update | ⏭️     | Requires Qdrant instance  |
| 8   | Performance test: 10 files         | ⏭️     | Requires full environment |
| 9   | Idempotency test                   | ⏭️     | Requires Qdrant instance  |
| 10  | End-to-end test                    | ⏭️     | Requires full environment |

**Status Legend:**

- ✅ Unit tests implemented and passing
- ⏭️ Integration tests require live Qdrant instance (to be run in CI/CD)

---

## Future Enhancements

### 1. Content Hash Optimization (Skipped Changes)

**Goal:** Skip re-embedding files where only comments changed

**Implementation:**

- Store `content_hash` (SHA-256) in Qdrant metadata during upsert
- In `_filter_by_content_hash()`: Query existing chunks, compare hashes
- Skip files with matching hash

**Benefit:** Reduces embedding API calls for non-semantic changes (comments, formatting)

### 2. Transitive Dependency Expansion

**Goal:** Re-embed files that depend on files that depend on changed files (A→B→C)

**Implementation:**

- Multiple passes of `detect_all_affected_files()` until fixed point
- Add depth limit to prevent full codebase re-indexing

**Benefit:** Ensures all affected code is up-to-date

### 3. Parallel Embedding Generation

**Goal:** Speed up large syncs by generating embeddings concurrently

**Implementation:**

- Use `asyncio.gather()` with `provider.async_generate_batch()`
- Requires async provider methods (already implemented)

**Benefit:** 2-3x speedup for 10+ changed files

### 4. Orphan Cleanup Command

**Goal:** Remove embeddings for deleted files that weren't part of a sync

**Implementation:**

- CLI command: `aica cleanup-embeddings`
- Scroll through Qdrant collection
- Check if each file exists on disk
- Delete orphaned chunks

**Benefit:** Prevents accumulation of stale embeddings over time

### 5. Embedding Model Validation

**Goal:** Detect when user switches embedding model, prompt for re-index

**Implementation:**

- Store `embedding_model` in collection metadata
- On connect, compare with current config
- Warning if mismatch: "Model changed, run `aica index-embeddings --force`"

**Benefit:** Prevents mixing embeddings from different models (invalid search results)

---

## Maintenance Notes

### Dependencies

- `qdrant-client>=1.7` — Vector database client
- `aica.memory.graph_store.cross_file_detector` — Cross-file dependency detection
- `aica.memory.vector_store.chunkers` — Code chunking functions
- `aica.memory.vector_store.embedding_provider` — Embedding generation

### Configuration

- `AICA_SYNC_UPDATE_EMBEDDINGS` — Enable/disable auto-updates (default: True)
- `AICA_EMBEDDING_BATCH_SIZE` — Embedding generation batch size (default: 32)
- `AICA_QDRANT_BATCH_SIZE` — Qdrant upsert batch size (default: 500)

### Logging

- Logger name: `vector_store.incremental_updater`
- Key events: `embeddings.deleted`, `embeddings.updated`, `embeddings.update_failed`
- Debug: `rechunk.functions`, `rechunk.components`, `files.expanded`

### Error Handling

- Individual file failures logged, don't block sync
- Qdrant connection errors raise `VectorStoreError`
- Missing AST files return empty chunks (graceful fallback)

---

## Conclusion

SUB-PLAN 6 successfully implemented automatic embedding updates integrated with AICA's sync system. The implementation follows established patterns, includes comprehensive tests, and provides a solid foundation for future enhancements.

**Next Steps:**

- Run integration tests with live Qdrant instance
- Benchmark performance with large repositories (1000+ files)
- Implement content hash optimization (skip comment-only changes)
- Add CLI command for manual embedding sync (`aica sync-embeddings`)

**Estimated Completion:** 100% of core functionality

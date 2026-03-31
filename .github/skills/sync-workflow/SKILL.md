---
name: sync-workflow
description: 'Complete workflow for incremental repository synchronization in AICA. Use when: syncing code changes, understanding sync modes, configuring fallback thresholds, troubleshooting sync issues, integrating with CI/CD, optimizing development workflow.'
argument-hint: 'Describe what to sync or troubleshoot (e.g., "sync after feature branch", "configure fallback threshold", "debug sync issues")'
---

# Incremental Sync Workflow

Complete guide for AICA's intelligent incremental synchronization system that automatically updates scanner artifacts, AST data, Neo4j graph, and Qdrant embeddings when files change.

## When to Use

- After making code changes in your repository
- Integrating AICA into development workflow loops
- Setting up CI/CD pipelines with AICA
- Optimizing sync performance with threshold tuning
- Troubleshooting "no changes detected" or sync failures
- Understanding when full rebuild vs incremental update is used

## What is Incremental Sync?

AICA's sync system intelligently updates only what changed, rather than rebuilding everything from scratch:

**What gets synced:**

1. **Scanner artifacts** — Incremental merge of detector outputs
2. **AST data** — Re-extract changed TypeScript/TSX files only
3. **Neo4j graph** — Delete changed nodes → rebuild with cross-file dependencies
4. **Qdrant embeddings** — Delete changed chunks → re-chunk → re-embed

**Intelligent fallback:**

- Automatically switches to **full rebuild** when changes exceed threshold (default: 20%)
- Prevents inefficient incremental updates when most of codebase changed
- Configurable per-project via `AICA_SYNC_FALLBACK_THRESHOLD`

---

## Architecture Overview

```
Developer makes changes
    ↓
git diff --name-status (detect changed files)
    ↓
Content hash verification (skip unchanged files)
    ↓
Decision: Incremental or Full?
    ↓ (< 20%)                    ↓ (≥ 20%)
Incremental Mode              Full Mode
    ↓                              ↓
Scanner incremental merge     Full scanner scan
AST runner (changed files)    Full AST extraction
Graph incremental update      Full graph rebuild
Embedding incremental update  (Skip — use manual re-index)
    ↓                              ↓
Update .repo_intelligence/    Update .repo_intelligence/
Save content hashes           Save content hashes
```

---

## Workflow Steps

### 1. Detect Repository Changes

**Command:**

```bash
aica sync-repo
# or
aica sync-repo --path /path/to/repo --base main
```

**What happens internally:**

1. **Git diff analysis:** `git diff --name-status <base_ref>...HEAD`
   - Changed files (modified, added)
   - Deleted files (removed)

2. **Filter relevant files:** Only TypeScript/TSX files (`*.ts`, `*.tsx`)
   - Ignores: `node_modules/`, `.next/`, `dist/`, build outputs

3. **Content hash verification:**
   - Load cached hashes from `.repo_intelligence/.cache/file_hashes.json`
   - Compute SHA256 hash for each changed file
   - Skip files with identical hash (cosmetic changes only)

4. **Save updated hashes** for next sync

**Configuration:**

```env
# Base ref for change detection (default: HEAD)
# Can be: branch name, commit hash, tag
aica sync-repo --base main
aica sync-repo --base develop
aica sync-repo --base abc123def
```

---

### 2. Choose Sync Mode (Automatic)

**Decision formula:**

```python
changed_count = len(changed_files) + len(deleted_files)
total_ts_files = count_all_ts_tsx_files(repo_path)
change_percentage = changed_count / total_ts_files

if change_percentage > threshold:
    mode = "full"
else:
    mode = "incremental"
```

**Default threshold:** `0.20` (20%)

**Override threshold:**

```bash
# Use incremental mode more aggressively (30% threshold)
AICA_SYNC_FALLBACK_THRESHOLD=0.30 aica sync-repo

# Force full rebuild regardless of changes
aica sync-repo --force-full
```

**When to tune threshold:**

- **Lower threshold (0.10-0.15):** Large repos, frequent merges, CI/CD pipelines
- **Higher threshold (0.25-0.40):** Small repos, infrequent large changes, development mode
- **Disable incremental (1.0):** Always full rebuild (safest, slowest)

---

### 3. Run Sync Pipeline

#### Incremental Mode (< threshold)

**Step 1: Scanner incremental merge**

- Re-run full scanner to get fresh detector outputs
- For **list artifacts** (routes, components, services):
  - Keep existing entries from unchanged files
  - Replace entries from changed files
- For **singleton artifacts** (framework, structure):
  - Overwrite with fresh values
- Write merged outputs to `.repo_intelligence/`

**Step 2: AST incremental extraction**

- Re-run AST extractors **only** for changed files
- Merge outputs with existing AST data
- Write updated `functions.json`, `imports.json`, `calls.json`, etc.

**Step 3: Graph incremental update**

1. **Cross-file dependency detection:**
   - Find files that **import** changed files
   - Find files that **call** functions from changed files
   - Expand affected files = changed + importers + callers

2. **Delete old subgraph:**
   - Remove nodes for changed files
   - Remove orphaned module nodes
   - Relationships auto-deleted (cascade)

3. **Rebuild nodes for changed files:**
   - File nodes
   - Function nodes
   - Component nodes
   - Type nodes
   - Hook nodes

4. **Rebuild edges for ALL affected files:**
   - Import relationships
   - Call relationships
   - Ensures cross-file links are correct

**Step 4: Embedding incremental update** (optional)

Controlled by `AICA_SYNC_UPDATE_EMBEDDINGS` (default: `true`)

1. **Expand affected files** (same as graph)
2. **Delete embeddings** for changed + deleted files
3. **Re-chunk changed files** using AST data
4. **Generate embeddings** for new chunks
5. **Upsert to Qdrant** in batches

**To disable embedding updates:**

```env
AICA_SYNC_UPDATE_EMBEDDINGS=false
```

Then manually re-index:

```bash
aica index-embeddings --force
```

#### Full Mode (≥ threshold or --force-full)

**Step 1: Full scanner scan**

- Run all 17 detectors on entire repository
- Write all `.repo_intelligence/*.json` files

**Step 2: Full AST extraction**

- Re-run AST extractors on all TypeScript/TSX files
- Write all `.repo_intelligence/ast/*.json` files

**Step 3: Full graph rebuild**

- Delete entire graph (MATCH (n) DETACH DELETE n)
- Build from scratch using graph builder
- Create all nodes and relationships

**Step 4: Manual embedding re-index**

- Full mode **skips** automatic embedding update
- Re-index manually for efficiency:

```bash
aica index-embeddings --force
```

---

### 4. Verify Results

**Check sync summary:**

```bash
aica sync-repo
```

**Output example:**

```
✓ Sync completed (incremental mode)
  Changed files: 3
  Deleted files: 0
  AST extractions: 5 (expanded with dependencies)
  Graph nodes created: 12
  Graph edges created: 8
  Embeddings updated: 15 chunks
  Duration: 2.3s
```

**Verify artifacts updated:**

```bash
# Check AST outputs
ls .repo_intelligence/ast/
# functions.json, imports.json, calls.json, etc.

# Check graph (Neo4j Browser)
MATCH (f:Function)-[r:CALLS]->(g:Function) RETURN f, r, g LIMIT 25

# Check embeddings
aica embedding-status
```

---

## Configuration Reference

### Environment Variables

```env
# Sync behavior
AICA_SYNC_FALLBACK_THRESHOLD=0.20       # 20% changed files → full rebuild
AICA_SYNC_UPDATE_EMBEDDINGS=true        # Auto-update embeddings in incremental mode
AICA_SYNC_MAX_AST_AGE_SECONDS=259200    # 3 days; fail if AST artifacts too old

# For CI/CD: disable embedding auto-update (manual batch)
AICA_SYNC_UPDATE_EMBEDDINGS=false
```

### CLI Flags

```bash
# Specify base ref for change detection
aica sync-repo --base main
aica sync-repo --base develop

# Force full rebuild (ignore threshold)
aica sync-repo --force-full

# Custom repo path
aica sync-repo --path /path/to/repo
```

---

## Common Workflows

### Development Loop

```bash
# 1. Make code changes
vim src/features/Auth/Login.tsx

# 2. Incremental sync
aica sync-repo
# ✓ Incremental mode (1 file changed, 0.5%)

# 3. Verify indexed
aica search-code "login authentication"

# 4. Commit
git add src/features/Auth/Login.tsx
git commit -m "feat: add OAuth login"
```

### Feature Branch Workflow

```bash
# After completing feature branch
git checkout feature/new-auth
# ... make changes ...

# Sync against main branch
aica sync-repo --base main
# ✓ Incremental mode (8 files changed, 4%)

# Verify before merge
aica embedding-status
aica search-code "authentication flow"

# Merge
git checkout main
git merge feature/new-auth
aica sync-repo  # Sync main branch
```

### CI/CD Integration

```yaml
# .github/workflows/aica-sync.yml
name: AICA Sync

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for git diff

      - name: Install AICA
        run: pip install -e .[dev]

      - name: Sync repository
        env:
          AICA_SYNC_UPDATE_EMBEDDINGS: false  # Manual batch later
          AICA_NEO4J_URI: ${{ secrets.NEO4J_URI }}
          AICA_NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
        run: |
          aica sync-repo --base origin/main

      - name: Re-index embeddings (if main branch)
        if: github.ref == 'refs/heads/main'
        run: |
          aica index-embeddings --force
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
aica sync-repo --base HEAD~1
if [ $? -ne 0 ]; then
  echo "❌ AICA sync failed"
  exit 1
fi
echo "✓ AICA sync completed"
```

---

## Troubleshooting

### "No changes detected"

**Symptoms:**

```
Error: NoChangesError: No relevant TypeScript changes detected
```

**Causes:**

1. Only non-TS files changed (e.g., `.md`, `.json`, `.env`)
2. All changed files have identical content hash (cosmetic changes)
3. Cache out of sync

**Solutions:**

```bash
# Force full rebuild to reset cache
aica sync-repo --force-full

# Or delete cache manually
rm -rf .repo_intelligence/.cache/

# Then sync again
aica sync-repo
```

### "AST artifacts too old"

**Symptoms:**

```
Error: AST artifacts are 4 days old (max age: 3 days)
```

**Cause:** AST data is stale; graph update requires fresh AST

**Solution:**

```bash
# Re-run AST extraction
aica index-code

# Then sync
aica sync-repo
```

**Adjust max age:**

```env
# Increase to 7 days
AICA_SYNC_MAX_AST_AGE_SECONDS=604800
```

### Sync falls back to full mode unexpectedly

**Symptoms:**

```
ℹ Using full mode (25% changed files)
```

**Cause:** Threshold too low for your workflow

**Solution:**

```bash
# Raise threshold to 30%
AICA_SYNC_FALLBACK_THRESHOLD=0.30 aica sync-repo

# Or set permanently in .env
echo "AICA_SYNC_FALLBACK_THRESHOLD=0.30" >> .env
```

### Embedding updates fail but sync continues

**Symptoms:**

```
⚠ Embedding update failed: VectorStoreConnectionError
✓ Sync completed (graph updated, embeddings skipped)
```

**Cause:** Qdrant unreachable, but sync is resilient

**Solution:**

```bash
# Check Qdrant status
docker ps | grep qdrant

# Manually re-index embeddings
aica index-embeddings --force
```

### Graph update shows unexpected affected files

**Symptoms:**

```
✓ Expanded 2 changed files → 15 affected files
```

**Cause:** Cross-file dependency detection (expected behavior)

**Explanation:**

When you change `src/auth.ts`:

- All files that **import** `auth.ts` are affected (must rebuild import edges)
- All files that **call** functions from `auth.ts` are affected (must rebuild call edges)

This ensures graph relationships stay accurate.

---

## Performance Tuning

### Optimize for Large Repos

```env
# More aggressive incremental mode (30% threshold)
AICA_SYNC_FALLBACK_THRESHOLD=0.30

# Skip embedding auto-update (batch manually)
AICA_SYNC_UPDATE_EMBEDDINGS=false
```

### Optimize for CI/CD

```bash
# Always use incremental mode (disable fallback)
AICA_SYNC_FALLBACK_THRESHOLD=1.0 aica sync-repo
```

### Optimize for Development

```bash
# Enable all auto-updates for immediate feedback
AICA_SYNC_UPDATE_EMBEDDINGS=true aica sync-repo
```

---

## Related Documentation

- **Graph Schema Extension**: [graph-schema-extension/SKILL.md](../graph-schema-extension/SKILL.md) — How incremental graph builder works
- **Vector Store Workflow**: [vector-store-workflow/SKILL.md](../vector-store-workflow/SKILL.md) — Incremental embedding updates
- **Pre-release Checklist**: [pre-release-checklist/SKILL.md](../pre-release-checklist/SKILL.md) — Validate before commit
- **CLI Reference**: `aica sync-repo --help`

---

## Advanced Topics

### Custom Change Detection

```python
from aica.repo_intelligence.sync import detect_repository_changes

result = detect_repository_changes(repo_path, base_ref="origin/main")
print(f"Changed: {len(result.real_changed_files)}")
print(f"Deleted: {len(result.deleted_files)}")
```

### Programmatic Sync

```python
from aica.repo_intelligence.sync import sync_repository

result = sync_repository(
    repo_path,
    base_ref="main",
    force_full=False,
    fallback_threshold=0.25,
)

print(f"Mode: {result.mode}")
print(f"Nodes created: {result.graph_summary.nodes_created}")
print(f"Duration: {result.duration_seconds:.2f}s")
```

### Inspect Affected Files

```python
from aica.memory.graph_store.cross_file_detector import detect_all_affected_files

affected = detect_all_affected_files(
    changed_files=["src/auth.ts"],
    imports_data=imports,
    functions_data=functions,
    calls_data=calls,
)

print(f"Files that import or call auth.ts: {affected}")
```

---

## Success Criteria

After mastering this workflow, you should be able to:

- [x] Understand when incremental vs full mode is used
- [x] Configure fallback threshold for your project
- [x] Integrate AICA sync into development workflow
- [x] Troubleshoot common sync issues independently
- [x] Optimize sync performance for CI/CD pipelines
- [x] Explain cross-file dependency expansion to team members

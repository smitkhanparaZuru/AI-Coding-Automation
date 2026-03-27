from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from aica.config import get_settings
from aica.core.logging import get_logger
from aica.memory.graph_store.call_builder import insert_call_edges
from aica.memory.graph_store.cross_file_detector import detect_all_affected_files
from aica.memory.graph_store.delete_builder import delete_graph_for_files
from aica.memory.graph_store.import_builder import insert_import_edges
from aica.memory.graph_store.neo4j_client import Neo4jClient
from aica.memory.graph_store.node_builder import (
    build_component_nodes,
    build_file_nodes,
    build_function_nodes,
    build_hook_nodes,
    build_type_nodes,
)

if TYPE_CHECKING:
    from dataclasses import dataclass
else:
    from dataclasses import dataclass

log = get_logger("incremental_builder")

_REQUIRED_AST_FILES = (
    "functions.json",
    "components.json",
    "types.json",
    "hooks.json",
    "imports.json",
    "call_graph.json",
)


@dataclass
class GraphUpdateSummary:
    """Summary of graph update operation."""

    nodes_deleted: int
    """Number of AST nodes deleted."""

    nodes_created: int
    """Number of AST nodes created."""

    edges_created: int
    """Number of edges created (imports, calls, hook_usage)."""

    files_affected: list[str]
    """List of files affected by the update."""

    duration_seconds: float
    """Total duration of the update operation."""

    def __str__(self) -> str:
        """Format as human-readable string."""
        return (
            f"deleted {self.nodes_deleted} nodes, "
            f"created {self.nodes_created} nodes and {self.edges_created} edges "
            f"for {len(self.files_affected)} files in {self.duration_seconds:.2f}s"
        )


def _filter_data_by_files(
    data: list[dict],
    file_paths: list[str],
    file_key: str = "file",
) -> list[dict]:
    """Filter AST data items for specific files only.

    Efficiently filters any array of AST data (functions, components, etc.)
    to include only items belonging to the given file paths.

    Args:
        data: List of dicts to filter (each dict should have file_key field).
        file_paths: List of file paths to keep.
        file_key: Key name in each dict containing the file path (default: "file").

    Returns:
        Filtered list containing only items for files in file_paths.

    Example:
        >>> functions = [
        ...     {"file": "src/a.ts", "name": "login"},
        ...     {"file": "src/b.ts", "name": "logout"},
        ... ]
        >>> filtered = _filter_data_by_files(functions, ["src/a.ts"])
        >>> len(filtered)
        1
    """
    file_set = set(file_paths)
    return [item for item in data if item.get(file_key) in file_set]


def _load_all_ast_data(ast_dir: Path) -> dict[str, list[dict]]:
    """Load all AST JSON files from .repo_intelligence/ast/

    Loads:
        - functions.json
        - components.json
        - types.json
        - hooks.json
        - imports.json
        - call_graph.json (flattened)

    Missing files are gracefully handled (return empty list).

    Args:
        ast_dir: Path to .repo_intelligence/ast/ directory.

    Returns:
        Dict with keys: functions, components, types, hooks, imports, calls.
        Each value is list[dict], or [] if file missing.

    Example:
        >>> data = _load_all_ast_data(Path("repo/.repo_intelligence/ast"))
        >>> print(f"Loaded {len(data['functions'])} functions")
    """

    def load_json(filename: str) -> list[dict]:
        path = ast_dir / filename
        if not path.exists():
            log.debug("ast.file_missing", filename=filename)
            return []
        try:
            with open(path) as f:
                content = json.load(f)
                # Ensure always returns list[dict]
                if isinstance(content, dict):
                    return [content]
                return content if isinstance(content, list) else []
        except (json.JSONDecodeError, OSError) as e:
            log.warning("ast.file_load_failed", filename=filename, error=str(e))
            return []

    # Load individual files
    functions = load_json("functions.json")
    components = load_json("components.json")
    types = load_json("types.json")
    hooks = load_json("hooks.json")
    imports = load_json("imports.json")
    calls = load_json("call_graph.json")

    # Flatten calls if needed (handle nested structure)
    flat_calls = _flatten_calls(calls)

    log.info(
        "ast.loaded",
        functions=len(functions),
        components=len(components),
        types=len(types),
        hooks=len(hooks),
        imports=len(imports),
        calls=len(flat_calls),
    )

    return {
        "functions": functions,
        "components": components,
        "types": types,
        "hooks": hooks,
        "imports": imports,
        "calls": flat_calls,
    }


def _validate_ast_artifacts(ast_dir: Path, max_age_seconds: int) -> None:
    """Validate AST artifacts required for incremental graph updates.

    Args:
        ast_dir: Path to .repo_intelligence/ast.
        max_age_seconds: Max allowed age in seconds for newest artifact.

    Raises:
        FileNotFoundError: If required AST artifacts are missing.
        ValueError: If artifacts are stale beyond configured age.
    """
    missing_files = [name for name in _REQUIRED_AST_FILES if not (ast_dir / name).is_file()]
    if missing_files:
        missing_list = ", ".join(missing_files)
        raise FileNotFoundError(
            "AST artifacts are incomplete. Missing: "
            f"{missing_list}. Run `aica index-code` and retry."
        )

    if max_age_seconds <= 0:
        return

    newest_mtime = max((ast_dir / name).stat().st_mtime for name in _REQUIRED_AST_FILES)
    age_seconds = int(time.time() - newest_mtime)
    if age_seconds > max_age_seconds:
        raise ValueError(
            "AST artifacts appear stale "
            f"({age_seconds}s old, max {max_age_seconds}s). "
            "Run `aica index-code` before syncing graph updates."
        )


def _flatten_calls(calls: list[dict]) -> list[dict]:
    """Flatten nested call_graph.json structure into flat list.

    The call_graph.json may have nested structure:
        [{"file": "...", "functions": [{"name": "...", "calls": [...]}]}]

    Flatten to:
        [{"file": "...", "caller": "...", "callee": "...", ...}]

    Args:
        calls: Original call_graph data (may be nested or flat).

    Returns:
        Flat list of call entries.
    """
    if not calls:
        return []

    # If already flat (list of dicts with 'caller' or 'callee'), return as-is
    if calls and isinstance(calls[0], dict) and ("caller" in calls[0] or "callee" in calls[0]):
        return calls

    # Otherwise, assume nested structure and flatten
    flattened = []
    for entry in calls:
        if isinstance(entry, dict):
            file_path = entry.get("file")
            functions = entry.get("functions", [])
            for func in functions:
                if isinstance(func, dict):
                    caller = func.get("name")
                    func_calls = func.get("calls", [])
                    for call in func_calls:
                        if isinstance(call, dict):
                            flattened.append(
                                {
                                    "file": file_path,
                                    "caller": caller,
                                    "callee": call.get("callee"),
                                    "kind": call.get("kind"),
                                    "line": call.get("line"),
                                }
                            )
    return flattened


def _rebuild_nodes_for_files(
    client: Neo4jClient, changed_files: list[str], ast_dir: Path
) -> dict[str, int]:
    """Rebuild all node types for changed files only.

    Process:
        1. Load all AST data from disk
        2. Filter each entity type for changed files
        3. Call existing builders with filtered data
        4. Aggregate counts

    Strategy: Always call all builders even with empty data (they handle it).
    This ensures uniform behavior regardless of which entity types changed.

    Args:
        client: Neo4j client for database access.
        changed_files: List of file paths that changed.
        ast_dir: Path to .repo_intelligence/ast/ directory.

    Returns:
        Dict with counts: {"files": N, "functions": N, "components": N, ...}
    """
    ast_data = _load_all_ast_data(ast_dir)

    # Filter each type for changed files
    functions = _filter_data_by_files(ast_data["functions"], changed_files)
    components = _filter_data_by_files(ast_data["components"], changed_files)
    types = _filter_data_by_files(ast_data["types"], changed_files)
    hooks = _filter_data_by_files(ast_data["hooks"], changed_files)

    log.debug(
        "filtered_ast_data",
        functions=len(functions),
        components=len(components),
        types=len(types),
        hooks=len(hooks),
    )

    # Build nodes using existing builders
    # Note: build_file_nodes takes all entity types to extract all file paths
    counts = {}
    counts["files"] = build_file_nodes(client, functions, components, types, hooks)
    counts["functions"] = build_function_nodes(client, functions)
    counts["components"] = build_component_nodes(client, components)
    counts["types"] = build_type_nodes(client, types)
    counts["hooks"] = build_hook_nodes(client, hooks)

    total = sum(counts.values())
    log.info("nodes.rebuilt", **counts, total=total)

    return counts


def _rebuild_edges_for_files(
    client: Neo4jClient,
    affected_files: list[str],
    ast_dir: Path,
    repo_root: Path,
) -> dict[str, int]:
    """Rebuild all edge types for affected files.

    Important: For edge building, we use:
    - Filtered data for the linking (changed/affected files)
    - All data for ID resolution (function IDs, component IDs, etc.)

    Example:
        - Calls: Link calls only for affected functions, but resolve function IDs from all
        - Imports: Link imports only for affected files, but resolve module IDs from all

    Args:
        client: Neo4j client for database access.
        affected_files: Files that should have edges updated.
        ast_dir: Path to .repo_intelligence/ast/ directory.
        repo_root: Root path for resolving relative imports.

    Returns:
        Dict with counts: {"imports": N, "calls": N, "hook_usage": N}
    """
    ast_data = _load_all_ast_data(ast_dir)

    # Filter for affected files (for edge linking)
    filtered_imports = _filter_data_by_files(ast_data["imports"], affected_files)
    filtered_calls = _filter_data_by_files(ast_data["calls"], affected_files)

    # Keep all data for ID resolution
    all_functions = ast_data["functions"]

    log.debug(
        "filtered_edges",
        imports=len(filtered_imports),
        calls=len(filtered_calls),
    )

    # Build edges using existing builders
    counts = {}
    counts["imports"] = insert_import_edges(client, filtered_imports, ast_dir, repo_root)
    counts["calls"] = insert_call_edges(client, filtered_calls, all_functions)
    counts["hook_usage"] = insert_hook_usage_edges(client, affected_files, ast_dir)

    total = sum(counts.values())
    log.info("edges.rebuilt", **counts, total=total)

    return counts


def insert_hook_usage_edges(
    client: Neo4jClient,
    affected_files: list[str],
    ast_dir: Path,
) -> int:
    """Insert hook usage edges for affected files.

    TODO: Implement full hook usage edge insertion.
    This is a stub that returns 0 and logs a debug message.

    Args:
        client: Neo4j client for database access.
        affected_files: Files to update hook usage for.
        ast_dir: Path to .repo_intelligence/ast/ directory.

    Returns:
        Number of hook usage edges created (currently 0 - stub).
    """
    log.debug("hook_usage.edges_stub", files=len(affected_files))
    return 0


def update_graph_for_files(
    repo_path: str | Path,
    changed_files: list[str],
    deleted_files: list[str] | None = None,
) -> GraphUpdateSummary:
    """Main entry point for incremental graph update.

    Orchestrates the complete incremental update process:
    1. Validate inputs (repo exists)
    2. Load AST data from disk
    3. Detect cross-file dependencies (files that import/call changed files)
    4. Delete old subgraph for changed files
    5. Rebuild nodes for changed files
    6. Rebuild edges for affected files (changed + importers + callers)

    Args:
        repo_path: Root path of the repository.
        changed_files: List of file paths that changed (relative to repo root).
        deleted_files: List of files that were deleted (optional).

    Returns:
        GraphUpdateSummary with update results and timing.

    Raises:
        ValueError: If repo doesn't exist.
        FileNotFoundError: If AST directory not found.

    Example:
        >>> summary = update_graph_for_files(
        ...     "/repo",
        ...     ["src/app.tsx", "src/utils.ts"],
        ...     deleted_files=["src/old.ts"],
        ... )
        >>> print(summary)
        >>> print(f"Nodes created: {summary.nodes_created}")
    """
    start_time = time.time()
    repo_path = Path(repo_path)

    # Validate inputs
    if not repo_path.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    # Handle empty changed_files gracefully
    if not changed_files:
        log.info("update.skipped", reason="no changed files")
        return GraphUpdateSummary(
            nodes_deleted=0,
            nodes_created=0,
            edges_created=0,
            files_affected=[],
            duration_seconds=time.time() - start_time,
        )

    log.info(
        "update.started",
        repo=str(repo_path),
        changed_count=len(changed_files),
        deleted_count=len(deleted_files or []),
    )

    # Setup paths
    ast_dir = repo_path / ".repo_intelligence" / "ast"
    if not ast_dir.exists():
        raise FileNotFoundError(f"AST directory not found: {ast_dir}")
    settings = get_settings()
    _validate_ast_artifacts(ast_dir, settings.sync_max_ast_age_seconds)

    client: Neo4jClient | None = None
    try:
        # Load AST data for dependency detection
        ast_data = _load_all_ast_data(ast_dir)

        # Detect all affected files (changed + importers + callers)
        affected_files = detect_all_affected_files(
            changed_files,
            ast_data["imports"],
            ast_data["functions"],
            ast_data["calls"],
        )

        log.info(
            "affected_files.detected",
            changed_count=len(changed_files),
            affected_count=len(affected_files),
            expansion_factor=len(affected_files) / len(changed_files) if changed_files else 0,
        )

        # Connect to database
        client = Neo4jClient()

        # Delete old subgraph for changed files
        delete_summary = delete_graph_for_files(client, changed_files)
        log.info("graph.deleted", **delete_summary.__dict__)

        # Rebuild nodes for changed files
        node_counts = _rebuild_nodes_for_files(client, changed_files, ast_dir)

        # Rebuild edges for affected files
        edge_counts = _rebuild_edges_for_files(client, list(affected_files), ast_dir, repo_path)

        # Aggregate results
        total_nodes_created = sum(node_counts.values())
        total_edges_created = sum(edge_counts.values())

        duration = time.time() - start_time

        summary = GraphUpdateSummary(
            nodes_deleted=delete_summary.nodes_deleted,
            nodes_created=total_nodes_created,
            edges_created=total_edges_created,
            files_affected=changed_files,
            duration_seconds=duration,
        )

        log.info(
            "update.completed",
            nodes_deleted=summary.nodes_deleted,
            nodes_created=summary.nodes_created,
            edges_created=summary.edges_created,
            duration=f"{duration:.2f}s",
        )

        return summary

    finally:
        if client:
            client.close()

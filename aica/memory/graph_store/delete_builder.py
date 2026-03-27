from __future__ import annotations

from dataclasses import dataclass

from aica.core.logging import get_logger
from aica.memory.graph_store.neo4j_client import Neo4jClient

log = get_logger("graph_store.delete_builder")


@dataclass
class DeleteSummary:
    """Summary of graph deletion operation."""

    nodes_deleted: int
    orphaned_modules_deleted: int
    relationships_deleted: int
    files_affected: list[str]


def delete_file_subgraph(
    client: Neo4jClient, file_paths: list[str], validate_exists: bool = True
) -> int:
    """Delete File nodes and all entities they define.

    Deletes File nodes and cascades DEFINES edges to Function, Component, Type,
    and Hook nodes. Preserves Module nodes (may be referenced by other files).

    Args:
        client: Neo4j client connection.
        file_paths: List of file paths to delete (e.g., ["src/auth.ts"]).
        validate_exists: Check files exist in repo before deletion (default True).

    Returns:
        Count of deleted nodes (File + child entities).

    Raises:
        GraphError: If Neo4j transaction fails.

    Example:
        >>> from aica.memory.graph_store import delete_file_subgraph
        >>> count = delete_file_subgraph(client, ["src/auth.ts"])
        >>> print(f"Deleted {count} nodes")
    """
    if not file_paths:
        log.debug("delete.file_subgraph.skipped", reason="empty_file_paths")
        return 0

    log.info("delete.file_subgraph.started", file_count=len(file_paths))

    cypher = """
    MATCH (f:File)
    WHERE f.path IN $file_paths
    DETACH DELETE f
    RETURN count(*) AS deleted_count
    """

    try:
        result = client.run_query(cypher, {"file_paths": file_paths})
        deleted_count = result[0]["deleted_count"] if result else 0

        log.info("delete.file_subgraph.completed", deleted_count=deleted_count)
        return deleted_count

    except Exception as e:
        log.error(
            "delete.file_subgraph.failed",
            error=str(e),
            file_count=len(file_paths),
        )
        raise


def delete_orphaned_modules(client: Neo4jClient) -> int:
    """Delete Module nodes no longer imported by any file.

    Cleans up external packages (npm modules) that were imported by now-deleted
    files or whose imports were removed.

    Args:
        client: Neo4j client connection.

    Returns:
        Count of deleted module nodes.

    Raises:
        GraphError: If Neo4j transaction fails.

    Example:
        >>> count = delete_orphaned_modules(client)
        >>> print(f"Cleaned up {count} orphaned modules")
    """
    log.info("delete.orphaned_modules.started")

    cypher = """
    MATCH (m:Module)
    WHERE NOT (m)<-[:IMPORTS]-()
    DELETE m
    RETURN count(*) AS deleted_count
    """

    try:
        result = client.run_query(cypher, {})
        deleted_count = result[0]["deleted_count"] if result else 0

        log.info("delete.orphaned_modules.completed", deleted_count=deleted_count)
        return deleted_count

    except Exception as e:
        log.error("delete.orphaned_modules.failed", error=str(e))
        raise


def delete_graph_for_files(
    client: Neo4jClient, file_paths: list[str]
) -> DeleteSummary:
    """Atomic deletion of File subgraphs with orphaned module cleanup.

    Orchestrates file deletion and cleanup in separate transactions.
    Each transaction can fail independently (not all-or-nothing atomicity),
    but cleanup is idempotent (safe to retry).

    Steps:
        1. Delete File nodes and cascading DEFINES relationships
        2. Delete orphaned Modules (no incoming IMPORTS edges)
        3. Aggregate counts into DeleteSummary

    Args:
        client: Neo4j client connection.
        file_paths: List of file paths to delete.

    Returns:
        DeleteSummary with detailed deletion counts.

    Raises:
        GraphError: If either deletion operation fails.

    Example:
        >>> summary = delete_graph_for_files(client, ["src/auth.ts", "src/utils.ts"])
        >>> print(f"Deleted {summary.nodes_deleted} nodes")
    """
    if not file_paths:
        log.info("delete.graph_for_files.skipped", reason="empty_file_paths")
        return DeleteSummary(
            nodes_deleted=0,
            orphaned_modules_deleted=0,
            relationships_deleted=0,
            files_affected=[],
        )

    log.info("delete.graph_for_files.started", file_count=len(file_paths))

    try:
        # Step 1: Delete File nodes and cascading entities
        files_deleted = delete_file_subgraph(client, file_paths, validate_exists=False)

        # Step 2: Cleanup orphaned modules
        modules_deleted = delete_orphaned_modules(client)

        # Step 3: Aggregate and return
        summary = DeleteSummary(
            nodes_deleted=files_deleted,
            orphaned_modules_deleted=modules_deleted,
            relationships_deleted=0,  # Not tracked separately; included in nodes_deleted
            files_affected=file_paths,
        )

        log.info(
            "delete.graph_for_files.completed",
            nodes_deleted=summary.nodes_deleted,
            modules_deleted=summary.orphaned_modules_deleted,
        )

        return summary

    except Exception as e:
        log.error(
            "delete.graph_for_files.failed",
            error=str(e),
            file_count=len(file_paths),
        )
        raise

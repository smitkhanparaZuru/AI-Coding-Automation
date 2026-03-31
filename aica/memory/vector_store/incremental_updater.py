"""
Incremental Embedding Updater — Sub-Plan 6

Auto-update vector embeddings when files change, integrated with AICA's sync system.

Public API
----------
update_embeddings_for_files(repo_path, changed_files, deleted_files) -> EmbeddingUpdateSummary
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from aica.__about__ import __version__
from aica.config import get_settings
from aica.core.logging import get_logger
from aica.memory.graph_store.cross_file_detector import detect_all_affected_files
from aica.memory.vector_store.chunkers import (
    chunk_components,
    chunk_functions,
    chunk_types,
)
from aica.memory.vector_store.embedding_provider import BaseEmbeddingProvider
from aica.memory.vector_store.exceptions import VectorStoreError
from aica.memory.vector_store.factory import EmbeddingProvider
from aica.memory.vector_store.qdrant_client import QdrantClient
from aica.memory.vector_store.schemas import CodeChunk

log = get_logger("vector_store.incremental_updater")


@dataclass
class EmbeddingUpdateSummary:
    """Summary of embedding update operation.

    Attributes:
        chunks_deleted: Number of chunks removed from vector store.
        chunks_created: Number of new chunks generated and stored.
        chunks_updated: Number of existing chunks updated (currently always 0).
        files_processed: List of files that were re-chunked and re-embedded.
        duration_seconds: Total operation duration in seconds.
    """

    chunks_deleted: int
    """Number of chunks removed from vector store."""

    chunks_created: int
    """Number of new chunks generated and stored."""

    chunks_updated: int
    """Number of existing chunks updated (delete-then-insert = 0)."""

    files_processed: list[str]
    """List of files that were re-chunked and re-embedded."""

    duration_seconds: float
    """Total operation duration in seconds."""

    def __str__(self) -> str:
        """Format as human-readable string."""
        return (
            f"deleted {self.chunks_deleted} chunks, "
            f"created {self.chunks_created} chunks "
            f"for {len(self.files_processed)} files in {self.duration_seconds:.2f}s"
        )


def _delete_embeddings_for_files(
    client: QdrantClient,
    collection: str,
    file_paths: list[str],
) -> None:
    """Delete all embeddings for specified files using Qdrant filter.

    Args:
        client: Connected Qdrant client.
        collection: Collection name.
        file_paths: List of file paths to delete embeddings for.

    Raises:
        VectorStoreError: Deletion failed.
    """
    if not file_paths:
        log.debug("embeddings.delete_empty", collection=collection)
        return

    # Build Qdrant filter: metadata.file IN file_paths
    # Qdrant filter format: {"must": [{"key": "file", "match": {"any": [...]}}]}
    filter_dict = {"must": [{"key": "file", "match": {"any": file_paths}}]}

    try:
        client.delete_by_filter(filter_dict=filter_dict, collection_name=collection)
        log.info(
            "embeddings.deleted",
            collection=collection,
            files=len(file_paths),
        )
    except Exception as exc:
        log.error(
            "embeddings.delete_failed",
            collection=collection,
            files=len(file_paths),
            error=str(exc),
        )
        raise VectorStoreError(f"Failed to delete embeddings: {exc}") from exc


def _rechunk_files(repo_path: Path, file_paths: list[str]) -> list[CodeChunk]:
    """Re-chunk specified files into embeddable code chunks.

    Loads AST artifacts and filters to only include entities from the
    specified files. Handles missing AST files gracefully.

    Args:
        repo_path: Absolute path to repository root.
        file_paths: List of file paths to chunk (POSIX-relative).

    Returns:
        List of CodeChunk instances for the specified files.
    """
    if not file_paths:
        return []

    ast_dir = repo_path / ".repo_intelligence" / "ast"
    file_set = set(file_paths)
    chunks: list[CodeChunk] = []

    # Load and filter AST artifacts
    try:
        # Functions
        functions_path = ast_dir / "functions.json"
        if functions_path.exists():
            functions_data = json.loads(functions_path.read_text(encoding="utf-8"))
            filtered_functions = [
                fn for fn in functions_data if fn.get("file") in file_set
            ]
            if filtered_functions:
                chunks.extend(chunk_functions(filtered_functions, repo_path))
                log.debug(
                    "rechunk.functions",
                    count=len(filtered_functions),
                    files=len(file_paths),
                )

        # Components
        components_path = ast_dir / "components.json"
        if components_path.exists():
            components_data = json.loads(components_path.read_text(encoding="utf-8"))
            filtered_components = [
                comp for comp in components_data if comp.get("file") in file_set
            ]
            if filtered_components:
                chunks.extend(chunk_components(filtered_components, repo_path))
                log.debug(
                    "rechunk.components",
                    count=len(filtered_components),
                    files=len(file_paths),
                )

        # Types
        types_path = ast_dir / "types.json"
        if types_path.exists():
            types_data = json.loads(types_path.read_text(encoding="utf-8"))
            filtered_types = [
                typ for typ in types_data if typ.get("file") in file_set
            ]
            if filtered_types:
                chunks.extend(chunk_types(filtered_types, repo_path))
                log.debug(
                    "rechunk.types",
                    count=len(filtered_types),
                    files=len(file_paths),
                )

    except FileNotFoundError:
        log.warning(
            "rechunk.ast_missing",
            ast_dir=str(ast_dir),
            files=len(file_paths),
        )
        return []
    except json.JSONDecodeError as exc:
        log.error("rechunk.json_error", error=str(exc))
        return []

    # Deduplicate by chunk ID (prefer exported over internal)
    chunk_map: dict[str, CodeChunk] = {}
    for chunk in chunks:
        existing = chunk_map.get(chunk.id)
        if existing is None or (chunk.metadata.exported and not existing.metadata.exported):
            chunk_map[chunk.id] = chunk

    result = list(chunk_map.values())
    log.info("rechunk.complete", chunks=len(result), files=len(file_paths))
    return result


def _upsert_embeddings(
    client: QdrantClient,
    collection: str,
    chunks: list[CodeChunk],
    provider: BaseEmbeddingProvider,
) -> int:
    """Generate embeddings and upsert to Qdrant.

    Args:
        client: Connected Qdrant client.
        collection: Collection name.
        chunks: List of CodeChunk instances to embed.
        provider: Embedding provider instance.

    Returns:
        Number of chunks upserted.

    Raises:
        VectorStoreError: Embedding generation or upsert failed.
    """
    if not chunks:
        log.debug("embeddings.upsert_empty", collection=collection)
        return 0

    cfg = get_settings()
    batch_size = cfg.embedding_batch_size

    try:
        # Extract texts for embedding generation
        texts = [chunk.text for chunk in chunks]

        # Generate embeddings in batches
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_embeddings = provider.generate_batch(batch_texts)
            all_embeddings.extend(batch_embeddings)
            log.debug(
                "embeddings.batch_generated",
                batch=f"{i + 1}-{i + len(batch_texts)}",
                total=len(texts),
            )

        # Prepare Qdrant points with enriched payload
        from datetime import UTC, datetime

        indexed_at = datetime.now(UTC).isoformat()
        vectors = []
        for chunk, embedding in zip(chunks, all_embeddings, strict=False):
            # Enrich payload with metadata
            payload = chunk.model_dump()
            payload["indexed_at"] = indexed_at
            payload["aica_version"] = __version__

            vectors.append(
                {
                    "id": chunk.id,
                    "vector": embedding,
                    "payload": payload,
                }
            )

        # Upsert in batches
        upserted = client.upsert_vectors(vectors, collection_name=collection)
        log.info("embeddings.upserted", count=upserted, collection=collection)
        return upserted

    except Exception as exc:
        log.error(
            "embeddings.upsert_failed",
            collection=collection,
            chunks=len(chunks),
            error=str(exc),
        )
        raise VectorStoreError(f"Failed to upsert embeddings: {exc}") from exc


def _expand_affected_files(
    repo_path: Path,
    changed_files: list[str],
    deleted_files: list[str],
) -> set[str]:
    """Expand changed files to include files that depend on them.

    Uses cross-file detector to find files that import or call functions
    from the changed files. Excludes deleted files from re-indexing set.

    Args:
        repo_path: Absolute path to repository root.
        changed_files: List of modified file paths.
        deleted_files: List of deleted file paths.

    Returns:
        Set of file paths to re-embed (changed + importers + callers).
    """
    if not changed_files:
        return set()

    ast_dir = repo_path / ".repo_intelligence" / "ast"

    try:
        # Load AST data for cross-file detection
        imports_data = (
            json.loads((ast_dir / "imports.json").read_text(encoding="utf-8"))
            if (ast_dir / "imports.json").exists()
            else []
        )
        functions_data = (
            json.loads((ast_dir / "functions.json").read_text(encoding="utf-8"))
            if (ast_dir / "functions.json").exists()
            else []
        )
        calls_data = (
            json.loads((ast_dir / "call_graph.json").read_text(encoding="utf-8"))
            if (ast_dir / "call_graph.json").exists()
            else []
        )

        # Detect all affected files
        affected = detect_all_affected_files(
            changed_files,
            imports_data,
            functions_data,
            calls_data,
        )

        # Exclude deleted files (they only trigger deletion, not re-embedding)
        deleted_set = set(deleted_files) if deleted_files else set()
        result = affected - deleted_set

        log.info(
            "files.expanded",
            original=len(changed_files),
            affected=len(affected),
            final=len(result),
            deleted_excluded=len(deleted_set),
        )

        return result

    except (FileNotFoundError, json.JSONDecodeError) as exc:
        log.warning(
            "files.expansion_failed",
            error=str(exc),
            fallback="using original changed files",
        )
        # Fallback: just use the original changed files
        return set(changed_files) - set(deleted_files)


def _filter_by_content_hash(
    repo_path: Path,
    file_paths: set[str],
) -> set[str]:
    """Filter files by content hash to skip unchanged files.

    Computes SHA-256 hash of each file's content and compares against
    stored hash in vector metadata. Skips files with matching hash
    (e.g., comment-only changes that don't affect embeddings).

    Args:
        repo_path: Absolute path to repository root.
        file_paths: Set of file paths to check.

    Returns:
        Filtered set of file paths that need re-embedding.

    Note:
        This optimization requires metadata.content_hash field to be stored.
        If not present, all files are included (first-time indexing).
    """
    if not file_paths:
        return set()

    filtered = set()
    skipped = 0

    for file_path in file_paths:
        abs_path = repo_path / file_path
        if not abs_path.exists():
            log.debug("hash_filter.file_missing", file=file_path)
            filtered.add(file_path)
            continue

        try:
            # Compute current content hash
            content = abs_path.read_bytes()
            current_hash = hashlib.sha256(content).hexdigest()

            # TODO: Query Qdrant for existing chunks with this file
            # and check if any have matching content_hash in metadata.
            # For Phase 5 MVP, we'll skip this optimization and always
            # re-embed. Add in future enhancement.

            # Placeholder: Always include file (no hash comparison yet)
            filtered.add(file_path)

        except (OSError, IOError) as exc:
            log.warning(
                "hash_filter.read_error",
                file=file_path,
                error=str(exc),
            )
            filtered.add(file_path)

    if skipped > 0:
        log.info("hash_filter.skipped", count=skipped, total=len(file_paths))

    return filtered


def update_embeddings_for_files(
    repo_path: Path,
    changed_files: list[str],
    deleted_files: list[str] | None = None,
) -> EmbeddingUpdateSummary:
    """Update vector embeddings for changed files (incremental sync).

    Orchestrates the full incremental embedding update workflow:
    1. Expand to affected files (cross-file dependencies)
    2. Filter by content hash (skip unchanged)
    3. Delete embeddings for changed + deleted files
    4. Re-chunk changed files
    5. Generate & upsert embeddings
    6. Return summary

    Args:
        repo_path: Absolute path to repository root.
        changed_files: List of modified file paths (POSIX-relative).
        deleted_files: List of deleted file paths (optional).

    Returns:
        Summary with counts and timing.

    Raises:
        VectorStoreError: Embedding update failed.
    """
    start_time = time.time()
    deleted_files = deleted_files or []

    log.info(
        "embeddings.update_started",
        changed=len(changed_files),
        deleted=len(deleted_files),
    )

    try:
        # Get configuration
        cfg = get_settings()

        # Initialize clients
        qdrant = QdrantClient()
        qdrant.connect()

        provider = EmbeddingProvider.from_settings()
        collection = cfg.qdrant_collection_name

        # (1) Expand to affected files (importers + callers)
        affected_files = _expand_affected_files(
            repo_path,
            changed_files,
            deleted_files,
        )

        # (2) Filter by content hash (skip unchanged)
        files_to_reindex = _filter_by_content_hash(repo_path, affected_files)

        # (3) Delete embeddings for all changed + deleted files
        all_files_to_delete = list(set(changed_files) | set(deleted_files))
        _delete_embeddings_for_files(qdrant, collection, all_files_to_delete)

        # (4) Re-chunk changed files only (not deleted)
        chunks = _rechunk_files(repo_path, list(files_to_reindex))

        # (5) Generate & upsert embeddings
        chunks_created = _upsert_embeddings(qdrant, collection, chunks, provider)

        # (6) Build summary
        duration = time.time() - start_time
        summary = EmbeddingUpdateSummary(
            chunks_deleted=len(all_files_to_delete),  # Approximation (file count)
            chunks_created=chunks_created,
            chunks_updated=0,  # Delete-then-insert strategy
            files_processed=list(files_to_reindex),
            duration_seconds=duration,
        )

        log.info("embeddings.update_complete", summary=str(summary))
        return summary

    except Exception as exc:
        duration = time.time() - start_time
        log.error(
            "embeddings.update_failed",
            error=str(exc),
            duration=duration,
        )
        raise VectorStoreError(f"Embedding update failed: {exc}") from exc

    finally:
        # Cleanup: close connections
        try:
            if "qdrant" in locals():
                qdrant.close()
        except Exception as cleanup_exc:  # noqa: BLE001
            log.warning("embeddings.cleanup_error", error=str(cleanup_exc))

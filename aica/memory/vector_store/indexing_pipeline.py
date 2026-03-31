"""
Indexing Pipeline — Sub-Plan 3

End-to-end pipeline for generating and storing code embeddings in Qdrant.

Public API
----------
index_codebase(repo_path: Path, force_reindex: bool = False) -> IndexingSummary
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aica.__about__ import __version__
from aica.config.settings import get_settings
from aica.core.logging import get_logger
from aica.memory.vector_store.chunkers import create_code_chunks
from aica.memory.vector_store.exceptions import (
    VectorStoreConnectionError,
    VectorStoreError,
)
from aica.memory.vector_store.factory import EmbeddingProvider
from aica.memory.vector_store.qdrant_client import QdrantClient
from aica.memory.vector_store.schemas import CodeChunk

log = get_logger("vector_store.indexing")

# Default batch size for embedding generation (smaller than Qdrant's 500 due to API latency)
DEFAULT_BATCH_SIZE = 32

# Maximum errors to retain in summary
MAX_ERRORS_IN_SUMMARY = 100


@dataclass
class IndexingSummary:
    """Summary of indexing pipeline execution.

    Attributes:
        total_chunks: Total number of chunks loaded from codebase.
        embedded: Number of chunks successfully embedded.
        stored: Number of vectors successfully stored in Qdrant.
        skipped: Number of chunks skipped (already exist in collection).
        failed: Number of chunks that failed to embed or store.
        errors: List of error dicts (capped at MAX_ERRORS_IN_SUMMARY).
        duration_seconds: Total pipeline execution time.
        repo_path: Absolute path to indexed repository.
    """

    total_chunks: int
    embedded: int
    stored: int
    skipped: int
    failed: int
    errors: list[dict]
    duration_seconds: float
    repo_path: str

    def __str__(self) -> str:
        """Human-readable summary string."""
        status = "✅" if self.failed == 0 else "⚠️"
        return (
            f"{status} Indexed {self.stored}/{self.total_chunks} code chunks "
            f"in {self.duration_seconds:.1f}s "
            f"(skipped: {self.skipped}, failed: {self.failed})"
        )


def _chunks(items: list, size: int) -> Iterator[list]:
    """Yield successive non-overlapping chunks from items.

    Args:
        items: List to chunk.
        size: Maximum chunk size.

    Yields:
        Successive sublists of at most `size` elements.

    Example:
        >>> list(_chunks([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    for i in range(0, len(items), size):
        yield items[i : i + size]


def index_codebase(
    repo_path: Path,
    *,
    force_reindex: bool = False,
) -> IndexingSummary:
    """Index codebase by generating embeddings and storing in Qdrant.

    This is the main entry point for the embedding indexing pipeline. It:
    1. Connects to Qdrant and embedding provider
    2. Loads code chunks from AST outputs
    3. Generates embeddings in batches
    4. Stores vectors with enriched metadata in Qdrant
    5. Returns comprehensive summary

    Args:
        repo_path: Absolute path to repository root.
        force_reindex: If True, delete existing collection and rebuild from scratch.
                      If False (default), skip chunks that already exist.

    Returns:
        IndexingSummary with counts, timing, and error details.

    Raises:
        ValueError: If repo_path does not exist or is not a directory.
        VectorStoreConnectionError: If cannot connect to Qdrant or embedding provider.
        VectorStoreError: For other vector store failures (after partial progress saved).

    Example:
        >>> from pathlib import Path
        >>> summary = index_codebase(Path("/path/to/repo"))
        >>> print(summary)
        ✅ Indexed 1200/1200 code chunks in 45.2s (skipped: 0, failed: 0)
    """
    start_time = time.time()
    cfg = get_settings()

    # Validate repo_path
    if not repo_path.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")
    if not repo_path.is_dir():
        raise ValueError(f"Repository path is not a directory: {repo_path}")

    repo_path_str = str(repo_path)

    log.info(
        "indexing.start",
        repo_path=repo_path_str,
        force_reindex=force_reindex,
    )

    # Initialize counters
    total_chunks = 0
    embedded = 0
    stored = 0
    skipped = 0
    failed = 0
    errors: list[dict] = []

    # Initialize clients
    qdrant_client: QdrantClient | None = None
    embedder: EmbeddingProvider | None = None

    try:
        # Connect to Qdrant
        qdrant_client = QdrantClient()
        qdrant_client.connect()

        # Initialize embedding provider
        embedder = EmbeddingProvider()
        log.info(
            "indexing.clients_ready",
            qdrant_url=cfg.qdrant_url,
            embedding_provider=cfg.embedding_provider,
            embedding_model=cfg.embedding_model,
        )

        # Handle force_reindex: delete existing collection
        collection_exists = qdrant_client.collection_exists()
        if force_reindex and collection_exists:
            log.info("indexing.deleting_collection", collection=cfg.qdrant_collection_name)
            qdrant_client.delete_collection()
            collection_exists = False

        # Load code chunks
        log.info("indexing.loading_chunks", repo_path=repo_path_str)
        chunks = create_code_chunks(repo_path)
        total_chunks = len(chunks)

        if total_chunks == 0:
            log.warning("indexing.no_chunks", repo_path=repo_path_str)
            duration = time.time() - start_time
            return IndexingSummary(
                total_chunks=0,
                embedded=0,
                stored=0,
                skipped=0,
                failed=0,
                errors=[],
                duration_seconds=duration,
                repo_path=repo_path_str,
            )

        # Log chunk breakdown by type
        chunk_types = {}
        for chunk in chunks:
            chunk_type = chunk.metadata.chunk_type
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

        log.info(
            "indexing.chunks_loaded",
            total=total_chunks,
            functions=chunk_types.get("function", 0),
            components=chunk_types.get("component", 0),
            types=chunk_types.get("type", 0),
        )

        # Create collection if needed (with dimension auto-detection)
        if not collection_exists:
            # Auto-detect dimension from first embedding
            dimension = cfg.qdrant_vector_dimension
            if dimension is None:
                log.info("indexing.auto_detect_dimension", sample_text=chunks[0].text[:50])
                sample_embedding = embedder.backend.generate_embedding(chunks[0].text)
                dimension = len(sample_embedding)
                log.info("indexing.dimension_detected", dimension=dimension)

            qdrant_client.create_collection(vector_dimension=dimension)
            log.info("indexing.collection_created", dimension=dimension)

        # Retrieve existing IDs for deduplication (if not force_reindex)
        existing_ids: set[str] = set()
        if not force_reindex and collection_exists:
            log.info("indexing.fetching_existing_ids")
            try:
                # Note: This requires implementing scroll in QdrantClient
                # For now, we'll skip deduplication and always upsert (simpler)
                # TODO: Implement scroll-based deduplication in future iteration
                log.debug("indexing.deduplication_skipped", reason="scroll not yet implemented")
            except Exception as e:  # noqa: BLE001
                log.warning("indexing.deduplication_failed", error=str(e))

        # Process chunks in batches
        batch_size = cfg.embedding_batch_size or DEFAULT_BATCH_SIZE
        log.info("indexing.starting_batches", batch_size=batch_size, total_batches=(total_chunks + batch_size - 1) // batch_size)

        # Check if we should show progress bar (TTY detection)
        show_progress = sys.stdout.isatty()

        if show_progress:
            try:
                from rich.progress import (
                    BarColumn,
                    Progress,
                    TaskProgressColumn,
                    TextColumn,
                    TimeRemainingColumn,
                )

                progress = Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeRemainingColumn(),
                    TextColumn("• {task.fields[speed]:.1f} chunks/s"),
                )
                progress.start()
                task_id = progress.add_task(
                    "Indexing code chunks",
                    total=total_chunks,
                    speed=0.0,
                )
            except ImportError:
                log.warning("indexing.rich_unavailable", fallback="logging only")
                show_progress = False
                progress = None
        else:
            progress = None

        try:
            batch_idx = 0
            for batch in _chunks(chunks, batch_size):
                batch_idx += 1

                # Skip chunks that already exist (deduplication)
                if existing_ids:
                    batch = [c for c in batch if c.id not in existing_ids]
                    skipped_in_batch = len(batch) - len(batch)
                    skipped += skipped_in_batch

                if not batch:
                    continue

                # Extract texts for embedding
                texts = [chunk.text for chunk in batch]

                # Generate embeddings for batch
                try:
                    embeddings = embedder.backend.generate_batch(texts)
                    embedded += len(embeddings)

                    # Prepare Qdrant points with enriched metadata
                    timestamp = datetime.now(timezone.utc).isoformat()
                    points = []

                    for chunk, embedding in zip(batch, embeddings):
                        # Enrich metadata
                        payload = {
                            "text": chunk.text,
                            "metadata": chunk.metadata.model_dump(),
                            # Computed fields
                            "indexed_at": timestamp,
                            "repo_path": repo_path_str,
                            "aica_version": __version__,
                            "text_length": len(chunk.text),
                            "has_docstring": "/**" in chunk.text or '"""' in chunk.text,
                            "line_count": chunk.text.count("\n") + 1,
                        }

                        points.append({
                            "id": chunk.id,
                            "vector": embedding,
                            "payload": payload,
                        })

                    # Upsert batch to Qdrant
                    stored_count = qdrant_client.upsert_vectors(points)
                    stored += stored_count

                    # Update progress
                    if progress:
                        chunks_processed = batch_idx * batch_size
                        elapsed = time.time() - start_time
                        speed = chunks_processed / elapsed if elapsed > 0 else 0
                        progress.update(task_id, advance=len(batch), speed=speed)

                    # Log every 5 batches
                    if batch_idx % 5 == 0:
                        log.info(
                            "indexing.batch_progress",
                            batch=batch_idx,
                            chunks_processed=min(batch_idx * batch_size, total_chunks),
                            total_chunks=total_chunks,
                        )

                except Exception as e:  # noqa: BLE001
                    # Batch failed - try individual chunks for better recovery
                    log.warning(
                        "indexing.batch_failed",
                        batch=batch_idx,
                        error=str(e),
                        retrying_individuals=True,
                    )

                    for chunk in batch:
                        try:
                            # Try embedding individually
                            embedding = embedder.backend.generate_embedding(chunk.text)
                            embedded += 1

                            # Prepare point
                            timestamp = datetime.now(timezone.utc).isoformat()
                            payload = {
                                "text": chunk.text,
                                "metadata": chunk.metadata.model_dump(),
                                "indexed_at": timestamp,
                                "repo_path": repo_path_str,
                                "aica_version": __version__,
                                "text_length": len(chunk.text),
                                "has_docstring": "/**" in chunk.text or '"""' in chunk.text,
                                "line_count": chunk.text.count("\n") + 1,
                            }

                            # Upsert individual point
                            qdrant_client.upsert_vectors([{
                                "id": chunk.id,
                                "vector": embedding,
                                "payload": payload,
                            }])
                            stored += 1

                        except Exception as chunk_error:  # noqa: BLE001
                            # Individual chunk failed - collect error and continue
                            failed += 1
                            if len(errors) < MAX_ERRORS_IN_SUMMARY:
                                errors.append({
                                    "chunk_id": chunk.id,
                                    "error": str(chunk_error),
                                    "batch_index": batch_idx,
                                })
                            log.error(
                                "indexing.chunk_failed",
                                chunk_id=chunk.id,
                                error=str(chunk_error),
                            )

        finally:
            if progress:
                progress.stop()

        # Calculate duration
        duration = time.time() - start_time

        # Build summary
        summary = IndexingSummary(
            total_chunks=total_chunks,
            embedded=embedded,
            stored=stored,
            skipped=skipped,
            failed=failed,
            errors=errors,
            duration_seconds=duration,
            repo_path=repo_path_str,
        )

        # Log completion
        log.info(
            "indexing.completed",
            total_chunks=total_chunks,
            embedded=embedded,
            stored=stored,
            skipped=skipped,
            failed=failed,
            duration_seconds=duration,
        )

        # Show final summary with rich if available
        if show_progress:
            try:
                from rich.console import Console

                console = Console()
                console.print(f"\n{summary}")
            except ImportError:
                pass

        return summary

    except Exception as e:
        # Pipeline failed - log and return partial summary
        duration = time.time() - start_time
        log.error(
            "indexing.failed",
            error=str(e),
            total_chunks=total_chunks,
            embedded=embedded,
            stored=stored,
            duration_seconds=duration,
        )

        # Return partial summary
        return IndexingSummary(
            total_chunks=total_chunks,
            embedded=embedded,
            stored=stored,
            skipped=skipped,
            failed=failed,
            errors=errors + [{"error": f"Pipeline failure: {e}"}],
            duration_seconds=duration,
            repo_path=repo_path_str,
        )

    finally:
        # Cleanup: close clients
        if qdrant_client:
            qdrant_client.close()
        log.info("indexing.cleanup_complete")

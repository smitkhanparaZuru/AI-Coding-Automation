"""Unit tests for indexing pipeline (Sub-plan 3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aica.memory.vector_store.indexing_pipeline import (
    IndexingSummary,
    _chunks,
    index_codebase,
)
from aica.memory.vector_store.schemas import ChunkMetadata, CodeChunk


def test_chunks_generator():
    """Test _chunks() batch generator helper."""
    items = list(range(10))

    # Test normal batching
    batches = list(_chunks(items, 3))
    assert len(batches) == 4
    assert batches[0] == [0, 1, 2]
    assert batches[1] == [3, 4, 5]
    assert batches[2] == [6, 7, 8]
    assert batches[3] == [9]

    # Test exact division
    batches = list(_chunks(items, 5))
    assert len(batches) == 2
    assert batches[0] == [0, 1, 2, 3, 4]
    assert batches[1] == [5, 6, 7, 8, 9]

    # Test batch size larger than list
    batches = list(_chunks(items, 20))
    assert len(batches) == 1
    assert batches[0] == items

    # Test empty list
    batches = list(_chunks([], 5))
    assert len(batches) == 0


def test_indexing_summary_str():
    """Test IndexingSummary string representation."""
    summary = IndexingSummary(
        total_chunks=100,
        embedded=98,
        stored=98,
        skipped=0,
        failed=2,
        errors=[],
        duration_seconds=45.2,
        repo_path="/path/to/repo",
    )

    result = str(summary)
    assert "98/100" in result
    assert "45.2s" in result
    assert "failed: 2" in result
    assert "⚠️" in result  # Warning icon due to failures

    # Test success case
    summary_success = IndexingSummary(
        total_chunks=100,
        embedded=100,
        stored=100,
        skipped=0,
        failed=0,
        errors=[],
        duration_seconds=30.0,
        repo_path="/path/to/repo",
    )

    result_success = str(summary_success)
    assert "✅" in result_success  # Success icon


def test_index_codebase_invalid_path():
    """Test index_codebase with invalid repository path."""
    # Non-existent path
    with pytest.raises(ValueError, match="does not exist"):
        index_codebase(Path("/nonexistent/path"))

    # File instead of directory
    with patch("pathlib.Path.exists", return_value=True), patch(
        "pathlib.Path.is_dir", return_value=False
    ):
        with pytest.raises(ValueError, match="not a directory"):
            index_codebase(Path("/some/file.txt"))


@patch("aica.memory.vector_store.indexing_pipeline.QdrantClient")
@patch("aica.memory.vector_store.indexing_pipeline.EmbeddingProvider")
@patch("aica.memory.vector_store.indexing_pipeline.create_code_chunks")
def test_index_codebase_no_chunks(
    mock_create_chunks, mock_embedder, mock_qdrant, tmp_path: Path
):
    """Test index_codebase returns early when no chunks found."""
    # Setup mocks
    mock_create_chunks.return_value = []
    mock_qdrant_instance = MagicMock()
    mock_qdrant.return_value = mock_qdrant_instance

    # Run indexing
    summary = index_codebase(tmp_path)

    # Verify early return
    assert summary.total_chunks == 0
    assert summary.embedded == 0
    assert summary.stored == 0
    assert summary.failed == 0

    # Verify no embedding or upsert calls
    mock_qdrant_instance.create_collection.assert_not_called()
    mock_qdrant_instance.upsert_vectors.assert_not_called()


@patch("aica.memory.vector_store.indexing_pipeline.QdrantClient")
@patch("aica.memory.vector_store.indexing_pipeline.EmbeddingProvider")
@patch("aica.memory.vector_store.indexing_pipeline.create_code_chunks")
@patch("aica.memory.vector_store.indexing_pipeline.sys.stdout.isatty", return_value=False)
def test_index_codebase_success(
    mock_isatty, mock_create_chunks, mock_embedder_cls, mock_qdrant_cls, tmp_path: Path
):
    """Test successful indexing pipeline with mocked dependencies."""
    # Create mock chunks
    mock_chunks = []
    for i in range(10):
        metadata = ChunkMetadata(
            file=f"src/file{i}.ts",
            line=10,
            chunk_type="function",
            name=f"func{i}",
            exported=True,
            language="typescript",
        )
        chunk = CodeChunk(
            id=f"src/file{i}.ts:function:func{i}:10",
            text=f"function func{i}() {{ return {i}; }}",
            metadata=metadata,
        )
        mock_chunks.append(chunk)

    mock_create_chunks.return_value = mock_chunks

    # Setup Qdrant mock
    mock_qdrant_instance = MagicMock()
    mock_qdrant_instance.collection_exists.return_value = False
    mock_qdrant_instance.upsert_vectors.return_value = 10
    mock_qdrant_cls.return_value = mock_qdrant_instance

    # Setup embedding provider mock
    mock_embedder_instance = MagicMock()
    mock_embedder_instance.backend.generate_embedding.return_value = [0.1] * 384
    mock_embedder_instance.backend.generate_batch.return_value = [[0.1] * 384] * 10
    mock_embedder_cls.return_value = mock_embedder_instance

    # Run indexing
    summary = index_codebase(tmp_path, force_reindex=False)

    # Verify summary
    assert summary.total_chunks == 10
    assert summary.embedded == 10
    assert summary.stored == 10
    assert summary.skipped == 0
    assert summary.failed == 0
    assert len(summary.errors) == 0
    assert summary.duration_seconds > 0

    # Verify client calls
    mock_qdrant_instance.connect.assert_called_once()
    mock_qdrant_instance.collection_exists.assert_called()
    mock_qdrant_instance.create_collection.assert_called_once()
    mock_qdrant_instance.upsert_vectors.assert_called_once()
    mock_qdrant_instance.close.assert_called_once()

    # Verify embedder calls
    mock_embedder_instance.backend.generate_embedding.assert_called_once()  # For dimension detection
    mock_embedder_instance.backend.generate_batch.assert_called_once()


@patch("aica.memory.vector_store.indexing_pipeline.QdrantClient")
@patch("aica.memory.vector_store.indexing_pipeline.EmbeddingProvider")
@patch("aica.memory.vector_store.indexing_pipeline.create_code_chunks")
@patch("aica.memory.vector_store.indexing_pipeline.sys.stdout.isatty", return_value=False)
def test_index_codebase_force_reindex(
    mock_isatty, mock_create_chunks, mock_embedder_cls, mock_qdrant_cls, tmp_path: Path
):
    """Test force_reindex deletes existing collection."""
    # Create mock chunks
    mock_chunks = []
    for i in range(5):
        metadata = ChunkMetadata(
            file=f"src/file{i}.ts",
            line=10,
            chunk_type="function",
            name=f"func{i}",
            exported=True,
            language="typescript",
        )
        chunk = CodeChunk(
            id=f"src/file{i}.ts:function:func{i}:10",
            text=f"function func{i}() {{ return {i}; }}",
            metadata=metadata,
        )
        mock_chunks.append(chunk)

    mock_create_chunks.return_value = mock_chunks

    # Setup Qdrant mock - collection exists
    mock_qdrant_instance = MagicMock()
    mock_qdrant_instance.collection_exists.return_value = True
    mock_qdrant_instance.upsert_vectors.return_value = 5
    mock_qdrant_cls.return_value = mock_qdrant_instance

    # Setup embedding provider mock
    mock_embedder_instance = MagicMock()
    mock_embedder_instance.backend.generate_embedding.return_value = [0.1] * 384
    mock_embedder_instance.backend.generate_batch.return_value = [[0.1] * 384] * 5
    mock_embedder_cls.return_value = mock_embedder_instance

    # Run indexing with force_reindex
    summary = index_codebase(tmp_path, force_reindex=True)

    # Verify collection was deleted
    mock_qdrant_instance.delete_collection.assert_called_once()

    # Verify new collection created
    mock_qdrant_instance.create_collection.assert_called_once()

    # Verify indexing completed
    assert summary.total_chunks == 5
    assert summary.stored == 5


@patch("aica.memory.vector_store.indexing_pipeline.QdrantClient")
@patch("aica.memory.vector_store.indexing_pipeline.EmbeddingProvider")
@patch("aica.memory.vector_store.indexing_pipeline.create_code_chunks")
@patch("aica.memory.vector_store.indexing_pipeline.sys.stdout.isatty", return_value=False)
def test_index_codebase_batch_failure_recovery(
    mock_isatty, mock_create_chunks, mock_embedder_cls, mock_qdrant_cls, tmp_path: Path
):
    """Test pipeline handles batch failures and retries individuals."""
    # Create mock chunks
    mock_chunks = []
    for i in range(10):
        metadata = ChunkMetadata(
            file=f"src/file{i}.ts",
            line=10,
            chunk_type="function",
            name=f"func{i}",
            exported=True,
            language="typescript",
        )
        chunk = CodeChunk(
            id=f"src/file{i}.ts:function:func{i}:10",
            text=f"function func{i}() {{ return {i}; }}",
            metadata=metadata,
        )
        mock_chunks.append(chunk)

    mock_create_chunks.return_value = mock_chunks

    # Setup Qdrant mock
    mock_qdrant_instance = MagicMock()
    mock_qdrant_instance.collection_exists.return_value = False
    mock_qdrant_instance.upsert_vectors.return_value = 1
    mock_qdrant_cls.return_value = mock_qdrant_instance

    # Setup embedding provider mock - batch fails, individuals succeed
    mock_embedder_instance = MagicMock()
    mock_embedder_instance.backend.generate_embedding.return_value = [0.1] * 384
    # First call for dimension detection, second call fails (batch), then individual calls succeed
    mock_embedder_instance.backend.generate_batch.side_effect = [
        ValueError("Batch embedding failed")
    ]
    mock_embedder_cls.return_value = mock_embedder_instance

    # Run indexing
    summary = index_codebase(tmp_path, force_reindex=False)

    # Verify pipeline continued despite batch failure
    assert summary.total_chunks == 10
    # Individual retries should succeed (dimension detection not counted in embedded)
    assert summary.embedded == 10
    assert summary.stored == 10
    assert summary.failed == 0


@patch("aica.memory.vector_store.indexing_pipeline.QdrantClient")
@patch("aica.memory.vector_store.indexing_pipeline.EmbeddingProvider")
@patch("aica.memory.vector_store.indexing_pipeline.create_code_chunks")
@patch("aica.memory.vector_store.indexing_pipeline.sys.stdout.isatty", return_value=False)
def test_index_codebase_individual_chunk_failure(
    mock_isatty, mock_create_chunks, mock_embedder_cls, mock_qdrant_cls, tmp_path: Path
):
    """Test pipeline collects errors when individual chunks fail."""
    # Create mock chunks
    mock_chunks = []
    for i in range(5):
        metadata = ChunkMetadata(
            file=f"src/file{i}.ts",
            line=10,
            chunk_type="function",
            name=f"func{i}",
            exported=True,
            language="typescript",
        )
        chunk = CodeChunk(
            id=f"src/file{i}.ts:function:func{i}:10",
            text=f"function func{i}() {{ return {i}; }}",
            metadata=metadata,
        )
        mock_chunks.append(chunk)

    mock_create_chunks.return_value = mock_chunks

    # Setup Qdrant mock
    mock_qdrant_instance = MagicMock()
    mock_qdrant_instance.collection_exists.return_value = False
    mock_qdrant_cls.return_value = mock_qdrant_instance

    # Setup embedding provider mock - batch fails, some individuals fail
    mock_embedder_instance = MagicMock()
    # Dimension detection succeeds
    call_count = [0]

    def embedding_side_effect(text):
        call_count[0] += 1
        if call_count[0] == 1:  # First call for dimension detection
            return [0.1] * 384
        # Fail on chunks with index 2 and 4
        if "func2" in text or "func4" in text:
            raise ValueError("Embedding generation failed")
        return [0.1] * 384

    mock_embedder_instance.backend.generate_embedding.side_effect = embedding_side_effect
    mock_embedder_instance.backend.generate_batch.side_effect = ValueError("Batch failed")
    mock_embedder_cls.return_value = mock_embedder_instance

    # Setup upsert to succeed
    mock_qdrant_instance.upsert_vectors.return_value = 1

    # Run indexing
    summary = index_codebase(tmp_path, force_reindex=False)

    # Verify partial success
    assert summary.total_chunks == 5
    assert summary.failed == 2  # chunks 2 and 4
    assert summary.stored == 3  # chunks 0, 1, 3
    assert len(summary.errors) == 2

    # Verify error details
    error_chunk_ids = [err["chunk_id"] for err in summary.errors]
    assert "src/file2.ts:function:func2:10" in error_chunk_ids
    assert "src/file4.ts:function:func4:10" in error_chunk_ids

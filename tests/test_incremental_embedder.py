"""
Tests for Incremental Embedding Updater — Sub-Plan 6

Tests the embedding sync integration with automatic updates on file changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aica.memory.vector_store.incremental_updater import (
    EmbeddingUpdateSummary,
    _delete_embeddings_for_files,
    _expand_affected_files,
    _filter_by_content_hash,
    _rechunk_files,
    _upsert_embeddings,
    update_embeddings_for_files,
)
from aica.memory.vector_store.schemas import ChunkMetadata, CodeChunk


# ------------------------------------------------------------------
# Test: Batch Deletion
# ------------------------------------------------------------------


def test_delete_embeddings_for_files_builds_correct_filter():
    """Test that batch deletion builds correct Qdrant filter."""
    mock_client = MagicMock()
    file_paths = ["src/auth.ts", "src/utils.ts", "src/api.ts"]

    _delete_embeddings_for_files(mock_client, "test-collection", file_paths)

    # Verify delete_by_filter was called with correct filter
    mock_client.delete_by_filter.assert_called_once()
    call_args = mock_client.delete_by_filter.call_args
    filter_dict = call_args.kwargs["filter_dict"]

    assert "must" in filter_dict
    assert len(filter_dict["must"]) == 1
    assert filter_dict["must"][0]["key"] == "file"
    assert filter_dict["must"][0]["match"]["any"] == file_paths


def test_delete_embeddings_for_files_empty_list():
    """Test that empty file list is handled gracefully."""
    mock_client = MagicMock()

    _delete_embeddings_for_files(mock_client, "test-collection", [])

    # Should not call delete_by_filter
    mock_client.delete_by_filter.assert_not_called()


# ------------------------------------------------------------------
# Test: Re-chunking
# ------------------------------------------------------------------


def test_rechunk_files_filters_to_changed_files(tmp_path: Path):
    """Test that re-chunking only processes specified files."""
    # Setup AST directory with mock data
    ast_dir = tmp_path / ".repo_intelligence" / "ast"
    ast_dir.mkdir(parents=True)

    # Mock functions.json with 3 functions from different files
    functions_data = [
        {"file": "src/auth.ts", "name": "login", "line": 10, "exported": True},
        {"file": "src/utils.ts", "name": "hash", "line": 5, "exported": True},
        {"file": "src/api.ts", "name": "fetch", "line": 20, "exported": False},
    ]
    (ast_dir / "functions.json").write_text(json.dumps(functions_data))

    # Create source files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.ts").write_text("export function login() {}")
    (tmp_path / "src" / "utils.ts").write_text("export function hash() {}")
    (tmp_path / "src" / "api.ts").write_text("function fetch() {}")

    # Re-chunk only auth.ts and utils.ts (not api.ts)
    changed_files = ["src/auth.ts", "src/utils.ts"]

    with patch("aica.memory.vector_store.incremental_updater.chunk_functions") as mock_chunk:
        mock_chunk.return_value = []  # Return empty for simplicity
        _rechunk_files(tmp_path, changed_files)

        # Verify chunk_functions was called with filtered data (only 2 files)
        mock_chunk.assert_called_once()
        filtered_functions = mock_chunk.call_args[0][0]
        assert len(filtered_functions) == 2
        assert all(fn["file"] in changed_files for fn in filtered_functions)


def test_rechunk_files_handles_missing_ast():
    """Test that missing AST files are handled gracefully."""
    tmp_path = Path("/nonexistent")
    result = _rechunk_files(tmp_path, ["src/auth.ts"])

    # Should return empty list, not crash
    assert result == []


# ------------------------------------------------------------------
# Test: Embedding Upsert
# ------------------------------------------------------------------


def test_upsert_embeddings_enriches_payload():
    """Test that embeddings are enriched with metadata."""
    mock_client = MagicMock()
    mock_provider = MagicMock()
    mock_provider.generate_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]

    chunks = [
        CodeChunk(
            id="src/auth.ts:function:login:10",
            text="function login() {}",
            metadata=ChunkMetadata(
                file="src/auth.ts",
                line=10,
                chunk_type="function",
                name="login",
                exported=True,
            ),
        ),
        CodeChunk(
            id="src/utils.ts:function:hash:5",
            text="function hash() {}",
            metadata=ChunkMetadata(
                file="src/utils.ts",
                line=5,
                chunk_type="function",
                name="hash",
                exported=True,
            ),
        ),
    ]

    _upsert_embeddings(mock_client, "test-collection", chunks, mock_provider)

    # Verify upsert_vectors was called
    mock_client.upsert_vectors.assert_called_once()
    vectors = mock_client.upsert_vectors.call_args[0][0]

    assert len(vectors) == 2
    # Check that payload includes enriched metadata
    assert "indexed_at" in vectors[0]["payload"]
    assert "aica_version" in vectors[0]["payload"]


def test_upsert_embeddings_empty_chunks():
    """Test that empty chunks list is handled gracefully."""
    mock_client = MagicMock()
    mock_provider = MagicMock()

    result = _upsert_embeddings(mock_client, "test-collection", [], mock_provider)

    assert result == 0
    mock_client.upsert_vectors.assert_not_called()


# ------------------------------------------------------------------
# Test: Cross-File Expansion
# ------------------------------------------------------------------


def test_expand_affected_files_includes_importers(tmp_path: Path):
    """Test that expansion includes files that import changed files."""
    # Setup AST directory
    ast_dir = tmp_path / ".repo_intelligence" / "ast"
    ast_dir.mkdir(parents=True)

    # Mock data: file B imports from file A
    imports_data = [
        {"file": "src/api.ts", "from": "src/auth.ts", "import": "login"},
    ]
    (ast_dir / "imports.json").write_text(json.dumps(imports_data))
    (ast_dir / "functions.json").write_text(json.dumps([]))
    (ast_dir / "call_graph.json").write_text(json.dumps([]))

    # Change auth.ts
    changed_files = ["src/auth.ts"]
    affected = _expand_affected_files(tmp_path, changed_files, [])

    # Should include both auth.ts (changed) and api.ts (importer)
    assert "src/auth.ts" in affected
    assert "src/api.ts" in affected


def test_expand_affected_files_excludes_deleted():
    """Test that deleted files are excluded from re-indexing set."""
    tmp_path = Path("/tmp")
    ast_dir = tmp_path / ".repo_intelligence" / "ast"

    # Mock: file deleted.ts was deleted but is in expansion set
    changed_files = ["src/auth.ts"]
    deleted_files = ["src/deleted.ts"]

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value="[]"):
            affected = _expand_affected_files(tmp_path, changed_files, deleted_files)

    # deleted.ts should not be in the re-indexing set
    assert "src/deleted.ts" not in affected


# ------------------------------------------------------------------
# Test: Content Hash Filtering
# ------------------------------------------------------------------


def test_filter_by_content_hash_includes_all_for_mvp(tmp_path: Path):
    """Test that hash filtering includes all files (MVP implementation)."""
    # Create test files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.ts").write_text("function login() {}")

    file_paths = {"src/auth.ts"}
    filtered = _filter_by_content_hash(tmp_path, file_paths)

    # For MVP, should include all files (no optimization)
    assert filtered == file_paths


def test_filter_by_content_hash_handles_missing_files(tmp_path: Path):
    """Test that missing files are still included."""
    file_paths = {"src/nonexistent.ts"}
    filtered = _filter_by_content_hash(tmp_path, file_paths)

    # Should include file (will fail gracefully during chunking)
    assert "src/nonexistent.ts" in filtered


# ------------------------------------------------------------------
# Test: Main Orchestrator
# ------------------------------------------------------------------


def test_update_embeddings_for_files_summary(tmp_path: Path):
    """Test that orchestrator returns correct summary."""
    # Setup mock environment
    ast_dir = tmp_path / ".repo_intelligence" / "ast"
    ast_dir.mkdir(parents=True)
    (ast_dir / "imports.json").write_text("[]")
    (ast_dir / "functions.json").write_text("[]")
    (ast_dir / "call_graph.json").write_text("[]")

    with patch("aica.memory.vector_store.incremental_updater.QdrantClient") as MockQdrant:
        with patch("aica.memory.vector_store.incremental_updater.EmbeddingProvider"):
            mock_client = MagicMock()
            MockQdrant.return_value = mock_client

            changed_files = ["src/auth.ts"]
            deleted_files = ["src/old.ts"]

            summary = update_embeddings_for_files(tmp_path, changed_files, deleted_files)

            assert isinstance(summary, EmbeddingUpdateSummary)
            assert summary.chunks_deleted == 2  # Changed + deleted
            assert summary.duration_seconds >= 0


def test_update_embeddings_for_files_closes_connection():
    """Test that Qdrant connection is closed after update."""
    tmp_path = Path("/tmp")

    with patch("aica.memory.vector_store.incremental_updater.QdrantClient") as MockQdrant:
        with patch("aica.memory.vector_store.incremental_updater.EmbeddingProvider"):
            with patch("aica.memory.vector_store.incremental_updater._expand_affected_files"):
                with patch("aica.memory.vector_store.incremental_updater._filter_by_content_hash"):
                    with patch("aica.memory.vector_store.incremental_updater._delete_embeddings_for_files"):
                        with patch("aica.memory.vector_store.incremental_updater._rechunk_files"):
                            with patch("aica.memory.vector_store.incremental_updater._upsert_embeddings"):
                                mock_client = MagicMock()
                                MockQdrant.return_value = mock_client

                                update_embeddings_for_files(tmp_path, ["src/auth.ts"], [])

                                # Verify connection was closed
                                mock_client.close.assert_called_once()


# ------------------------------------------------------------------
# Test: EmbeddingUpdateSummary
# ------------------------------------------------------------------


def test_embedding_update_summary_str():
    """Test that summary formats correctly."""
    summary = EmbeddingUpdateSummary(
        chunks_deleted=10,
        chunks_created=15,
        chunks_updated=0,
        files_processed=["src/auth.ts", "src/api.ts"],
        duration_seconds=2.5,
    )

    str_repr = str(summary)
    assert "deleted 10 chunks" in str_repr
    assert "created 15 chunks" in str_repr
    assert "2 files" in str_repr
    assert "2.50s" in str_repr

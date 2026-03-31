"""
Tests for Semantic Code Retrieval — Sub-Plan 4.7

Unit tests for search functionality, filtering, re-ranking, and result formatting.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aica.memory.vector_store.exceptions import VectorStoreQueryError
from aica.memory.vector_store.retriever import (
    _rerank_results,
    build_context_from_results,
    build_qdrant_filter,
    format_search_results,
    search_code,
)
from aica.memory.vector_store.schemas import (
    ChunkMetadata,
    CodeChunk,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_chunk(
    chunk_id: str = "file.ts:testFunc:function:10",
    name: str = "testFunc",
    chunk_type: str = "function",
    exported: bool = False,
    feature: str | None = None,
    text: str = "function testFunc() {\n  return true;\n}",
) -> CodeChunk:
    """Create a test CodeChunk."""
    return CodeChunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            file="src/file.ts",
            line=10,
            chunk_type=chunk_type,
            name=name,
            exported=exported,
            feature=feature,
            language="typescript",
        ),
        embedding=None,
    )


def _make_mock_qdrant_client() -> MagicMock:
    """Create a mock QdrantClient."""
    mock_client = MagicMock()
    mock_client.search.return_value = []
    return mock_client


def _make_mock_embedding_provider() -> MagicMock:
    """Create a mock EmbeddingProvider."""
    mock_provider = MagicMock()
    mock_provider.generate_embedding.return_value = [0.1] * 384  # 384-dim vector
    return mock_provider


# ---------------------------------------------------------------------------
# build_qdrant_filter()
# ---------------------------------------------------------------------------


class TestBuildQdrantFilter:
    def test_empty_filters(self) -> None:
        """No filters returns None."""
        result = build_qdrant_filter({})
        assert result is None

    def test_chunk_type_filter(self) -> None:
        """Chunk type creates exact match condition."""
        result = build_qdrant_filter({"chunk_type": "function"})
        assert result == {
            "must": [{"key": "chunk_type", "match": {"value": "function"}}]
        }

    def test_exported_only_filter(self) -> None:
        """Exported only creates boolean match condition."""
        result = build_qdrant_filter({"exported_only": True})
        assert result == {"must": [{"key": "exported", "match": {"value": True}}]}

    def test_feature_filter(self) -> None:
        """Feature creates exact match condition."""
        result = build_qdrant_filter({"feature": "auth"})
        assert result == {"must": [{"key": "feature", "match": {"value": "auth"}}]}

    def test_line_range_filters(self) -> None:
        """Min/max lines create range condition."""
        result = build_qdrant_filter({"min_lines": 10, "max_lines": 100})
        assert result == {"must": [{"range": {"key": "line", "gte": 10, "lte": 100}}]}

    def test_combined_filters(self) -> None:
        """Multiple filters create multiple must conditions."""
        result = build_qdrant_filter({
            "chunk_type": "function",
            "exported_only": True,
            "feature": "auth",
        })
        assert len(result["must"]) == 3
        assert {"key": "chunk_type", "match": {"value": "function"}} in result["must"]
        assert {"key": "exported", "match": {"value": True}} in result["must"]
        assert {"key": "feature", "match": {"value": "auth"}} in result["must"]

    def test_file_pattern_ignored(self) -> None:
        """File pattern is not converted to Qdrant filter (handled post-search)."""
        result = build_qdrant_filter({"file_pattern": "src/**/*.ts"})
        assert result is None


# ---------------------------------------------------------------------------
# _rerank_results()
# ---------------------------------------------------------------------------


class TestRerankResults:
    def test_boost_exported(self) -> None:
        """Exported entities get +0.05 boost."""
        chunk_exported = _make_test_chunk(name="exported", exported=True)
        chunk_internal = _make_test_chunk(name="internal", exported=False)

        results = [
            SearchResult(score=0.8, chunk=chunk_exported, explanation="", adjusted_score=0.8),
            SearchResult(score=0.8, chunk=chunk_internal, explanation="", adjusted_score=0.8),
        ]

        reranked = _rerank_results(results)
        assert reranked[0].chunk.metadata.name == "exported"
        assert reranked[0].adjusted_score == pytest.approx(0.85)  # 0.8 + 0.05

    def test_boost_docstring(self) -> None:
        """Entities with docstrings get +0.03 boost."""
        chunk_with_doc = _make_test_chunk(
            name="withDoc",
            text="/**\n * Documentation\n */\nfunction withDoc() {}",
        )
        chunk_without_doc = _make_test_chunk(
            name="withoutDoc",
            text="function withoutDoc() {}",
        )

        results = [
            SearchResult(score=0.7, chunk=chunk_with_doc, explanation="", adjusted_score=0.7),
            SearchResult(score=0.7, chunk=chunk_without_doc, explanation="", adjusted_score=0.7),
        ]

        reranked = _rerank_results(results)
        assert reranked[0].chunk.metadata.name == "withDoc"
        assert reranked[0].adjusted_score == 0.73  # 0.7 + 0.03

    def test_boost_same_feature(self) -> None:
        """Entities in same feature get +0.04 boost."""
        chunk_auth = _make_test_chunk(name="authFunc", feature="auth")
        chunk_other = _make_test_chunk(name="otherFunc", feature="billing")

        results = [
            SearchResult(score=0.75, chunk=chunk_auth, explanation="", adjusted_score=0.75),
            SearchResult(score=0.75, chunk=chunk_other, explanation="", adjusted_score=0.75),
        ]

        reranked = _rerank_results(results, context_feature="auth")
        assert reranked[0].chunk.metadata.name == "authFunc"
        assert reranked[0].adjusted_score == 0.79  # 0.75 + 0.04

    def test_combined_boosts(self) -> None:
        """Multiple boosts are cumulative."""
        chunk = _make_test_chunk(
            name="superFunc",
            exported=True,
            feature="auth",
            text="/** Doc */\nfunction superFunc() {}",
        )

        results = [
            SearchResult(score=0.8, chunk=chunk, explanation="", adjusted_score=0.8),
        ]

        reranked = _rerank_results(results, context_feature="auth")
        # 0.8 + 0.05 (exported) + 0.03 (docstring) + 0.04 (feature) = 0.92
        assert reranked[0].adjusted_score == pytest.approx(0.92)

    def test_cap_at_one(self) -> None:
        """Adjusted score is capped at 1.0."""
        chunk = _make_test_chunk(exported=True, text="/** Doc */\nfunction test() {}")

        results = [
            SearchResult(score=0.95, chunk=chunk, explanation="", adjusted_score=0.95),
        ]

        reranked = _rerank_results(results)
        # 0.95 + 0.05 + 0.03 = 1.03, but capped at 1.0
        assert reranked[0].adjusted_score == 1.0

    def test_sort_by_adjusted_score(self) -> None:
        """Results are sorted by adjusted_score descending."""
        chunk1 = _make_test_chunk(name="func1", exported=False)
        chunk2 = _make_test_chunk(name="func2", exported=True)
        chunk3 = _make_test_chunk(name="func3", exported=False)

        results = [
            SearchResult(score=0.9, chunk=chunk1, explanation="", adjusted_score=0.9),
            SearchResult(score=0.7, chunk=chunk2, explanation="", adjusted_score=0.7),
            SearchResult(score=0.85, chunk=chunk3, explanation="", adjusted_score=0.85),
        ]

        reranked = _rerank_results(results)
        # After boost: func1=0.9, func2=0.75, func3=0.85
        # Sorted: func1 (0.9), func3 (0.85), func2 (0.75)
        assert reranked[0].chunk.metadata.name == "func1"
        assert reranked[1].chunk.metadata.name == "func3"
        assert reranked[2].chunk.metadata.name == "func2"


# ---------------------------------------------------------------------------
# search_code()
# ---------------------------------------------------------------------------


class TestSearchCode:
    def test_search_with_mocked_clients(self) -> None:
        """Search with mocked QdrantClient and EmbeddingProvider."""
        mock_qdrant = _make_mock_qdrant_client()
        mock_qdrant.search.return_value = [
            {
                "id": "file.ts:testFunc:function:10",
                "score": 0.9,
                "payload": {
                    "text": "function testFunc() {\n  return true;\n}",
                    "metadata": {
                        "file": "src/file.ts",
                        "line": 10,
                        "chunk_type": "function",
                        "name": "testFunc",
                        "exported": True,
                        "language": "typescript",
                    },
                },
            }
        ]

        mock_embedder = _make_mock_embedding_provider()

        response = search_code(
            "test function",
            qdrant_client=mock_qdrant,
            embedding_provider=mock_embedder,
        )

        # Verify embedding generation was called
        mock_embedder.generate_embedding.assert_called_once_with("test function")
        
        # Verify qdrant search was called
        mock_qdrant.search.assert_called_once()
        
        # Verify response structure
        assert response.query == "test function"
        assert response.total_found == 1
        assert len(response.results) == 1
        assert response.results[0].chunk.metadata.name == "testFunc"
        assert response.execution_time_ms > 0

    def test_search_with_filters(self) -> None:
        """Search respects filter parameters."""
        mock_qdrant = _make_mock_qdrant_client()
        mock_qdrant.search.return_value = []
        mock_embedder = _make_mock_embedding_provider()

        query = SearchQuery(
            text="test",
            top_k=5,
            filters={"chunk_type": "function", "exported_only": True},
        )

        response = search_code(
            query,
            qdrant_client=mock_qdrant,
            embedding_provider=mock_embedder,
        )

        # Verify filter was passed to Qdrant
        call_args = mock_qdrant.search.call_args
        assert call_args[1]["filter_dict"] is not None
        assert call_args[1]["top_k"] == 5

    def test_search_applies_min_score(self) -> None:
        """Results below min_score are filtered out."""
        mock_qdrant = _make_mock_qdrant_client()
        mock_qdrant.search.return_value = [
            {
                "id": "high.ts:highFunc:function:10",
                "score": 0.9,
                "payload": {
                    "text": "function highFunc() {}",
                    "metadata": {
                        "file": "high.ts",
                        "line": 10,
                        "chunk_type": "function",
                        "name": "highFunc",
                        "exported": False,
                        "language": "typescript",
                    },
                },
            },
            {
                "id": "low.ts:lowFunc:function:20",
                "score": 0.3,
                "payload": {
                    "text": "function lowFunc() {}",
                    "metadata": {
                        "file": "low.ts",
                        "line": 20,
                        "chunk_type": "function",
                        "name": "lowFunc",
                        "exported": False,
                        "language": "typescript",
                    },
                },
            },
        ]
        mock_embedder = _make_mock_embedding_provider()

        query = SearchQuery(text="test", min_score=0.5)
        response = search_code(
            query,
            qdrant_client=mock_qdrant,
            embedding_provider=mock_embedder,
        )

        # Only high score result should be returned
        assert response.total_found == 1
        assert response.results[0].chunk.metadata.name == "highFunc"

    def test_search_applies_file_pattern(self) -> None:
        """File pattern filter is applied post-search."""
        mock_qdrant = _make_mock_qdrant_client()
        mock_qdrant.search.return_value = [
            {
                "id": "src/auth/login.ts:login:function:10",
                "score": 0.9,
                "payload": {
                    "text": "function login() {}",
                    "metadata": {
                        "file": "src/auth/login.ts",
                        "line": 10,
                        "chunk_type": "function",
                        "name": "login",
                        "exported": True,
                        "language": "typescript",
                    },
                },
            },
            {
                "id": "tests/test.spec.ts:test:function:5",
                "score": 0.85,
                "payload": {
                    "text": "function test() {}",
                    "metadata": {
                        "file": "tests/test.spec.ts",
                        "line": 5,
                        "chunk_type": "function",
                        "name": "test",
                        "exported": False,
                        "language": "typescript",
                    },
                },
            },
        ]
        mock_embedder = _make_mock_embedding_provider()

        query = SearchQuery(text="function", filters={"file_pattern": "src/**/*.ts"})
        response = search_code(
            query,
            qdrant_client=mock_qdrant,
            embedding_provider=mock_embedder,
        )

        # Only src file should match pattern
        assert response.total_found == 1
        assert response.results[0].chunk.metadata.file == "src/auth/login.ts"

    def test_search_empty_results(self) -> None:
        """Search with no results returns empty list."""
        mock_qdrant = _make_mock_qdrant_client()
        mock_qdrant.search.return_value = []
        mock_embedder = _make_mock_embedding_provider()

        response = search_code(
            "nonexistent query",
            qdrant_client=mock_qdrant,
            embedding_provider=mock_embedder,
        )

        assert response.total_found == 0
        assert len(response.results) == 0

    def test_search_error_handling(self) -> None:
        """Search errors are caught and re-raised as VectorStoreQueryError."""
        mock_qdrant = _make_mock_qdrant_client()
        mock_qdrant.search.side_effect = Exception("Qdrant connection failed")
        mock_embedder = _make_mock_embedding_provider()

        with pytest.raises(VectorStoreQueryError, match="Search failed"):
            search_code(
                "test",
                qdrant_client=mock_qdrant,
                embedding_provider=mock_embedder,
            )


# ---------------------------------------------------------------------------
# build_context_from_results()
# ---------------------------------------------------------------------------


class TestBuildContextFromResults:
    def test_empty_results(self) -> None:
        """Empty results return helpful message."""
        response = SearchResponse(
            query="test",
            total_found=0,
            results=[],
            execution_time_ms=10.0,
        )

        context = build_context_from_results(response)
        assert context == "No relevant code chunks found."

    def test_single_result(self) -> None:
        """Single result is formatted correctly."""
        chunk = _make_test_chunk(name="testFunc", exported=True, feature="auth")
        result = SearchResult(
            score=0.9,
            chunk=chunk,
            explanation="High similarity",
            adjusted_score=0.95,
        )
        response = SearchResponse(
            query="test function",
            total_found=1,
            results=[result],
            execution_time_ms=15.0,
        )

        context = build_context_from_results(response)
        
        assert "Relevant code for query: 'test function'" in context
        assert "1. testFunc" in context
        assert "src/file.ts:10" in context
        assert "exported" in context
        assert "feature: auth" in context
        assert "function testFunc()" in context

    def test_multiple_results(self) -> None:
        """Multiple results are numbered correctly."""
        chunks = [
            _make_test_chunk(name=f"func{i}", chunk_id=f"file{i}.ts:func{i}:function:{i}")
            for i in range(3)
        ]
        results = [
            SearchResult(score=0.9 - i*0.1, chunk=chunk, explanation="", adjusted_score=0.9 - i*0.1)
            for i, chunk in enumerate(chunks)
        ]
        response = SearchResponse(
            query="test",
            total_found=3,
            results=results,
            execution_time_ms=20.0,
        )

        context = build_context_from_results(response)
        
        assert "1. func0" in context
        assert "2. func1" in context
        assert "3. func2" in context

    def test_respects_max_context_chars(self) -> None:
        """Context is truncated when exceeding max_context_chars."""
        large_text = "function large() {\n" + "  // comment\n" * 100 + "}"
        chunks = [
            _make_test_chunk(name=f"func{i}", text=large_text)
            for i in range(10)
        ]
        results = [
            SearchResult(score=0.9, chunk=chunk, explanation="", adjusted_score=0.9)
            for chunk in chunks
        ]
        response = SearchResponse(
            query="test",
            total_found=10,
            results=results,
            execution_time_ms=25.0,
        )

        context = build_context_from_results(response, max_context_chars=1000)
        
        assert len(context) <= 1500  # Allow some overhead
        assert "truncated" in context.lower()

    def test_include_score_option(self) -> None:
        """Score inclusion can be toggled."""
        chunk = _make_test_chunk()
        result = SearchResult(score=0.92, chunk=chunk, explanation="", adjusted_score=0.97)
        response = SearchResponse(
            query="test",
            total_found=1,
            results=[result],
            execution_time_ms=10.0,
        )

        context_with_score = build_context_from_results(response, include_score=True)
        context_without_score = build_context_from_results(response, include_score=False)

        assert "[score: 0.97]" in context_with_score
        assert "[score:" not in context_without_score


# ---------------------------------------------------------------------------
# SearchResult.get_preview()
# ---------------------------------------------------------------------------


class TestSearchResultGetPreview:
    def test_preview_basic(self) -> None:
        """Preview extracts first N lines."""
        chunk = _make_test_chunk(text="line1\nline2\nline3\nline4\nline5")
        result = SearchResult(score=0.9, chunk=chunk, explanation="", adjusted_score=0.9)

        preview = result.get_preview(max_lines=3)
        lines = preview.split("\n")
        assert len(lines) == 3
        assert lines[0] == "line1"
        assert lines[2] == "line3"

    def test_preview_truncate_long_lines(self) -> None:
        """Long lines are truncated."""
        long_line = "x" * 200
        chunk = _make_test_chunk(text=f"{long_line}\nshort")
        result = SearchResult(score=0.9, chunk=chunk, explanation="", adjusted_score=0.9)

        preview = result.get_preview(max_chars_per_line=100)
        lines = preview.split("\n")
        assert len(lines[0]) == 103  # 100 chars + "..."
        assert lines[0].endswith("...")

    def test_preview_skips_empty_lines(self) -> None:
        """Empty lines are filtered out."""
        chunk = _make_test_chunk(text="line1\n\n\nline2\n\nline3")
        result = SearchResult(score=0.9, chunk=chunk, explanation="", adjusted_score=0.9)

        preview = result.get_preview(max_lines=3)
        lines = preview.split("\n")
        assert len(lines) == 3
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert lines[2] == "line3"

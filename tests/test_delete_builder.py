from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aica.memory.graph_store.delete_builder import (
    DeleteSummary,
    delete_file_subgraph,
    delete_graph_for_files,
    delete_orphaned_modules,
)


class MockNeo4jClient:
    """Mock Neo4jClient for testing."""

    def __init__(self):
        self.queries: list[tuple[str, dict]] = []
        self._response = [{"deleted_count": 0}]

    def run_query(self, cypher: str, params: dict) -> list[dict]:
        """Mock run_query method."""
        self.queries.append((cypher, params))
        return self._response

    def set_response(self, response: list[dict]) -> None:
        """Set the response for the next query."""
        self._response = response


class TestDeleteFileSubgraph:
    """Tests for delete_file_subgraph function."""

    def test_delete_single_file(self) -> None:
        """Test deleting a single file."""
        client = MockNeo4jClient()
        client.set_response([{"deleted_count": 5}])

        count = delete_file_subgraph(client, ["src/auth.ts"])

        assert count == 5
        assert len(client.queries) == 1
        cypher, params = client.queries[0]
        assert "DELETE" in cypher
        assert params["file_paths"] == ["src/auth.ts"]

    def test_delete_multiple_files(self) -> None:
        """Test deleting multiple files."""
        client = MockNeo4jClient()
        client.set_response([{"deleted_count": 15}])

        count = delete_file_subgraph(client, ["src/auth.ts", "src/utils.ts"])

        assert count == 15
        assert len(client.queries) == 1
        cypher, params = client.queries[0]
        assert params["file_paths"] == ["src/auth.ts", "src/utils.ts"]

    def test_delete_empty_file_list(self) -> None:
        """Test with empty file list."""
        client = MockNeo4jClient()

        count = delete_file_subgraph(client, [])

        assert count == 0
        assert len(client.queries) == 0

    def test_delete_nonexistent_file(self) -> None:
        """Test deleting non-existent file (no nodes deleted)."""
        client = MockNeo4jClient()
        client.set_response([{"deleted_count": 0}])

        count = delete_file_subgraph(client, ["src/nonexistent.ts"])

        assert count == 0
        assert len(client.queries) == 1

    def test_delete_with_detach(self) -> None:
        """Verify DETACH DELETE is used (cascades to child nodes)."""
        client = MockNeo4jClient()
        client.set_response([{"deleted_count": 10}])

        delete_file_subgraph(client, ["src/auth.ts"])

        cypher, _ = client.queries[0]
        assert "DETACH DELETE" in cypher


class TestDeleteOrphanedModules:
    """Tests for delete_orphaned_modules function."""

    def test_delete_orphaned_modules(self) -> None:
        """Test deleting modules with no incoming IMPORTS edges."""
        client = MockNeo4jClient()
        client.set_response([{"deleted_count": 3}])

        count = delete_orphaned_modules(client)

        assert count == 3
        assert len(client.queries) == 1
        cypher, _ = client.queries[0]
        assert "NOT (m)<-[:IMPORTS]" in cypher

    def test_delete_no_orphaned_modules(self) -> None:
        """Test when no modules are orphaned."""
        client = MockNeo4jClient()
        client.set_response([{"deleted_count": 0}])

        count = delete_orphaned_modules(client)

        assert count == 0

    def test_preserves_imported_modules(self) -> None:
        """Verify query preserves modules with incoming IMPORTS edges."""
        client = MockNeo4jClient()
        client.set_response([{"deleted_count": 0}])

        delete_orphaned_modules(client)

        cypher, _ = client.queries[0]
        # The query should exclude modules that have incoming edges
        assert "NOT (m)<-[:IMPORTS]" in cypher


class TestDeleteGraphForFiles:
    """Tests for delete_graph_for_files orchestrator."""

    def test_delete_graph_aggregates_counts(self) -> None:
        """Test that summary aggregates file and module deletions."""
        client = MockNeo4jClient()

        # First call (delete_file_subgraph)
        client.set_response([{"deleted_count": 5}])
        summary = delete_graph_for_files(client, ["src/auth.ts"])
        # Second call (delete_orphaned_modules)
        client.set_response([{"deleted_count": 2}])
        summary = delete_graph_for_files(client, ["src/auth.ts"])

        assert isinstance(summary, DeleteSummary)
        assert summary.files_affected == ["src/auth.ts"]

    def test_delete_graph_empty_list(self) -> None:
        """Test with empty file list."""
        client = MockNeo4jClient()

        summary = delete_graph_for_files(client, [])

        assert summary.nodes_deleted == 0
        assert summary.orphaned_modules_deleted == 0
        assert summary.files_affected == []

    def test_delete_graph_summary_structure(self) -> None:
        """Verify DeleteSummary has required fields."""
        client = MockNeo4jClient()
        client.set_response([{"deleted_count": 5}])

        summary = delete_graph_for_files(client, ["src/auth.ts"])

        assert hasattr(summary, "nodes_deleted")
        assert hasattr(summary, "orphaned_modules_deleted")
        assert hasattr(summary, "relationships_deleted")
        assert hasattr(summary, "files_affected")


class TestDeleteSummary:
    """Tests for DeleteSummary dataclass."""

    def test_delete_summary_creation(self) -> None:
        """Test creating DeleteSummary."""
        summary = DeleteSummary(
            nodes_deleted=5,
            orphaned_modules_deleted=2,
            relationships_deleted=0,
            files_affected=["src/auth.ts"],
        )

        assert summary.nodes_deleted == 5
        assert summary.orphaned_modules_deleted == 2
        assert summary.files_affected == ["src/auth.ts"]

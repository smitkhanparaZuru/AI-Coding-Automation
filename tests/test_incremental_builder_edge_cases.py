from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aica.memory.graph_store.incremental_builder import (
    _filter_data_by_files,
    _load_all_ast_data,
    _rebuild_edges_for_files,
    _rebuild_nodes_for_files,
    update_graph_for_files,
)


class TestEdgeCasesEmptyData:
    """Tests for edge cases with empty or missing data."""

    def test_filter_with_none_file_key(self) -> None:
        """Test filtering handles missing file keys gracefully."""
        data = [
            {"name": "funcA"},  # Missing 'file' key
            {"file": "src/b.ts", "name": "funcB"},
        ]

        filtered = _filter_data_by_files(data, ["src/a.ts"])

        # Should filter out items without the file key
        assert len(filtered) == 0

    def test_load_with_corrupted_json(self) -> None:
        """Test loading handles corrupted JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create corrupted JSON file
            (ast_dir / "functions.json").write_text("{invalid json")
            (ast_dir / "components.json").write_text(json.dumps([]))
            (ast_dir / "types.json").write_text(json.dumps([]))
            (ast_dir / "hooks.json").write_text(json.dumps([]))
            (ast_dir / "imports.json").write_text(json.dumps([]))
            (ast_dir / "call_graph.json").write_text(json.dumps([]))

            # Should not crash, just return empty list for corrupted file
            data = _load_all_ast_data(ast_dir)

            assert data["functions"] == []  # Corrupted file returns []

    def test_rebuild_nodes_with_empty_data(self) -> None:
        """Test node building with empty AST data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create empty AST files
            for filename in [
                "functions.json",
                "components.json",
                "types.json",
                "hooks.json",
                "imports.json",
                "call_graph.json",
            ]:
                (ast_dir / filename).write_text(json.dumps([]))

            mock_client = MagicMock()

            with patch(
                "aica.memory.graph_store.incremental_builder.build_file_nodes"
            ) as mock_file:
                mock_file.return_value = 0

                counts = _rebuild_nodes_for_files(mock_client, ["src/a.ts"], ast_dir)

                # Should not crash, just return zeros
                assert counts["files"] == 0

    def test_rebuild_edges_with_empty_data(self) -> None:
        """Test edge building with empty AST data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create empty AST files
            for filename in [
                "functions.json",
                "components.json",
                "types.json",
                "hooks.json",
                "imports.json",
                "call_graph.json",
            ]:
                (ast_dir / filename).write_text(json.dumps([]))

            mock_client = MagicMock()
            repo_root = Path(tmpdir)

            with patch(
                "aica.memory.graph_store.incremental_builder.insert_import_edges"
            ) as mock_import:
                mock_import.return_value = 0

                counts = _rebuild_edges_for_files(
                    mock_client, ["src/a.ts"], ast_dir, repo_root
                )

                # Should not crash
                assert counts["imports"] == 0


class TestEdgeCasesLargeData:
    """Tests for edge cases with large amounts of data."""

    def test_filter_with_large_dataset(self) -> None:
        """Test filtering performance with large dataset."""
        # Create dataset with 1000 items
        data = [
            {"file": f"src/file_{i % 10}.ts", "name": f"func_{i}"}
            for i in range(1000)
        ]

        filtered = _filter_data_by_files(data, ["src/file_0.ts"])

        # Should get ~100 items (1000 / 10)
        assert len(filtered) == 100
        assert all(item["file"] == "src/file_0.ts" for item in filtered)

    def test_rebuild_nodes_with_large_dataset(self) -> None:
        """Test node building with large function count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create large dataset
            large_functions = [
                {"file": "src/a.ts", "name": f"func_{i}", "line": i}
                for i in range(500)
            ]

            (ast_dir / "functions.json").write_text(json.dumps(large_functions))
            (ast_dir / "components.json").write_text(json.dumps([]))
            (ast_dir / "types.json").write_text(json.dumps([]))
            (ast_dir / "hooks.json").write_text(json.dumps([]))
            (ast_dir / "imports.json").write_text(json.dumps([]))
            (ast_dir / "call_graph.json").write_text(json.dumps([]))

            mock_client = MagicMock()

            with patch(
                "aica.memory.graph_store.incremental_builder.build_function_nodes"
            ) as mock_func:
                mock_func.return_value = 500

                counts = _rebuild_nodes_for_files(mock_client, ["src/a.ts"], ast_dir)

                assert counts["functions"] == 500


class TestEdgeCasesCircularDependencies:
    """Tests for handling circular dependencies."""

    def test_filter_circular_imports(self) -> None:
        """Test filtering with circular import relationships.

        A imports B, B imports A. When A changes, B should be affected.
        When B changes, A should be affected.
        """
        changed = ["src/a.ts"]
        imports = [
            {"file": "src/a.ts", "from": "src/b.ts"},
            {"file": "src/b.ts", "from": "src/a.ts"},
        ]

        from aica.memory.graph_store.cross_file_detector import find_files_importing

        importers = find_files_importing(changed, imports)

        assert importers == {"src/b.ts"}

    def test_filter_circular_calls(self) -> None:
        """Test filtering with circular function calls (recursion).

        Function A calls B, B calls A (direct recursion).
        """
        changed = ["src/a.ts"]
        functions = [
            {"file": "src/a.ts", "name": "funcA", "line": 10},
            {"file": "src/b.ts", "name": "funcB", "line": 20},
        ]
        calls = [
            {"file": "src/a.ts", "caller": "funcA", "callee": "funcB"},
            {"file": "src/b.ts", "caller": "funcB", "callee": "funcA"},
        ]

        from aica.memory.graph_store.cross_file_detector import find_files_calling

        callers = find_files_calling(changed, functions, calls)

        assert callers == {"src/b.ts"}


class TestEdgeCasesUnresolvedReferences:
    """Tests for handling unresolved references."""

    def test_unresolved_imports(self) -> None:
        """Test filtering with unresolved imports (no 'from' field)."""
        changed = ["src/a.ts"]
        imports = [
            {"file": "src/a.ts"},  # No 'from' field
            {"file": "src/b.ts", "from": "src/a.ts"},
        ]

        from aica.memory.graph_store.cross_file_detector import find_files_importing

        importers = find_files_importing(changed, imports)

        assert importers == {"src/b.ts"}

    def test_unresolved_function_calls(self) -> None:
        """Test filtering with calls to undefined functions."""
        changed = ["src/a.ts"]
        functions = [
            {"file": "src/a.ts", "name": "funcA", "line": 10},
        ]
        calls = [
            {"file": "src/b.ts", "caller": "funcB", "callee": "funcA"},
            {"file": "src/c.ts", "caller": "funcC", "callee": "unknownFunc"},
        ]

        from aica.memory.graph_store.cross_file_detector import find_files_calling

        callers = find_files_calling(changed, functions, calls)

        assert callers == {"src/b.ts"}
        # funcC calling unknownFunc is skipped (doesn't match changed files)

    def test_missing_file_key_in_calls(self) -> None:
        """Test filtering calls with missing 'file' key."""
        changed = ["src/a.ts"]
        functions = [
            {"file": "src/a.ts", "name": "funcA", "line": 10},
        ]
        calls = [
            {"caller": "funcB", "callee": "funcA"},  # Missing 'file' key
        ]

        from aica.memory.graph_store.cross_file_detector import find_files_calling

        # Should not crash
        callers = find_files_calling(changed, functions, calls)

        assert callers == set()


class TestEdgeCasesDelete:
    """Tests for edge cases in deletion operations."""

    def test_delete_nonexistent_files(self) -> None:
        """Test deleting files that don't exist in Neo4j."""
        from unittest.mock import MagicMock

        from aica.memory.graph_store.delete_builder import delete_file_subgraph

        client = MagicMock()
        client.run_query.return_value = [{"deleted_count": 0}]

        # Should not crash
        count = delete_file_subgraph(client, ["src/nonexistent.ts"])

        assert count == 0
        # Query should still be called
        assert client.run_query.called

    def test_delete_with_empty_file_list(self) -> None:
        """Test delete with empty file list."""
        from aica.memory.graph_store.delete_builder import delete_file_subgraph

        client = MagicMock()

        count = delete_file_subgraph(client, [])

        assert count == 0
        assert not client.run_query.called


class TestErrorHandlingNeoQueryFailed:
    """Tests for error handling when Neo4j queries fail."""

    def test_rebuild_nodes_neo4j_error(self) -> None:
        """Test node building handles Neo4j errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create minimal AST files
            (ast_dir / "functions.json").write_text(
                json.dumps([{"file": "src/a.ts", "name": "login"}])
            )
            (ast_dir / "components.json").write_text(json.dumps([]))
            (ast_dir / "types.json").write_text(json.dumps([]))
            (ast_dir / "hooks.json").write_text(json.dumps([]))
            (ast_dir / "imports.json").write_text(json.dumps([]))
            (ast_dir / "call_graph.json").write_text(json.dumps([]))

            mock_client = MagicMock()

            with patch(
                "aica.memory.graph_store.incremental_builder.build_function_nodes"
            ) as mock_func:
                mock_func.side_effect = Exception("Neo4j connection failed")

                with pytest.raises(Exception):
                    _rebuild_nodes_for_files(
                        mock_client, ["src/a.ts"], ast_dir
                    )

    def test_rebuild_edges_neo4j_error(self) -> None:
        """Test edge building handles Neo4j errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create minimal AST files
            for filename in [
                "functions.json",
                "components.json",
                "types.json",
                "hooks.json",
                "imports.json",
                "call_graph.json",
            ]:
                (ast_dir / filename).write_text(json.dumps([]))

            mock_client = MagicMock()
            repo_root = Path(tmpdir)

            with patch(
                "aica.memory.graph_store.incremental_builder.insert_import_edges"
            ) as mock_import:
                mock_import.side_effect = Exception("Neo4j connection failed")

                with pytest.raises(Exception):
                    _rebuild_edges_for_files(
                        mock_client, ["src/a.ts"], ast_dir, repo_root
                    )


class TestErrorHandlingMissingAstDirectory:
    """Tests for error handling with missing AST directories."""

    @patch("aica.memory.graph_store.incremental_builder.Neo4jClient")
    def test_update_graph_missing_ast_dir(self, mock_neo4j_class) -> None:
        """Test update_graph fails with missing AST directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # AST directory not created

            with pytest.raises(FileNotFoundError):
                update_graph_for_files(repo_path, ["src/a.ts"], [])


class TestEdgeCasesFilePathHandling:
    """Tests for proper file path handling."""

    def test_filter_with_normalized_paths(self) -> None:
        """Test that different path representations are handled correctly."""
        data = [
            {"file": "src/a.ts", "name": "funcA"},
            {"file": "src/b.ts", "name": "funcB"},
        ]

        # Using forward slashes
        filtered = _filter_data_by_files(data, ["src/a.ts"])
        assert len(filtered) == 1

    def test_filter_with_relative_paths(self) -> None:
        """Test filtering with relative paths."""
        data = [
            {"file": "./src/a.ts", "name": "funcA"},
            {"file": "src/b.ts", "name": "funcB"},
        ]

        # Should match exact paths (no normalization)
        filtered = _filter_data_by_files(data, ["./src/a.ts"])
        assert len(filtered) == 1

        # Different representation won't match
        filtered = _filter_data_by_files(data, ["src/a.ts"])
        assert len(filtered) == 0


class TestEdgeCasesSpecialCharacters:
    """Tests for handling special characters in file names."""

    def test_filter_with_special_chars_in_filename(self) -> None:
        """Test filtering with special characters in file names."""
        data = [
            {"file": "src/[test]/a.ts", "name": "funcA"},
            {"file": "src/file with spaces.ts", "name": "funcB"},
            {"file": "src/file@special.ts", "name": "funcC"},
        ]

        filtered = _filter_data_by_files(data, ["src/[test]/a.ts"])
        assert len(filtered) == 1
        assert filtered[0]["file"] == "src/[test]/a.ts"

    def test_filter_with_unicode_filenames(self) -> None:
        """Test filtering with Unicode file names."""
        data = [
            {"file": "src/文件.ts", "name": "funcA"},
            {"file": "src/файл.ts", "name": "funcB"},
        ]

        filtered = _filter_data_by_files(data, ["src/文件.ts"])
        assert len(filtered) == 1

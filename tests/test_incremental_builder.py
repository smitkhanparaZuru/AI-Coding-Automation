from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aica.memory.graph_store.incremental_builder import (
    GraphUpdateSummary,
    _filter_data_by_files,
    _flatten_calls,
    _load_all_ast_data,
    _rebuild_edges_for_files,
    _rebuild_nodes_for_files,
    update_graph_for_files,
)


class TestFilterDataByFiles:
    """Tests for _filter_data_by_files function."""

    def test_filter_single_file(self) -> None:
        """Test filtering to a single file."""
        data = [
            {"file": "src/a.ts", "name": "funcA"},
            {"file": "src/b.ts", "name": "funcB"},
            {"file": "src/a.ts", "name": "funcC"},
        ]

        filtered = _filter_data_by_files(data, ["src/a.ts"])

        assert len(filtered) == 2
        assert all(item["file"] == "src/a.ts" for item in filtered)

    def test_filter_multiple_files(self) -> None:
        """Test filtering to multiple files."""
        data = [
            {"file": "src/a.ts", "name": "funcA"},
            {"file": "src/b.ts", "name": "funcB"},
            {"file": "src/c.ts", "name": "funcC"},
        ]

        filtered = _filter_data_by_files(data, ["src/a.ts", "src/c.ts"])

        assert len(filtered) == 2
        assert {item["file"] for item in filtered} == {"src/a.ts", "src/c.ts"}

    def test_filter_no_matches(self) -> None:
        """Test filtering with no matching files."""
        data = [
            {"file": "src/a.ts", "name": "funcA"},
            {"file": "src/b.ts", "name": "funcB"},
        ]

        filtered = _filter_data_by_files(data, ["src/nonexistent.ts"])

        assert len(filtered) == 0

    def test_filter_custom_file_key(self) -> None:
        """Test filtering with custom file key."""
        data = [
            {"caller_file": "src/a.ts", "name": "funcA"},
            {"caller_file": "src/b.ts", "name": "funcB"},
        ]

        filtered = _filter_data_by_files(data, ["src/a.ts"], file_key="caller_file")

        assert len(filtered) == 1
        assert filtered[0]["caller_file"] == "src/a.ts"

    def test_filter_empty_data(self) -> None:
        """Test filtering empty data."""
        filtered = _filter_data_by_files([], ["src/a.ts"])

        assert len(filtered) == 0

    def test_filter_empty_file_list(self) -> None:
        """Test filtering with empty file list."""
        data = [
            {"file": "src/a.ts", "name": "funcA"},
            {"file": "src/b.ts", "name": "funcB"},
        ]

        filtered = _filter_data_by_files(data, [])

        assert len(filtered) == 0


class TestFlattenCalls:
    """Tests for _flatten_calls function."""

    def test_flatten_nested_structure(self) -> None:
        """Test flattening nested call_graph structure."""
        nested = [
            {
                "file": "src/a.ts",
                "functions": [
                    {
                        "name": "login",
                        "calls": [
                            {"callee": "validateEmail", "kind": "function"},
                            {"callee": "hashPassword", "kind": "function"},
                        ],
                    },
                ],
            },
        ]

        flat = _flatten_calls(nested)

        assert len(flat) == 2
        assert all(item["file"] == "src/a.ts" for item in flat)
        assert all(item["caller"] == "login" for item in flat)
        callees = {item["callee"] for item in flat}
        assert callees == {"validateEmail", "hashPassword"}

    def test_flatten_already_flat(self) -> None:
        """Test with already-flat call structure."""
        already_flat = [
            {"file": "src/a.ts", "caller": "login", "callee": "validateEmail"},
            {"file": "src/a.ts", "caller": "logout", "callee": "clearSession"},
        ]

        flat = _flatten_calls(already_flat)

        assert flat == already_flat

    def test_flatten_empty_calls(self) -> None:
        """Test flattening empty calls list."""
        flat = _flatten_calls([])

        assert flat == []

    def test_flatten_multiple_files_and_functions(self) -> None:
        """Test flattening complex structure with multiple files and functions."""
        nested = [
            {
                "file": "src/a.ts",
                "functions": [
                    {
                        "name": "login",
                        "calls": [
                            {"callee": "validate", "kind": "function"},
                        ],
                    },
                    {
                        "name": "logout",
                        "calls": [
                            {"callee": "clear", "kind": "function"},
                        ],
                    },
                ],
            },
            {
                "file": "src/b.ts",
                "functions": [
                    {
                        "name": "render",
                        "calls": [
                            {"callee": "login", "kind": "function"},
                        ],
                    },
                ],
            },
        ]

        flat = _flatten_calls(nested)

        assert len(flat) == 3
        files = {item["file"] for item in flat}
        assert files == {"src/a.ts", "src/b.ts"}


class TestLoadAllAstData:
    """Tests for _load_all_ast_data function."""

    def test_load_with_all_files_present(self) -> None:
        """Test loading when all AST files are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create mock AST files
            (ast_dir / "functions.json").write_text(
                json.dumps([{"file": "src/a.ts", "name": "login"}])
            )
            (ast_dir / "components.json").write_text(
                json.dumps([{"file": "src/a.tsx", "name": "LoginButton"}])
            )
            (ast_dir / "types.json").write_text(json.dumps([]))
            (ast_dir / "hooks.json").write_text(json.dumps([]))
            (ast_dir / "imports.json").write_text(json.dumps([]))
            (ast_dir / "call_graph.json").write_text(json.dumps([]))

            data = _load_all_ast_data(ast_dir)

            assert len(data["functions"]) == 1
            assert len(data["components"]) == 1
            assert len(data["types"]) == 0

    def test_load_with_missing_files(self) -> None:
        """Test loading when some AST files are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create only some files
            (ast_dir / "functions.json").write_text(
                json.dumps([{"file": "src/a.ts", "name": "login"}])
            )
            # components.json missing
            # types.json missing

            data = _load_all_ast_data(ast_dir)

            assert len(data["functions"]) == 1
            assert data["components"] == []
            assert data["types"] == []

    def test_load_returns_dict_with_all_keys(self) -> None:
        """Test that returned dict has all expected keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create minimal files
            for filename in [
                "functions.json",
                "components.json",
                "types.json",
                "hooks.json",
                "imports.json",
                "call_graph.json",
            ]:
                (ast_dir / filename).write_text(json.dumps([]))

            data = _load_all_ast_data(ast_dir)

            assert "functions" in data
            assert "components" in data
            assert "types" in data
            assert "hooks" in data
            assert "imports" in data
            assert "calls" in data

    def test_load_with_singleton_dict(self) -> None:
        """Test that singleton dicts are wrapped in list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # functions.json as single dict (legacy format?)
            (ast_dir / "functions.json").write_text(
                json.dumps({"file": "src/a.ts", "name": "login"})
            )
            (ast_dir / "components.json").write_text(json.dumps([]))
            (ast_dir / "types.json").write_text(json.dumps([]))
            (ast_dir / "hooks.json").write_text(json.dumps([]))
            (ast_dir / "imports.json").write_text(json.dumps([]))
            (ast_dir / "call_graph.json").write_text(json.dumps([]))

            data = _load_all_ast_data(ast_dir)

            assert isinstance(data["functions"], list)
            assert len(data["functions"]) == 1


class TestGraphUpdateSummary:
    """Tests for GraphUpdateSummary dataclass."""

    def test_create_summary(self) -> None:
        """Test creating GraphUpdateSummary."""
        summary = GraphUpdateSummary(
            nodes_deleted=5,
            nodes_created=10,
            edges_created=15,
            files_affected=["src/a.ts", "src/b.ts"],
            duration_seconds=2.5,
        )

        assert summary.nodes_deleted == 5
        assert summary.nodes_created == 10
        assert summary.edges_created == 15
        assert len(summary.files_affected) == 2

    def test_summary_string_representation(self) -> None:
        """Test string representation of summary."""
        summary = GraphUpdateSummary(
            nodes_deleted=5,
            nodes_created=10,
            edges_created=15,
            files_affected=["src/a.ts"],
            duration_seconds=2.5,
        )

        summary_str = str(summary)

        assert "deleted 5 nodes" in summary_str
        assert "created 10 nodes" in summary_str
        assert "15 edges" in summary_str


class TestRebuildNodesForFiles:
    """Tests for _rebuild_nodes_for_files function."""

    @patch("aica.memory.graph_store.incremental_builder.build_file_nodes")
    @patch("aica.memory.graph_store.incremental_builder.build_function_nodes")
    @patch("aica.memory.graph_store.incremental_builder.build_component_nodes")
    @patch("aica.memory.graph_store.incremental_builder.build_type_nodes")
    @patch("aica.memory.graph_store.incremental_builder.build_hook_nodes")
    def test_rebuild_nodes_calls_builders(
        self,
        mock_hook_builder,
        mock_type_builder,
        mock_component_builder,
        mock_function_builder,
        mock_file_builder,
    ) -> None:
        """Test that rebuild calls all node builders."""
        # Setup mocks
        mock_file_builder.return_value = 2
        mock_function_builder.return_value = 3
        mock_component_builder.return_value = 1
        mock_type_builder.return_value = 0
        mock_hook_builder.return_value = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            ast_dir = Path(tmpdir)

            # Create minimal AST files
            (ast_dir / "functions.json").write_text(
                json.dumps([{"file": "src/a.ts", "name": "login"}])
            )
            (ast_dir / "components.json").write_text(
                json.dumps([{"file": "src/a.tsx", "name": "Button"}])
            )
            (ast_dir / "types.json").write_text(json.dumps([]))
            (ast_dir / "hooks.json").write_text(json.dumps([]))
            (ast_dir / "imports.json").write_text(json.dumps([]))
            (ast_dir / "call_graph.json").write_text(json.dumps([]))

            mock_client = MagicMock()

            counts = _rebuild_nodes_for_files(mock_client, ["src/a.ts"], ast_dir)

            # Verify all builders were called
            mock_file_builder.assert_called_once()
            mock_function_builder.assert_called_once()
            mock_component_builder.assert_called_once()

            # Verify counts
            assert counts["files"] == 2
            assert counts["functions"] == 3


class TestRebuildEdgesForFiles:
    """Tests for _rebuild_edges_for_files function."""

    @patch(
        "aica.memory.graph_store.incremental_builder.insert_import_edges"
    )
    @patch("aica.memory.graph_store.incremental_builder.insert_call_edges")
    @patch(
        "aica.memory.graph_store.incremental_builder.insert_hook_usage_edges"
    )
    def test_rebuild_edges_calls_builders(
        self, mock_hook_edges, mock_call_edges, mock_import_edges
    ) -> None:
        """Test that rebuild calls all edge builders."""
        # Setup mocks
        mock_import_edges.return_value = 5
        mock_call_edges.return_value = 3
        mock_hook_edges.return_value = 0

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

            counts = _rebuild_edges_for_files(
                mock_client, ["src/a.ts"], ast_dir, repo_root
            )

            # Verify builders were called
            mock_import_edges.assert_called_once()
            mock_call_edges.assert_called_once()

            # Verify counts
            assert counts["imports"] == 5
            assert counts["calls"] == 3


class TestUpdateGraphForFiles:
    """Tests for update_graph_for_files orchestrator."""

    @patch("aica.memory.graph_store.incremental_builder.Neo4jClient")
    @patch("aica.memory.graph_store.incremental_builder.delete_graph_for_files")
    @patch("aica.memory.graph_store.incremental_builder._rebuild_nodes_for_files")
    @patch("aica.memory.graph_store.incremental_builder._rebuild_edges_for_files")
    @patch(
        "aica.memory.graph_store.incremental_builder.detect_all_affected_files"
    )
    def test_update_graph_with_changes(
        self,
        mock_detect,
        mock_rebuild_edges,
        mock_rebuild_nodes,
        mock_delete,
        mock_neo4j_class,
    ) -> None:
        """Test full update_graph_for_files flow."""
        # Setup mocks
        mock_client = MagicMock()
        mock_neo4j_class.return_value = mock_client

        from aica.memory.graph_store.delete_builder import DeleteSummary

        mock_delete.return_value = DeleteSummary(
            nodes_deleted=5, orphaned_modules_deleted=2, relationships_deleted=0,
            files_affected=["src/a.ts"]
        )
        mock_rebuild_nodes.return_value = {"files": 1, "functions": 3}
        mock_rebuild_edges.return_value = {"imports": 2, "calls": 1}
        mock_detect.return_value = {"src/a.ts"}

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            ast_dir = repo_path / ".repo_intelligence" / "ast"
            ast_dir.mkdir(parents=True)

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

            summary = update_graph_for_files(
                repo_path, ["src/a.ts"], []
            )

            assert isinstance(summary, GraphUpdateSummary)
            assert summary.nodes_deleted == 5
            assert summary.files_affected == ["src/a.ts"]

    def test_update_graph_with_no_changes(self) -> None:
        """Test update when no files changed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            summary = update_graph_for_files(repo_path, [], [])

            assert summary.nodes_deleted == 0
            assert summary.nodes_created == 0
            assert summary.files_affected == []

    def test_update_graph_with_missing_ast_dir(self) -> None:
        """Test update fails gracefully with missing AST directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            with pytest.raises(FileNotFoundError):
                update_graph_for_files(repo_path, ["src/a.ts"], [])

    def test_update_graph_with_incomplete_ast_artifacts(self) -> None:
        """Test update fails when required AST files are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            ast_dir = repo_path / ".repo_intelligence" / "ast"
            ast_dir.mkdir(parents=True)

            # Missing required files on purpose.
            (ast_dir / "functions.json").write_text(json.dumps([]))

            with pytest.raises(FileNotFoundError, match="AST artifacts are incomplete"):
                update_graph_for_files(repo_path, ["src/a.ts"], [])

    def test_update_graph_with_stale_ast_artifacts(self, monkeypatch) -> None:
        """Test update fails when AST artifacts are too old."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            ast_dir = repo_path / ".repo_intelligence" / "ast"
            ast_dir.mkdir(parents=True)

            for filename in [
                "functions.json",
                "components.json",
                "types.json",
                "hooks.json",
                "imports.json",
                "call_graph.json",
            ]:
                (ast_dir / filename).write_text(json.dumps([]))

            old_timestamp = time.time() - 120
            for path in ast_dir.iterdir():
                path.touch()
                os.utime(path, (old_timestamp, old_timestamp))

            class _Settings:
                sync_max_ast_age_seconds = 1

            monkeypatch.setattr(
                "aica.memory.graph_store.incremental_builder.get_settings",
                lambda: _Settings(),
            )

            with pytest.raises(ValueError, match="AST artifacts appear stale"):
                update_graph_for_files(repo_path, ["src/a.ts"], [])

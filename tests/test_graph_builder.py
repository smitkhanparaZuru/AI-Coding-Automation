"""Tests for aica/memory/graph_store/graph_builder.py — Sub-Plan 4.7"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from aica.interfaces.cli import app
from aica.memory.graph_store.graph_builder import (
    GraphSummary,
    _flatten_call_graph,
    _load_json,
    build_dependency_graph,
)
from aica.memory.graph_store.neo4j_client import GraphConnectionError

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> MagicMock:
    """A mock Neo4jClient with all methods stubbed."""
    mock = MagicMock()
    mock.connect = MagicMock()
    mock.close = MagicMock()
    mock.run_query = MagicMock(return_value=[])
    return mock


@pytest.fixture()
def repo_with_ast(tmp_path: Path) -> Path:
    """Repository with .repo_intelligence/ structure and sample AST JSONs."""
    ast_dir = tmp_path / ".repo_intelligence" / "ast"
    ast_dir.mkdir(parents=True)
    
    # Write sample AST JSONs
    (ast_dir / "imports.json").write_text(json.dumps([
        {"file": "src/a.ts", "source": "react", "import_kind": "external", "line": 1}
    ]), encoding="utf-8")
    
    (ast_dir / "functions.json").write_text(json.dumps([
        {"file": "src/a.ts", "name": "foo", "kind": "function", "line": 10, "params": []}
    ]), encoding="utf-8")
    
    (ast_dir / "exports.json").write_text(json.dumps([]), encoding="utf-8")
    
    (ast_dir / "call_graph.json").write_text(json.dumps([
        {
            "file": "src/a.ts",
            "functions": [{"name": "foo", "calls": [{"callee": "bar", "line": 12}]}]
        }
    ]), encoding="utf-8")
    
    (ast_dir / "hooks.json").write_text(json.dumps([
        {"file": "src/App.tsx", "name": "useState", "caller": "App", "line": 5}
    ]), encoding="utf-8")
    
    (ast_dir / "components.json").write_text(json.dumps([
        {"file": "src/Button.tsx", "name": "Button", "kind": "arrow", "line": 3}
    ]), encoding="utf-8")
    
    (ast_dir / "types.json").write_text(json.dumps([
        {"file": "src/types.ts", "name": "Props", "kind": "interface", "line": 1}
    ]), encoding="utf-8")
    
    # Write sample scanner JSONs
    scanner_dir = tmp_path / ".repo_intelligence"
    (scanner_dir / "routes.json").write_text(json.dumps([
        {"route": "/home", "type": "page", "file": "src/app/home/page.tsx"}
    ]), encoding="utf-8")
    
    (scanner_dir / "services.json").write_text(json.dumps([
        {"name": "userService", "path": "src/services/user"}
    ]), encoding="utf-8")
    
    (scanner_dir / "stores.json").write_text(json.dumps([
        {"store": "auth", "path": "src/store/auth"}
    ]), encoding="utf-8")
    
    return tmp_path


# ---------------------------------------------------------------------------
# Entity factories
# ---------------------------------------------------------------------------


def _fn(name: str = "getData", file: str = "src/a.ts", line: int = 10) -> dict:
    return {"file": file, "name": name, "kind": "function", "line": line, "params": []}


def _comp(name: str = "Button", file: str = "src/Button.tsx", line: int = 5) -> dict:
    return {"file": file, "name": name, "kind": "arrow", "line": line, "props": []}


def _type(name: str = "Props", file: str = "src/types.ts", line: int = 1) -> dict:
    return {"file": file, "name": name, "kind": "interface", "line": line, "members": []}


def _hook(
    name: str = "useState",
    file: str = "src/App.tsx",
    caller: str = "App",
    line: int = 5,
) -> dict:
    return {"file": file, "name": name, "caller": caller, "line": line, "args_count": 1}


def _imp(source: str = "react", file: str = "src/a.ts", import_kind: str = "external") -> dict:
    return {"file": file, "source": source, "import_kind": import_kind, "line": 1}


def _call(callee: str = "bar", caller: str = "foo", file: str = "src/a.ts", line: int = 12) -> dict:
    return {"file": file, "caller": caller, "callee": callee, "line": line}


def _route(route: str = "/home", file: str = "src/app/home/page.tsx") -> dict:
    return {"route": route, "type": "page", "file": file}


def _service(name: str = "userService", path: str = "src/services/user") -> dict:
    return {"name": name, "path": path}


def _store(store: str = "auth", path: str = "src/store/auth") -> dict:
    return {"store": store, "path": path}


# ---------------------------------------------------------------------------
# _load_json
# ---------------------------------------------------------------------------


class TestLoadJson:
    def test_returns_none_on_missing_file(self, tmp_path: Path) -> None:
        result = _load_json(tmp_path / "missing.json")
        assert result is None

    def test_loads_valid_json_list(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        path.write_text('[{"a": 1}]', encoding="utf-8")
        result = _load_json(path)
        assert result == [{"a": 1}]

    def test_loads_valid_json_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        path.write_text('{"key": "value"}', encoding="utf-8")
        result = _load_json(path)
        # Dicts are wrapped in a list for consistent handling
        assert result == [{"key": "value"}]

    def test_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text('not valid json', encoding="utf-8")
        result = _load_json(path)
        assert result is None


# ---------------------------------------------------------------------------
# _flatten_call_graph
# ---------------------------------------------------------------------------


class TestFlattenCallGraph:
    def test_returns_empty_on_none(self) -> None:
        result = _flatten_call_graph(None)
        assert result == []

    def test_returns_empty_on_empty_list(self) -> None:
        result = _flatten_call_graph([])
        assert result == []

    def test_flattens_single_file_single_function(self) -> None:
        nested = [
            {
                "file": "src/a.ts",
                "functions": [
                    {
                        "name": "foo",
                        "calls": [
                            {"callee": "bar", "line": 10, "kind": "call"}
                        ]
                    }
                ]
            }
        ]
        result = _flatten_call_graph(nested)
        assert len(result) == 1
        assert result[0]["file"] == "src/a.ts"
        assert result[0]["caller"] == "foo"
        assert result[0]["callee"] == "bar"
        assert result[0]["line"] == 10

    def test_flattens_multiple_calls(self) -> None:
        nested = [
            {
                "file": "src/a.ts",
                "functions": [
                    {
                        "name": "foo",
                        "calls": [
                            {"callee": "bar", "line": 10},
                            {"callee": "baz", "line": 11}
                        ]
                    }
                ]
            }
        ]
        result = _flatten_call_graph(nested)
        assert len(result) == 2
        assert result[0]["callee"] == "bar"
        assert result[1]["callee"] == "baz"

    def test_handles_multiple_files_and_functions(self) -> None:
        nested = [
            {
                "file": "src/a.ts",
                "functions": [
                    {"name": "foo", "calls": [{"callee": "bar", "line": 10}]},
                    {"name": "qux", "calls": [{"callee": "quux", "line": 20}]}
                ]
            },
            {
                "file": "src/b.ts",
                "functions": [
                    {"name": "alpha", "calls": [{"callee": "beta", "line": 5}]}
                ]
            }
        ]
        result = _flatten_call_graph(nested)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# build_dependency_graph
# ---------------------------------------------------------------------------


class TestBuildDependencyGraph:
    @patch("aica.memory.graph_store.graph_builder.Neo4jClient")
    @patch("aica.memory.graph_store.graph_builder.setup_schema")
    @patch("aica.memory.graph_store.graph_builder.build_file_nodes", return_value=2)
    @patch("aica.memory.graph_store.graph_builder.build_function_nodes", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.build_component_nodes", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.build_type_nodes", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.build_hook_nodes", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.insert_import_edges", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.insert_call_edges", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.insert_hook_usage_edges", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.build_route_nodes", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.build_service_nodes", return_value=1)
    @patch("aica.memory.graph_store.graph_builder.build_store_nodes", return_value=1)
    def test_returns_graph_summary(
        self,
        mock_store_nodes,
        mock_service_nodes,
        mock_route_nodes,
        mock_hook_edges,
        mock_call_edges,
        mock_import_edges,
        mock_hook_nodes,
        mock_type_nodes,
        mock_component_nodes,
        mock_function_nodes,
        mock_file_nodes,
        mock_setup_schema,
        mock_neo4j_client,
        repo_with_ast: Path,
    ) -> None:
        # Mock client instance
        mock_client_instance = MagicMock()
        mock_neo4j_client.return_value = mock_client_instance
        
        result = build_dependency_graph(repo_with_ast)
        
        assert isinstance(result, GraphSummary)
        assert result.files == 2
        assert result.functions == 1
        assert result.components == 1
        assert result.types == 1
        assert result.hooks == 1
        assert result.routes == 1
        assert result.services == 1
        assert result.stores == 1
        assert result.import_edges == 1
        assert result.call_edges == 1
        assert result.hook_edges == 1

    @patch("aica.memory.graph_store.graph_builder.Neo4jClient")
    def test_calls_client_connect_and_close(
        self,
        mock_neo4j_client,
        repo_with_ast: Path,
    ) -> None:
        mock_client_instance = MagicMock()
        mock_neo4j_client.return_value = mock_client_instance
        
        # Mock all builder functions to avoid actually calling them
        with patch("aica.memory.graph_store.graph_builder.setup_schema"), \
             patch("aica.memory.graph_store.graph_builder.build_file_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_function_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_component_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_type_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_hook_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.insert_import_edges", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.insert_call_edges", return_value=0), \
             patch(
                 "aica.memory.graph_store.graph_builder.insert_hook_usage_edges",
                 return_value=0,
             ), \
             patch("aica.memory.graph_store.graph_builder.build_route_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_service_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_store_nodes", return_value=0):
            
            build_dependency_graph(repo_with_ast)
            
            mock_client_instance.connect.assert_called_once()
            mock_client_instance.close.assert_called_once()

    @patch("aica.memory.graph_store.graph_builder.Neo4jClient")
    def test_closes_client_on_error(
        self,
        mock_neo4j_client,
        repo_with_ast: Path,
    ) -> None:
        mock_client_instance = MagicMock()
        mock_neo4j_client.return_value = mock_client_instance
        
        # Mock setup_schema to raise error
        with patch(
            "aica.memory.graph_store.graph_builder.setup_schema",
            side_effect=Exception("Schema error"),
        ):
            with pytest.raises(Exception, match="Schema error"):
                build_dependency_graph(repo_with_ast)
            
            # Verify close was still called
            mock_client_instance.close.assert_called_once()

    @patch("aica.memory.graph_store.graph_builder.Neo4jClient")
    def test_handles_missing_ast_files_gracefully(
        self,
        mock_neo4j_client,
        tmp_path: Path,
    ) -> None:
        # Create repo dir but no JSON files
        (tmp_path / ".repo_intelligence" / "ast").mkdir(parents=True)
        (tmp_path / ".repo_intelligence").mkdir(exist_ok=True)
        
        mock_client_instance = MagicMock()
        mock_neo4j_client.return_value = mock_client_instance
        
        with patch("aica.memory.graph_store.graph_builder.setup_schema"), \
             patch("aica.memory.graph_store.graph_builder.build_file_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_function_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_component_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_type_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_hook_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.insert_import_edges", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.insert_call_edges", return_value=0), \
             patch(
                 "aica.memory.graph_store.graph_builder.insert_hook_usage_edges",
                 return_value=0,
             ), \
             patch("aica.memory.graph_store.graph_builder.build_route_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_service_nodes", return_value=0), \
             patch("aica.memory.graph_store.graph_builder.build_store_nodes", return_value=0):
            
            result = build_dependency_graph(tmp_path)
            
            # Should complete with zero counts
            assert result.files == 0
            assert result.functions == 0


# ---------------------------------------------------------------------------
# CLI: build-graph
# ---------------------------------------------------------------------------


class TestCLIBuildGraph:
    def test_build_graph_exits_zero_on_success(self, repo_with_ast: Path) -> None:
        with patch("aica.interfaces.cli.build_dependency_graph") as mock_build:
            mock_build.return_value = GraphSummary(
                files=2, functions=1, components=1, types=1, hooks=1,
                routes=1, services=1, stores=1,
                import_edges=1, call_edges=1, hook_edges=1
            )
            result = runner.invoke(app, ["build-graph", "--path", str(repo_with_ast)])
            assert result.exit_code == 0

    def test_build_graph_shows_summary_table(self, repo_with_ast: Path) -> None:
        with patch("aica.interfaces.cli.build_dependency_graph") as mock_build:
            mock_build.return_value = GraphSummary(
                files=5, functions=10, components=3, types=2, hooks=4,
                routes=2, services=1, stores=1,
                import_edges=15, call_edges=20, hook_edges=8
            )
            result = runner.invoke(app, ["build-graph", "--path", str(repo_with_ast)])
            
            assert "Files" in result.output
            assert "Functions" in result.output
            assert "Components" in result.output
            assert "Total Nodes" in result.output
            assert "Total Edges" in result.output

    def test_build_graph_displays_correct_counts(self, repo_with_ast: Path) -> None:
        with patch("aica.interfaces.cli.build_dependency_graph") as mock_build:
            mock_build.return_value = GraphSummary(
                files=5, functions=10, components=3, types=2, hooks=4,
                routes=2, services=1, stores=1,
                import_edges=15, call_edges=20, hook_edges=8
            )
            result = runner.invoke(app, ["build-graph", "--path", str(repo_with_ast)])
            
            # Check individual counts appear in output
            assert "5" in result.output  # files
            assert "10" in result.output  # functions
            assert "3" in result.output  # components

    def test_build_graph_error_on_missing_repo_intelligence(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["build-graph", "--path", str(tmp_path)])
        assert result.exit_code == 1
        assert "No .repo_intelligence/ directory found" in result.output

    def test_build_graph_error_on_graph_connection_failure(self, repo_with_ast: Path) -> None:
        with patch(
            "aica.interfaces.cli.build_dependency_graph",
            side_effect=GraphConnectionError("Connection failed"),
        ):
            result = runner.invoke(app, ["build-graph", "--path", str(repo_with_ast)])
            assert result.exit_code == 1
            assert "Error building graph" in result.output

    def test_build_graph_uses_workspace_dir_when_no_path_given(self, repo_with_ast: Path) -> None:
        with patch("aica.interfaces.cli.build_dependency_graph") as mock_build, \
             patch("aica.interfaces.cli.get_settings") as mock_settings:
            
            mock_build.return_value = GraphSummary(
                files=1, functions=1, components=1, types=1, hooks=1,
                routes=1, services=1, stores=1,
                import_edges=1, call_edges=1, hook_edges=1
            )
            mock_settings.return_value.workspace_dir = repo_with_ast
            
            result = runner.invoke(app, ["build-graph"])
            assert result.exit_code == 0
            mock_build.assert_called_once()

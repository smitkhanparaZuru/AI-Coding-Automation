"""Tests for aica/memory/graph_store/node_builder.py — Sub-Plan 4.3"""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from aica.memory.graph_store.node_builder import (
    BATCH_SIZE,
    build_component_nodes,
    build_file_nodes,
    build_function_nodes,
    build_hook_nodes,
    build_type_nodes,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> MagicMock:
    """A mock Neo4jClient with run_query stubbed out."""
    mock = MagicMock()
    mock.run_query = MagicMock(return_value=[])
    return mock


# ---------------------------------------------------------------------------
# Sample entity factories
# ---------------------------------------------------------------------------


def _fn(name: str | None = "getData", file: str = "src/handler.ts", line: int = 10) -> dict:
    return {
        "file": file,
        "name": name,
        "kind": "function",
        "async": False,
        "params": ["req", "res"],
        "line": line,
        "exported": True,
    }


def _comp(name: str = "Button", file: str = "src/Button.tsx", line: int = 5) -> dict:
    return {
        "file": file,
        "name": name,
        "kind": "arrow",
        "props": ["label", "onClick"],
        "exported": True,
        "line": line,
    }


def _typ(name: str = "UserProps", file: str = "src/types.ts", line: int = 8) -> dict:
    return {
        "file": file,
        "name": name,
        "kind": "interface",
        "exported": True,
        "members": ["id", "name"],
        "line": line,
    }


def _hook(name: str = "useState", file: str = "src/App.tsx", caller: str = "App", line: int = 20) -> dict:
    return {
        "file": file,
        "name": name,
        "caller": caller,
        "args_count": 1,
        "line": line,
    }


# ---------------------------------------------------------------------------
# build_file_nodes
# ---------------------------------------------------------------------------


class TestBuildFileNodes:
    def test_returns_unique_file_count(self, client: MagicMock) -> None:
        fns = [_fn(file="src/a.ts"), _fn(file="src/b.ts")]
        comps = [_comp(file="src/a.ts")]  # duplicate of first function's file
        result = build_file_nodes(client, fns, comps, [], [])
        assert result == 2

    def test_dedupes_across_all_lists(self, client: MagicMock) -> None:
        # same file appears in all four lists
        same_file = "src/shared.ts"
        result = build_file_nodes(
            client,
            [_fn(file=same_file)],
            [_comp(file=same_file)],
            [_typ(file=same_file)],
            [_hook(file=same_file)],
        )
        assert result == 1

    def test_empty_inputs_returns_zero(self, client: MagicMock) -> None:
        result = build_file_nodes(client, [], [], [], [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_cypher_contains_merge_and_file_label(self, client: MagicMock) -> None:
        build_file_nodes(client, [_fn()], [], [], [])
        cypher = client.run_query.call_args[0][0]
        assert "MERGE" in cypher
        assert "File" in cypher

    def test_batching_at_boundary(self, client: MagicMock) -> None:
        # 501 unique files → 2 run_query calls
        fns = [_fn(file=f"src/file_{i}.ts") for i in range(BATCH_SIZE + 1)]
        build_file_nodes(client, fns, [], [], [])
        assert client.run_query.call_count == 2

    def test_paths_passed_as_batch_param(self, client: MagicMock) -> None:
        build_file_nodes(client, [_fn(file="src/x.ts")], [], [], [])
        params = client.run_query.call_args[0][1]
        assert "batch" in params
        assert params["batch"] == [{"path": "src/x.ts"}]


# ---------------------------------------------------------------------------
# build_function_nodes
# ---------------------------------------------------------------------------


class TestBuildFunctionNodes:
    def test_filters_anonymous_functions(self, client: MagicMock) -> None:
        fns = [_fn(name=None), _fn(name=None), _fn(name="realFn")]
        result = build_function_nodes(client, fns)
        assert result == 1

    def test_returns_zero_for_all_anonymous(self, client: MagicMock) -> None:
        build_function_nodes(client, [_fn(name=None)])
        assert client.run_query.call_count == 0

    def test_empty_returns_zero(self, client: MagicMock) -> None:
        result = build_function_nodes(client, [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_id_format(self, client: MagicMock) -> None:
        fn = _fn(name="myFn", file="src/utils.ts", line=42)
        build_function_nodes(client, [fn])
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["id"] == "src/utils.ts::myFn::42"

    def test_async_key_mapped_to_is_async(self, client: MagicMock) -> None:
        fn = {**_fn(), "async": True}
        build_function_nodes(client, [fn])
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["props"]["is_async"] is True
        assert "async" not in batch[0]["props"]

    def test_defines_edge_in_cypher(self, client: MagicMock) -> None:
        build_function_nodes(client, [_fn()])
        cypher = client.run_query.call_args[0][0]
        assert "DEFINES" in cypher

    def test_file_passed_in_row(self, client: MagicMock) -> None:
        build_function_nodes(client, [_fn(file="src/api.ts")])
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["file"] == "src/api.ts"

    def test_batching_at_boundary(self, client: MagicMock) -> None:
        fns = [_fn(name=f"fn_{i}", line=i) for i in range(BATCH_SIZE + 1)]
        build_function_nodes(client, fns)
        assert client.run_query.call_count == 2

    def test_returns_named_count(self, client: MagicMock) -> None:
        fns = [_fn(name=f"fn_{i}", line=i) for i in range(3)] + [_fn(name=None)]
        result = build_function_nodes(client, fns)
        assert result == 3


# ---------------------------------------------------------------------------
# build_component_nodes
# ---------------------------------------------------------------------------


class TestBuildComponentNodes:
    def test_id_excludes_line(self, client: MagicMock) -> None:
        comp = _comp(name="Card", file="src/Card.tsx", line=99)
        build_component_nodes(client, [comp])
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["id"] == "src/Card.tsx::Card"

    def test_props_list_preserved(self, client: MagicMock) -> None:
        comp = _comp()
        build_component_nodes(client, [comp])
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["props"]["props"] == ["label", "onClick"]

    def test_defines_edge_in_cypher(self, client: MagicMock) -> None:
        build_component_nodes(client, [_comp()])
        cypher = client.run_query.call_args[0][0]
        assert "DEFINES" in cypher

    def test_returns_count(self, client: MagicMock) -> None:
        comps = [_comp(name=f"Comp{i}") for i in range(3)]
        result = build_component_nodes(client, comps)
        assert result == 3

    def test_empty_returns_zero(self, client: MagicMock) -> None:
        result = build_component_nodes(client, [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_component_label_in_cypher(self, client: MagicMock) -> None:
        build_component_nodes(client, [_comp()])
        cypher = client.run_query.call_args[0][0]
        assert "Component" in cypher

    def test_batching_at_boundary(self, client: MagicMock) -> None:
        comps = [_comp(name=f"Comp{i}") for i in range(BATCH_SIZE + 1)]
        build_component_nodes(client, comps)
        assert client.run_query.call_count == 2


# ---------------------------------------------------------------------------
# build_type_nodes
# ---------------------------------------------------------------------------


class TestBuildTypeNodes:
    def test_row_uses_composite_key_not_id(self, client: MagicMock) -> None:
        typ = _typ(name="MyInterface", file="src/types.ts", line=10)
        build_type_nodes(client, [typ])
        batch = client.run_query.call_args[0][1]["batch"]
        row = batch[0]
        assert row["file"] == "src/types.ts"
        assert row["name"] == "MyInterface"
        assert row["line"] == 10
        assert "id" not in row

    def test_set_props_excludes_merge_keys(self, client: MagicMock) -> None:
        build_type_nodes(client, [_typ()])
        batch = client.run_query.call_args[0][1]["batch"]
        props = batch[0]["props"]
        assert set(props.keys()) == {"kind", "exported", "members"}

    def test_defines_edge_in_cypher(self, client: MagicMock) -> None:
        build_type_nodes(client, [_typ()])
        cypher = client.run_query.call_args[0][0]
        assert "DEFINES" in cypher

    def test_type_label_in_cypher(self, client: MagicMock) -> None:
        build_type_nodes(client, [_typ()])
        cypher = client.run_query.call_args[0][0]
        assert "Type" in cypher

    def test_returns_count(self, client: MagicMock) -> None:
        types = [_typ(name=f"Type{i}") for i in range(4)]
        result = build_type_nodes(client, types)
        assert result == 4

    def test_empty_returns_zero(self, client: MagicMock) -> None:
        result = build_type_nodes(client, [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_members_preserved(self, client: MagicMock) -> None:
        typ = _typ()
        build_type_nodes(client, [typ])
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["props"]["members"] == ["id", "name"]

    def test_batching_at_boundary(self, client: MagicMock) -> None:
        types = [_typ(name=f"T{i}", line=i) for i in range(BATCH_SIZE + 1)]
        build_type_nodes(client, types)
        assert client.run_query.call_count == 2


# ---------------------------------------------------------------------------
# build_hook_nodes
# ---------------------------------------------------------------------------


class TestBuildHookNodes:
    def test_dedupes_hook_names(self, client: MagicMock) -> None:
        # same hook name from 3 different files
        hooks = [
            _hook(name="useState", file="src/A.tsx"),
            _hook(name="useState", file="src/B.tsx"),
            _hook(name="useState", file="src/C.tsx"),
        ]
        result = build_hook_nodes(client, hooks)
        assert result == 1
        # Only 1 run_query call for the MERGE Hook nodes
        assert client.run_query.call_count == 1
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch == [{"name": "useState"}]

    def test_returns_unique_count(self, client: MagicMock) -> None:
        hooks = [
            _hook(name="useState"),
            _hook(name="useEffect"),
            _hook(name="useState"),  # dup
        ]
        result = build_hook_nodes(client, hooks)
        assert result == 2

    def test_empty_hooks_returns_zero(self, client: MagicMock) -> None:
        result = build_hook_nodes(client, [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_no_defines_edge_without_functions_param(self, client: MagicMock) -> None:
        build_hook_nodes(client, [_hook(name="useState")], functions=None)
        # Only the MERGE Hook query — no DEFINES query
        assert client.run_query.call_count == 1
        cypher = client.run_query.call_args[0][0]
        assert "DEFINES" not in cypher

    def test_defines_edge_sent_for_user_defined_hook(self, client: MagicMock) -> None:
        user_hook = "useAuth"
        hooks = [_hook(name=user_hook, file="src/App.tsx")]
        fns = [_fn(name=user_hook, file="src/hooks/useAuth.ts")]
        build_hook_nodes(client, hooks, functions=fns)
        # 2 calls: 1 MERGE Hook + 1 DEFINES
        assert client.run_query.call_count == 2
        defines_cypher = client.run_query.call_args_list[1][0][0]
        assert "DEFINES" in defines_cypher

    def test_external_hooks_get_no_defines_edge(self, client: MagicMock) -> None:
        # useState is not in the functions list (it's external)
        hooks = [_hook(name="useState")]
        fns = [_fn(name="someOtherFn")]  # does not match "useState"
        build_hook_nodes(client, hooks, functions=fns)
        # Only MERGE Hook, no DEFINES
        assert client.run_query.call_count == 1

    def test_hook_label_in_cypher(self, client: MagicMock) -> None:
        build_hook_nodes(client, [_hook()])
        cypher = client.run_query.call_args[0][0]
        assert "Hook" in cypher

    def test_batching_hook_nodes(self, client: MagicMock) -> None:
        # BATCH_SIZE + 1 unique hook names → 2 MERGE queries for hook nodes
        hooks = [_hook(name=f"useHook{i}") for i in range(BATCH_SIZE + 1)]
        build_hook_nodes(client, hooks)
        assert client.run_query.call_count == 2

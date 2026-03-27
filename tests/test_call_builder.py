"""Tests for aica/memory/graph_store/call_builder.py — Sub-Plan 4.5"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aica.memory.graph_store.call_builder import (
    BATCH_SIZE,
    _build_component_id_map,
    _build_function_id_map,
    _resolve_caller_id,
    _resolve_callee_id,
    insert_call_edges,
    insert_hook_usage_edges,
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


def _fn(
    name: str | None = "myFn",
    file: str = "src/app.ts",
    line: int = 10,
    **kwargs: object,
) -> dict:
    return {
        "file": file,
        "name": name,
        "kind": "function",
        "async": False,
        "params": [],
        "line": line,
        "exported": False,
        **kwargs,
    }


def _comp(
    name: str = "MyComp",
    file: str = "src/App.tsx",
    line: int = 5,
    **kwargs: object,
) -> dict:
    return {
        "file": file,
        "name": name,
        "kind": "arrow",
        "props": [],
        "exported": False,
        "line": line,
        **kwargs,
    }


def _call(
    callee: str = "helper",
    file: str = "src/app.ts",
    caller: str | None = "myFn",
    line: int = 20,
    **kwargs: object,
) -> dict:
    return {
        "file": file,
        "caller": caller,
        "callee": callee,
        "callee_object": None,
        "kind": "call",
        "line": line,
        **kwargs,
    }


def _hook(
    name: str = "useState",
    file: str = "src/app.ts",
    caller: str | None = "myFn",
    line: int = 20,
) -> dict:
    return {
        "file": file,
        "name": name,
        "caller": caller,
        "args_count": 1,
        "line": line,
    }


# ---------------------------------------------------------------------------
# TestBuildFunctionIdMap
# ---------------------------------------------------------------------------


class TestBuildFunctionIdMap:
    def test_named_function_mapped_by_file(self) -> None:
        fns = [_fn(name="foo", file="src/a.ts", line=5)]
        result = _build_function_id_map(fns)
        assert "src/a.ts" in result
        assert result["src/a.ts"][0]["name"] == "foo"
        assert result["src/a.ts"][0]["id"] == "src/a.ts::foo::5"

    def test_anonymous_functions_excluded(self) -> None:
        fns = [_fn(name=None), _fn(name="named", line=1)]
        result = _build_function_id_map(fns)
        entries = result.get("src/app.ts", [])
        assert all(e["name"] is not None for e in entries)
        assert len(entries) == 1

    def test_multiple_functions_in_same_file_sorted_by_line(self) -> None:
        fns = [
            _fn(name="beta", file="src/a.ts", line=30),
            _fn(name="alpha", file="src/a.ts", line=10),
            _fn(name="gamma", file="src/a.ts", line=20),
        ]
        result = _build_function_id_map(fns)
        lines = [e["line"] for e in result["src/a.ts"]]
        assert lines == sorted(lines)

    def test_multiple_files_grouped_independently(self) -> None:
        fns = [
            _fn(name="f1", file="src/a.ts", line=1),
            _fn(name="f2", file="src/b.ts", line=1),
        ]
        result = _build_function_id_map(fns)
        assert set(result.keys()) == {"src/a.ts", "src/b.ts"}

    def test_empty_input_returns_empty_dict(self) -> None:
        assert _build_function_id_map([]) == {}

    def test_all_anonymous_returns_empty_dict(self) -> None:
        fns = [_fn(name=None), _fn(name=None)]
        assert _build_function_id_map(fns) == {}

    def test_id_format_matches_node_builder_constraint(self) -> None:
        fn = _fn(name="doWork", file="src/worker.ts", line=42)
        result = _build_function_id_map([fn])
        assert result["src/worker.ts"][0]["id"] == "src/worker.ts::doWork::42"


# ---------------------------------------------------------------------------
# TestResolveCaller
# ---------------------------------------------------------------------------


class TestResolveCaller:
    def _map_with_two_foos(self) -> dict:
        return _build_function_id_map([
            _fn(name="foo", file="src/a.ts", line=10),
            _fn(name="foo", file="src/a.ts", line=50),
            _fn(name="bar", file="src/a.ts", line=70),
        ])

    def test_single_match_returns_correct_id(self) -> None:
        fn_map = _build_function_id_map([_fn(name="doIt", file="src/x.ts", line=5)])
        result = _resolve_caller_id("src/x.ts", "doIt", 10, fn_map)
        assert result == "src/x.ts::doIt::5"

    def test_picks_closest_line_when_same_name_multiple_definitions(self) -> None:
        # Two functions named "foo" at lines 10 and 50; call at line 60 → line 50
        fn_map = self._map_with_two_foos()
        result = _resolve_caller_id("src/a.ts", "foo", 60, fn_map)
        assert result == "src/a.ts::foo::50"

    def test_picks_earlier_definition_when_call_between_them(self) -> None:
        # Call at line 30; foo@10 ≤ 30, foo@50 > 30 → picks line 10
        fn_map = self._map_with_two_foos()
        result = _resolve_caller_id("src/a.ts", "foo", 30, fn_map)
        assert result == "src/a.ts::foo::10"

    def test_wrong_file_returns_none(self) -> None:
        fn_map = _build_function_id_map([_fn(name="foo", file="src/a.ts", line=5)])
        result = _resolve_caller_id("src/b.ts", "foo", 10, fn_map)
        assert result is None

    def test_unknown_name_in_correct_file_returns_none(self) -> None:
        fn_map = _build_function_id_map([_fn(name="foo", file="src/a.ts", line=5)])
        result = _resolve_caller_id("src/a.ts", "unknown", 10, fn_map)
        assert result is None

    def test_call_before_definition_returns_none(self) -> None:
        # foo defined at line 20; call at line 5 → fn_line > call_line → None
        fn_map = _build_function_id_map([_fn(name="foo", file="src/a.ts", line=20)])
        result = _resolve_caller_id("src/a.ts", "foo", 5, fn_map)
        assert result is None

    def test_exact_same_line_as_definition_returns_id(self) -> None:
        fn_map = _build_function_id_map([_fn(name="foo", file="src/a.ts", line=10)])
        result = _resolve_caller_id("src/a.ts", "foo", 10, fn_map)
        assert result == "src/a.ts::foo::10"


# ---------------------------------------------------------------------------
# TestResolveCallee
# ---------------------------------------------------------------------------


class TestResolveCallee:
    def test_same_file_match_preferred(self) -> None:
        fns = [
            _fn(name="helper", file="src/a.ts", line=5),
            _fn(name="helper", file="src/b.ts", line=5),
        ]
        fn_map = _build_function_id_map(fns)
        result = _resolve_callee_id("helper", "src/a.ts", fn_map)
        assert result == "src/a.ts::helper::5"

    def test_cross_file_fallback_when_not_in_same_file(self) -> None:
        fns = [_fn(name="helper", file="src/utils.ts", line=3)]
        fn_map = _build_function_id_map(fns)
        result = _resolve_callee_id("helper", "src/app.ts", fn_map)
        assert result == "src/utils.ts::helper::3"

    def test_multiple_cross_file_picks_first_alphabetically(self) -> None:
        fns = [
            _fn(name="shared", file="src/z.ts", line=1),
            _fn(name="shared", file="src/a.ts", line=1),
        ]
        fn_map = _build_function_id_map(fns)
        result = _resolve_callee_id("shared", "src/caller.ts", fn_map)
        # "src/a.ts" < "src/z.ts" alphabetically
        assert result == "src/a.ts::shared::1"

    def test_no_match_returns_none(self) -> None:
        fn_map = _build_function_id_map([_fn(name="foo", line=1)])
        result = _resolve_callee_id("nonexistent", "src/app.ts", fn_map)
        assert result is None

    def test_empty_map_returns_none(self) -> None:
        result = _resolve_callee_id("foo", "src/app.ts", {})
        assert result is None

    def test_same_file_match_does_not_require_line_constraint(self) -> None:
        # Callee can be defined after caller line — it's a definition, not a call
        fns = [_fn(name="helper", file="src/a.ts", line=100)]
        fn_map = _build_function_id_map(fns)
        result = _resolve_callee_id("helper", "src/a.ts", fn_map)
        assert result == "src/a.ts::helper::100"


# ---------------------------------------------------------------------------
# TestBuildComponentIdMap
# ---------------------------------------------------------------------------


class TestBuildComponentIdMap:
    def test_maps_file_name_to_id(self) -> None:
        comps = [_comp(name="Button", file="src/Button.tsx")]
        result = _build_component_id_map(comps)
        assert result[("src/Button.tsx", "Button")] == "src/Button.tsx::Button"

    def test_excludes_components_without_name(self) -> None:
        comps = [{"file": "src/x.tsx", "name": None, "kind": "arrow"}]
        result = _build_component_id_map(comps)
        assert result == {}

    def test_multiple_components_different_files(self) -> None:
        comps = [
            _comp(name="A", file="src/A.tsx"),
            _comp(name="B", file="src/B.tsx"),
        ]
        result = _build_component_id_map(comps)
        assert len(result) == 2
        assert result[("src/A.tsx", "A")] == "src/A.tsx::A"
        assert result[("src/B.tsx", "B")] == "src/B.tsx::B"

    def test_empty_input_returns_empty_dict(self) -> None:
        assert _build_component_id_map([]) == {}


# ---------------------------------------------------------------------------
# TestInsertCallEdges
# ---------------------------------------------------------------------------


class TestInsertCallEdges:
    def test_empty_calls_returns_zero(self, client: MagicMock) -> None:
        result = insert_call_edges(client, [], [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_module_level_caller_skipped(self, client: MagicMock) -> None:
        calls = [_call(caller=None)]
        fns = [_fn()]
        result = insert_call_edges(client, calls, fns)
        assert result == 0
        client.run_query.assert_not_called()

    def test_unresolvable_caller_skipped(self, client: MagicMock) -> None:
        # "ghost" is not in functions list
        calls = [_call(caller="ghost", callee="helper", file="src/a.ts", line=30)]
        fns = [_fn(name="helper", file="src/a.ts", line=5)]
        result = insert_call_edges(client, calls, fns)
        assert result == 0
        client.run_query.assert_not_called()

    def test_unresolvable_callee_skipped(self, client: MagicMock) -> None:
        calls = [_call(caller="myFn", callee="unknown", file="src/a.ts", line=20)]
        fns = [_fn(name="myFn", file="src/a.ts", line=5)]
        result = insert_call_edges(client, calls, fns)
        assert result == 0
        client.run_query.assert_not_called()

    def test_resolved_edge_emits_run_query(self, client: MagicMock) -> None:
        fns = [
            _fn(name="caller", file="src/a.ts", line=5),
            _fn(name="callee", file="src/a.ts", line=1),
        ]
        calls = [_call(caller="caller", callee="callee", file="src/a.ts", line=10)]
        result = insert_call_edges(client, calls, fns)
        assert result == 1
        client.run_query.assert_called_once()

    def test_cypher_contains_calls_match_merge_function(self, client: MagicMock) -> None:
        fns = [
            _fn(name="a", file="src/a.ts", line=1),
            _fn(name="b", file="src/a.ts", line=2),
        ]
        calls = [_call(caller="a", callee="b", file="src/a.ts", line=5)]
        insert_call_edges(client, calls, fns)
        cypher = client.run_query.call_args[0][0]
        assert "CALLS" in cypher
        assert "MATCH" in cypher
        assert "MERGE" in cypher
        assert "Function" in cypher

    def test_batch_row_contains_caller_and_callee_ids(self, client: MagicMock) -> None:
        fns = [
            _fn(name="a", file="src/x.ts", line=1),
            _fn(name="b", file="src/x.ts", line=2),
        ]
        calls = [_call(caller="a", callee="b", file="src/x.ts", line=5)]
        insert_call_edges(client, calls, fns)
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["caller_id"] == "src/x.ts::a::1"
        assert batch[0]["callee_id"] == "src/x.ts::b::2"

    def test_batching_splits_at_batch_size(self, client: MagicMock) -> None:
        # 601 named functions → 600 consecutive call pairs
        fns = [_fn(name=f"fn_{i}", file="src/a.ts", line=i + 1) for i in range(601)]
        calls = [
            _call(caller=f"fn_{i}", callee=f"fn_{i + 1}", file="src/a.ts", line=i + 2)
            for i in range(600)
        ]
        result = insert_call_edges(client, calls, fns)
        # 600 edges → 2 batches (500 + 100)
        assert client.run_query.call_count == 2
        assert result == 600

    def test_returns_total_edge_count(self, client: MagicMock) -> None:
        fns = [
            _fn(name="a", file="src/a.ts", line=1),
            _fn(name="b", file="src/a.ts", line=2),
            _fn(name="c", file="src/a.ts", line=3),
        ]
        calls = [
            _call(caller="a", callee="b", file="src/a.ts", line=10),
            _call(caller="a", callee="c", file="src/a.ts", line=11),
        ]
        result = insert_call_edges(client, calls, fns)
        assert result == 2

    def test_new_kind_calls_included(self, client: MagicMock) -> None:
        # kind="new" constructor calls should still create CALLS edges
        fns = [
            _fn(name="maker", file="src/a.ts", line=1),
            _fn(name="MyClass", file="src/a.ts", line=2),
        ]
        calls = [_call(caller="maker", callee="MyClass", file="src/a.ts", line=5, kind="new")]
        result = insert_call_edges(client, calls, fns)
        assert result == 1

    def test_empty_functions_makes_all_unresolvable(self, client: MagicMock) -> None:
        calls = [_call(caller="myFn", callee="helper")]
        result = insert_call_edges(client, calls, [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_cross_file_callee_resolved(self, client: MagicMock) -> None:
        fns = [
            _fn(name="caller", file="src/a.ts", line=1),
            _fn(name="callee", file="src/utils.ts", line=5),
        ]
        calls = [_call(caller="caller", callee="callee", file="src/a.ts", line=10)]
        result = insert_call_edges(client, calls, fns)
        assert result == 1
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["callee_id"] == "src/utils.ts::callee::5"


# ---------------------------------------------------------------------------
# TestInsertHookUsageEdges
# ---------------------------------------------------------------------------


class TestInsertHookUsageEdges:
    def test_empty_hooks_returns_zero(self, client: MagicMock) -> None:
        result = insert_hook_usage_edges(client, [], [], [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_module_level_caller_skipped(self, client: MagicMock) -> None:
        hooks = [_hook(caller=None)]
        result = insert_hook_usage_edges(client, hooks, [_fn()], [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_function_caller_emits_function_batch(self, client: MagicMock) -> None:
        fns = [_fn(name="myFn", file="src/a.ts", line=5)]
        hooks = [_hook(name="useState", file="src/a.ts", caller="myFn", line=10)]
        result = insert_hook_usage_edges(client, hooks, fns, [])
        assert result == 1
        client.run_query.assert_called_once()
        cypher = client.run_query.call_args[0][0]
        assert "Function" in cypher
        assert "USES_HOOK" in cypher

    def test_component_caller_emits_component_batch(self, client: MagicMock) -> None:
        comps = [_comp(name="MyComp", file="src/App.tsx", line=5)]
        hooks = [_hook(name="useEffect", file="src/App.tsx", caller="MyComp", line=10)]
        result = insert_hook_usage_edges(client, hooks, [], comps)
        assert result == 1
        client.run_query.assert_called_once()
        cypher = client.run_query.call_args[0][0]
        assert "Component" in cypher
        assert "USES_HOOK" in cypher

    def test_unresolvable_caller_warns_and_skips(self, client: MagicMock) -> None:
        hooks = [_hook(name="useMemo", file="src/a.ts", caller="ghost", line=5)]
        result = insert_hook_usage_edges(client, hooks, [], [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_both_batches_emitted_when_mixed_callers(self, client: MagicMock) -> None:
        fns = [_fn(name="myFn", file="src/a.ts", line=1)]
        comps = [_comp(name="MyComp", file="src/App.tsx", line=1)]
        hooks = [
            _hook(name="useState", file="src/a.ts", caller="myFn", line=5),
            _hook(name="useEffect", file="src/App.tsx", caller="MyComp", line=5),
        ]
        result = insert_hook_usage_edges(client, hooks, fns, comps)
        assert result == 2
        assert client.run_query.call_count == 2

    def test_only_function_batch_when_no_component_callers(self, client: MagicMock) -> None:
        fns = [_fn(name="myFn", file="src/a.ts", line=1)]
        hooks = [
            _hook(name="useState", file="src/a.ts", caller="myFn", line=5),
            _hook(name="useEffect", file="src/a.ts", caller="myFn", line=6),
        ]
        insert_hook_usage_edges(client, hooks, fns, [])
        assert client.run_query.call_count == 1
        cypher = client.run_query.call_args[0][0]
        assert "Function" in cypher

    def test_only_component_batch_when_no_function_callers(self, client: MagicMock) -> None:
        comps = [_comp(name="MyComp", file="src/App.tsx", line=1)]
        hooks = [_hook(name="useState", file="src/App.tsx", caller="MyComp", line=5)]
        insert_hook_usage_edges(client, hooks, [], comps)
        assert client.run_query.call_count == 1
        cypher = client.run_query.call_args[0][0]
        assert "Component" in cypher

    def test_function_batch_respects_batch_size(self, client: MagicMock) -> None:
        fns = [_fn(name="myFn", file="src/a.ts", line=1)]
        hooks = [
            _hook(name=f"useHook{i}", file="src/a.ts", caller="myFn", line=i + 5)
            for i in range(BATCH_SIZE + 1)
        ]
        result = insert_hook_usage_edges(client, hooks, fns, [])
        assert result == BATCH_SIZE + 1
        # 501 fn edges → 2 batches
        assert client.run_query.call_count == 2

    def test_returns_total_fn_plus_comp_count(self, client: MagicMock) -> None:
        fns = [_fn(name="myFn", file="src/a.ts", line=1)]
        comps = [_comp(name="MyComp", file="src/App.tsx", line=1)]
        hooks = [
            _hook(name="useState", file="src/a.ts", caller="myFn", line=5),
            _hook(name="useEffect", file="src/a.ts", caller="myFn", line=6),
            _hook(name="useCallback", file="src/App.tsx", caller="MyComp", line=5),
        ]
        result = insert_hook_usage_edges(client, hooks, fns, comps)
        assert result == 3

    def test_batch_row_contains_hook_name(self, client: MagicMock) -> None:
        fns = [_fn(name="myFn", file="src/a.ts", line=1)]
        hooks = [_hook(name="useMyHook", file="src/a.ts", caller="myFn", line=5)]
        insert_hook_usage_edges(client, hooks, fns, [])
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["hook_name"] == "useMyHook"

    def test_batch_row_contains_caller_id(self, client: MagicMock) -> None:
        fns = [_fn(name="myFn", file="src/a.ts", line=1)]
        hooks = [_hook(name="useState", file="src/a.ts", caller="myFn", line=5)]
        insert_hook_usage_edges(client, hooks, fns, [])
        batch = client.run_query.call_args[0][1]["batch"]
        assert batch[0]["caller_id"] == "src/a.ts::myFn::1"

    def test_function_caller_preferred_over_component(self, client: MagicMock) -> None:
        # Same name exists as both a Function and a Component in the same file
        fns = [_fn(name="Overlap", file="src/a.ts", line=1)]
        comps = [_comp(name="Overlap", file="src/a.ts", line=1)]
        hooks = [_hook(name="useState", file="src/a.ts", caller="Overlap", line=5)]
        insert_hook_usage_edges(client, hooks, fns, comps)
        cypher = client.run_query.call_args[0][0]
        # Function resolution takes priority; should go to Function batch
        assert "Function" in cypher

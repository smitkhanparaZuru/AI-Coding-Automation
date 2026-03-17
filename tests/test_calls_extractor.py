"""
Tests for aica.repo_intelligence.ast.extractors.calls

Covers:
    extract() — call_expression and new_expression nodes
    callee     — resolved name of the called function / method
    callee_object — receiver for method calls; None for plain calls
    kind        — "call" | "new"
    caller      — innermost enclosing named function; None at module level / anonymous
    line        — 1-based
    file field  — embedded in every output dict
    build_call_graph() — groups flat rows into per-file nested structure
"""

from __future__ import annotations

import pytest

from aica.repo_intelligence.ast.extractors.calls import build_call_graph, extract
from aica.repo_intelligence.ast.parser import parse_code

_FILE = "src/test.ts"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(code: str, lang: str = "typescript"):
    return parse_code(code, lang=lang)


def _extract(code: str, file_path: str = _FILE, lang: str = "typescript") -> list[dict]:
    tree = _parse(code, lang=lang)
    return extract(tree, code, file_path)


def _find(results: list[dict], **kwargs) -> dict | None:
    """Return first entry whose fields all match *kwargs*."""
    for entry in results:
        if all(entry.get(k) == v for k, v in kwargs.items()):
            return entry
    return None


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


class TestCallsExtractorBasic:
    def test_empty_file_returns_empty_list(self):
        assert _extract("") == []

    def test_returns_list(self):
        result = _extract("foo();")
        assert isinstance(result, list)

    def test_no_calls_returns_empty(self):
        result = _extract("const x = 1;\nconst y = 'hello';")
        assert result == []

    def test_pure_declaration_no_calls(self):
        result = _extract("function greet() { return 'hi'; }")
        assert result == []


# ---------------------------------------------------------------------------
# Plain calls
# ---------------------------------------------------------------------------


class TestPlainCalls:
    def test_plain_call_callee(self):
        result = _extract("foo();")
        assert result[0]["callee"] == "foo"

    def test_plain_call_no_object(self):
        result = _extract("foo();")
        assert result[0]["callee_object"] is None

    def test_plain_call_kind(self):
        result = _extract("foo();")
        assert result[0]["kind"] == "call"

    def test_module_level_caller_is_none(self):
        result = _extract("foo();")
        assert result[0]["caller"] is None

    def test_plain_call_line(self):
        result = _extract("foo();")
        assert result[0]["line"] == 1

    def test_call_on_second_line(self):
        result = _extract("\nbar();")
        entry = _find(result, callee="bar")
        assert entry is not None
        assert entry["line"] == 2

    def test_call_with_args(self):
        result = _extract("foo(1, 2, 3);")
        assert result[0]["callee"] == "foo"

    def test_multiple_plain_calls(self):
        result = _extract("foo();\nbar();\nbaz();")
        callees = [r["callee"] for r in result]
        assert "foo" in callees
        assert "bar" in callees
        assert "baz" in callees


# ---------------------------------------------------------------------------
# Method calls (member expressions)
# ---------------------------------------------------------------------------


class TestMemberCalls:
    def test_method_call_callee(self):
        result = _extract("obj.bar();")
        entry = _find(result, callee="bar")
        assert entry is not None

    def test_method_call_object(self):
        result = _extract("obj.bar();")
        entry = _find(result, callee="bar")
        assert entry["callee_object"] == "obj"

    def test_method_call_kind(self):
        result = _extract("obj.bar();")
        entry = _find(result, callee="bar")
        assert entry["kind"] == "call"

    def test_chained_member_call_callee(self):
        result = _extract("a.b.c();")
        entry = _find(result, callee="c")
        assert entry is not None

    def test_chained_member_call_object(self):
        # For a.b.c(), tree-sitter gives object as "a.b" (member_expression text)
        result = _extract("a.b.c();")
        entry = _find(result, callee="c")
        assert entry["callee_object"] == "a.b"

    def test_console_log(self):
        result = _extract("console.log('hello');")
        entry = _find(result, callee="log")
        assert entry is not None
        assert entry["callee_object"] == "console"

    def test_react_use_state(self):
        result = _extract("React.useState(0);")
        entry = _find(result, callee="useState")
        assert entry is not None
        assert entry["callee_object"] == "React"


# ---------------------------------------------------------------------------
# Caller context — function declarations
# ---------------------------------------------------------------------------


class TestFunctionDeclarationCaller:
    def test_call_inside_function_has_caller(self):
        code = "function outer() { inner(); }"
        result = _extract(code)
        entry = _find(result, callee="inner")
        assert entry is not None
        assert entry["caller"] == "outer"

    def test_async_function_caller(self):
        code = "async function fetchData() { doSomething(); }"
        result = _extract(code)
        entry = _find(result, callee="doSomething")
        assert entry["caller"] == "fetchData"

    def test_generator_function_caller(self):
        code = "function* gen() { yield produce(); }"
        result = _extract(code)
        entry = _find(result, callee="produce")
        assert entry is not None
        assert entry["caller"] == "gen"


# ---------------------------------------------------------------------------
# Caller context — arrow functions
# ---------------------------------------------------------------------------


class TestArrowFunctionCaller:
    def test_arrow_bound_to_const(self):
        code = "const handler = () => { foo(); };"
        result = _extract(code)
        entry = _find(result, callee="foo")
        assert entry is not None
        assert entry["caller"] == "handler"

    def test_arrow_bound_to_let(self):
        code = "let process = (x) => { bar(x); };"
        result = _extract(code)
        entry = _find(result, callee="bar")
        assert entry["caller"] == "process"

    def test_arrow_expression_body(self):
        code = "const double = (n) => transform(n);"
        result = _extract(code)
        entry = _find(result, callee="transform")
        assert entry is not None
        assert entry["caller"] == "double"

    def test_unbound_arrow_caller_is_none(self):
        # Arrow passed directly to another function — no variable binding
        code = "arr.forEach(() => { run(); });"
        result = _extract(code)
        entry = _find(result, callee="run")
        assert entry is not None
        assert entry["caller"] is None


# ---------------------------------------------------------------------------
# Caller context — class methods
# ---------------------------------------------------------------------------


class TestMethodCaller:
    def test_method_call_inside_class_method(self):
        code = "class Svc { handle() { process(); } }"
        result = _extract(code)
        entry = _find(result, callee="process")
        assert entry is not None
        assert entry["caller"] == "handle"

    def test_async_method_caller(self):
        code = "class Api { async fetch() { doRequest(); } }"
        result = _extract(code)
        entry = _find(result, callee="doRequest")
        assert entry["caller"] == "fetch"


# ---------------------------------------------------------------------------
# New expressions
# ---------------------------------------------------------------------------


class TestNewExpressions:
    def test_new_plain_identifier(self):
        result = _extract("new Foo();")
        entry = _find(result, callee="Foo")
        assert entry is not None

    def test_new_kind_field(self):
        result = _extract("new Foo();")
        entry = _find(result, callee="Foo")
        assert entry["kind"] == "new"

    def test_new_no_object(self):
        result = _extract("new Foo();")
        entry = _find(result, callee="Foo")
        assert entry["callee_object"] is None

    def test_new_member_expression(self):
        result = _extract("new ns.Bar();")
        entry = _find(result, callee="Bar")
        assert entry is not None
        assert entry["callee_object"] == "ns"

    def test_new_kind_on_member(self):
        result = _extract("new ns.Bar();")
        entry = _find(result, callee="Bar")
        assert entry["kind"] == "new"

    def test_new_module_level_caller_none(self):
        result = _extract("new Foo();")
        entry = _find(result, callee="Foo")
        assert entry["caller"] is None

    def test_new_inside_function(self):
        code = "function init() { return new Client(); }"
        result = _extract(code)
        entry = _find(result, callee="Client")
        assert entry is not None
        assert entry["caller"] == "init"
        assert entry["kind"] == "new"


# ---------------------------------------------------------------------------
# Nested calls (e.g. foo(bar()))
# ---------------------------------------------------------------------------


class TestNestedCalls:
    def test_outer_call_captured(self):
        result = _extract("foo(bar());")
        assert _find(result, callee="foo") is not None

    def test_inner_call_captured(self):
        result = _extract("foo(bar());")
        assert _find(result, callee="bar") is not None

    def test_nested_call_count(self):
        result = _extract("a(b(c()));")
        callees = {r["callee"] for r in result}
        assert {"a", "b", "c"} == callees

    def test_nested_method_call(self):
        result = _extract("arr.map(x => transform(x));")
        assert _find(result, callee="map") is not None
        assert _find(result, callee="transform") is not None


# ---------------------------------------------------------------------------
# Line numbers
# ---------------------------------------------------------------------------


class TestLineNumbers:
    def test_first_line(self):
        result = _extract("foo();")
        assert result[0]["line"] == 1

    def test_multiline_correct_lines(self):
        code = "foo();\nbar();\nbaz();"
        result = _extract(code)
        foo = _find(result, callee="foo")
        bar = _find(result, callee="bar")
        baz = _find(result, callee="baz")
        assert foo["line"] == 1
        assert bar["line"] == 2
        assert baz["line"] == 3


# ---------------------------------------------------------------------------
# File field
# ---------------------------------------------------------------------------


class TestFileField:
    def test_file_field_present(self):
        result = _extract("foo();", file_path="src/utils.ts")
        assert result[0]["file"] == "src/utils.ts"

    def test_file_field_matches_argument(self):
        result = _extract("foo();\nbar();", file_path="app/service.ts")
        for entry in result:
            assert entry["file"] == "app/service.ts"


# ---------------------------------------------------------------------------
# TSX support
# ---------------------------------------------------------------------------


class TestTSXSupport:
    def test_call_in_tsx_file(self):
        code = "const App = () => { const [s, setS] = useState(0); return null; };"
        result = _extract(code, lang="tsx")
        entry = _find(result, callee="useState")
        assert entry is not None

    def test_caller_resolved_in_tsx(self):
        code = "const App = () => { doSomething(); return null; };"
        result = _extract(code, lang="tsx")
        entry = _find(result, callee="doSomething")
        assert entry is not None
        assert entry["caller"] == "App"


# ---------------------------------------------------------------------------
# Multiple calls — deduplication by position
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_same_call_not_duplicated(self):
        result = _extract("foo();")
        foo_calls = [r for r in result if r["callee"] == "foo"]
        assert len(foo_calls) == 1

    def test_different_calls_all_present(self):
        result = _extract("foo(); foo(); foo();")
        foo_calls = [r for r in result if r["callee"] == "foo"]
        # Each invocation is at a different position → 3 entries
        assert len(foo_calls) == 3


# ---------------------------------------------------------------------------
# build_call_graph — basic shape
# ---------------------------------------------------------------------------


class TestBuildCallGraph:
    def _sample_calls(self) -> list[dict]:
        return [
            {"file": "src/a.ts", "caller": "outer", "callee": "inner", "callee_object": None, "kind": "call", "line": 3},
            {"file": "src/a.ts", "caller": None, "callee": "init", "callee_object": None, "kind": "call", "line": 1},
            {"file": "src/b.ts", "caller": "run", "callee": "helper", "callee_object": "utils", "kind": "call", "line": 7},
        ]

    def test_returns_list(self):
        result = build_call_graph(self._sample_calls())
        assert isinstance(result, list)

    def test_files_are_grouped(self):
        result = build_call_graph(self._sample_calls())
        files = {entry["file"] for entry in result}
        assert "src/a.ts" in files
        assert "src/b.ts" in files

    def test_each_entry_has_functions_key(self):
        result = build_call_graph(self._sample_calls())
        for entry in result:
            assert "functions" in entry
            assert isinstance(entry["functions"], list)

    def test_functions_have_name_and_calls(self):
        result = build_call_graph(self._sample_calls())
        a_entry = next(e for e in result if e["file"] == "src/a.ts")
        for fn in a_entry["functions"]:
            assert "name" in fn
            assert "calls" in fn

    def test_named_caller_grouped_correctly(self):
        result = build_call_graph(self._sample_calls())
        a_entry = next(e for e in result if e["file"] == "src/a.ts")
        outer_fn = next((f for f in a_entry["functions"] if f["name"] == "outer"), None)
        assert outer_fn is not None
        assert len(outer_fn["calls"]) == 1
        assert outer_fn["calls"][0]["callee"] == "inner"

    def test_null_caller_grouped_correctly(self):
        result = build_call_graph(self._sample_calls())
        a_entry = next(e for e in result if e["file"] == "src/a.ts")
        null_fn = next((f for f in a_entry["functions"] if f["name"] is None), None)
        assert null_fn is not None
        assert null_fn["calls"][0]["callee"] == "init"

    def test_null_caller_last_in_functions_list(self):
        result = build_call_graph(self._sample_calls())
        a_entry = next(e for e in result if e["file"] == "src/a.ts")
        # Named callers should come before None
        names = [f["name"] for f in a_entry["functions"]]
        none_idx = names.index(None)
        for i, name in enumerate(names):
            if name is None:
                continue
            assert i < none_idx

    def test_call_row_fields(self):
        result = build_call_graph(self._sample_calls())
        b_entry = next(e for e in result if e["file"] == "src/b.ts")
        run_fn = next(f for f in b_entry["functions"] if f["name"] == "run")
        call_row = run_fn["calls"][0]
        assert call_row["callee"] == "helper"
        assert call_row["callee_object"] == "utils"
        assert call_row["kind"] == "call"
        assert call_row["line"] == 7

    def test_files_sorted_alphabetically(self):
        calls = [
            {"file": "src/z.ts", "caller": None, "callee": "last", "callee_object": None, "kind": "call", "line": 1},
            {"file": "src/a.ts", "caller": None, "callee": "first", "callee_object": None, "kind": "call", "line": 1},
        ]
        result = build_call_graph(calls)
        assert result[0]["file"] == "src/a.ts"
        assert result[1]["file"] == "src/z.ts"

    def test_empty_calls_returns_empty_list(self):
        assert build_call_graph([]) == []

    def test_call_row_has_no_file_key(self):
        """The file key should NOT appear in nested call rows — it lives at the top level."""
        result = build_call_graph(self._sample_calls())
        for file_entry in result:
            for fn in file_entry["functions"]:
                for call_row in fn["calls"]:
                    assert "file" not in call_row

    def test_call_row_has_no_caller_key(self):
        """The caller key should NOT appear in nested call rows — it is the grouping key."""
        result = build_call_graph(self._sample_calls())
        for file_entry in result:
            for fn in file_entry["functions"]:
                for call_row in fn["calls"]:
                    assert "caller" not in call_row

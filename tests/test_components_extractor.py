"""
Tests for the components extractor (Task 3.5).
"""

from __future__ import annotations

import pytest

from aica.repo_intelligence.ast.extractors.components import extract
from aica.repo_intelligence.ast.parser import parse_code

_FILE = "src/test.tsx"


def _parse(code: str, lang: str = "tsx"):
    return parse_code(code, lang=lang)


def _extract(code: str, file_path: str = _FILE, lang: str = "tsx") -> list[dict]:
    tree = _parse(code, lang=lang)
    return extract(tree, code, file_path)


def _find(results: list[dict], **kwargs) -> dict | None:
    """Return first entry whose fields all match *kwargs*."""
    for entry in results:
        if all(entry.get(k) == v for k, v in kwargs.items()):
            return entry
    return None


# ---------------------------------------------------------------------------
# Basic
# ---------------------------------------------------------------------------


class TestComponentsExtractorBasic:
    def test_empty_file_returns_empty_list(self):
        assert _extract("") == []

    def test_return_type_is_list(self):
        assert isinstance(_extract("const x = 1;"), list)

    def test_plain_function_without_jsx_not_captured(self):
        assert _extract("function foo() { return 42; }") == []

    def test_lowercase_function_with_jsx_not_component(self):
        code = "function myFunc() { return <div />; }"
        assert _extract(code) == []


# ---------------------------------------------------------------------------
# Function components
# ---------------------------------------------------------------------------


class TestFunctionComponents:
    def test_simple_function_component(self):
        code = "function MyComp() { return <div />; }"
        results = _extract(code)
        assert len(results) == 1
        assert results[0]["name"] == "MyComp"
        assert results[0]["kind"] == "function"

    def test_function_component_with_jsx_element(self):
        code = """\
function Header() {
  return <header><h1>Title</h1></header>;
}
"""
        results = _extract(code)
        comp = _find(results, name="Header")
        assert comp is not None
        assert comp["kind"] == "function"

    def test_exported_function_component(self):
        code = "export function Button() { return <button />; }"
        results = _extract(code)
        assert results[0]["exported"] is True

    def test_non_exported_function_component(self):
        code = "function Internal() { return <span />; }"
        results = _extract(code)
        assert results[0]["exported"] is False

    def test_function_component_line(self):
        code = "\nfunction MyComp() { return <div />; }"
        results = _extract(code)
        assert results[0]["line"] == 2


# ---------------------------------------------------------------------------
# Arrow components
# ---------------------------------------------------------------------------


class TestArrowComponents:
    def test_simple_arrow_component(self):
        code = "const MyComp = () => <div />;"
        results = _extract(code)
        assert len(results) == 1
        assert results[0]["name"] == "MyComp"
        assert results[0]["kind"] == "arrow"

    def test_arrow_component_with_block_body(self):
        code = """\
const Card = () => {
  return <div className="card" />;
};
"""
        results = _extract(code)
        comp = _find(results, name="Card")
        assert comp is not None
        assert comp["kind"] == "arrow"

    def test_exported_arrow_component(self):
        code = "export const Icon = () => <svg />;"
        results = _extract(code)
        assert results[0]["exported"] is True

    def test_anonymous_arrow_not_captured(self):
        # Arrow with no PascalCase binding — not a component
        code = "const x = () => <div />;"
        # 'x' starts with lowercase
        assert _extract(code) == []

    def test_arrow_component_name_from_declarator(self):
        code = "const NavBar = () => <nav />;"
        results = _extract(code)
        assert results[0]["name"] == "NavBar"


# ---------------------------------------------------------------------------
# Class components
# ---------------------------------------------------------------------------


class TestClassComponents:
    def test_extends_component(self):
        code = """\
import { Component } from 'react';
class MyWidget extends Component {
  render() { return <div />; }
}
"""
        results = _extract(code)
        comp = _find(results, name="MyWidget")
        assert comp is not None
        assert comp["kind"] == "class"

    def test_extends_react_component(self):
        code = """\
class Counter extends React.Component {
  render() { return <span>{this.state.count}</span>; }
}
"""
        results = _extract(code)
        comp = _find(results, name="Counter")
        assert comp is not None
        assert comp["kind"] == "class"

    def test_class_props_always_empty(self):
        code = """\
class Foo extends Component {
  render() { return <div />; }
}
"""
        results = _extract(code)
        assert results[0]["props"] == []

    def test_class_not_extending_component_excluded(self):
        code = """\
class MyService {
  run() {}
}
"""
        assert _extract(code) == []

    def test_exported_class_component(self):
        code = "export class Hero extends Component { render() { return <h1 />; } }"
        results = _extract(code)
        assert results[0]["exported"] is True


# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------


class TestExcludeNonComponents:
    def test_lowercase_arrow_with_jsx_excluded(self):
        code = "const helper = () => <span />;"
        assert _extract(code) == []

    def test_uppercase_function_without_jsx_excluded(self):
        code = "function MyUtil() { return 42; }"
        assert _extract(code) == []

    def test_uppercase_arrow_without_jsx_excluded(self):
        code = "const MyCalc = () => 42;"
        assert _extract(code) == []


# ---------------------------------------------------------------------------
# Props extraction
# ---------------------------------------------------------------------------


class TestPropsExtraction:
    def test_destructured_props(self):
        code = "function Card({ title, body }) { return <div>{title}</div>; }"
        results = _extract(code)
        assert results[0]["props"] == ["title", "body"]

    def test_no_props_empty_list(self):
        code = "function Logo() { return <img />; }"
        results = _extract(code)
        assert results[0]["props"] == []

    def test_props_object_param_not_destructured_empty(self):
        # When first param is a plain identifier (not object pattern) → []
        code = "function Comp(props) { return <div>{props.name}</div>; }"
        results = _extract(code)
        assert results[0]["props"] == []

    def test_arrow_destructured_props(self):
        code = "const Btn = ({ label, onClick }) => <button onClick={onClick}>{label}</button>;"
        results = _extract(code)
        assert results[0]["props"] == ["label", "onClick"]

    def test_single_prop(self):
        code = "function Title({ text }) { return <h1>{text}</h1>; }"
        results = _extract(code)
        assert results[0]["props"] == ["text"]


# ---------------------------------------------------------------------------
# Exported
# ---------------------------------------------------------------------------


class TestExportedComponents:
    def test_default_export_function(self):
        code = "export default function App() { return <main />; }"
        results = _extract(code)
        assert results[0]["exported"] is True

    def test_named_export_arrow(self):
        code = "export const Widget = () => <section />;"
        results = _extract(code)
        assert results[0]["exported"] is True

    def test_non_exported_arrow(self):
        code = "const Internal = () => <aside />;"
        results = _extract(code)
        assert results[0]["exported"] is False


# ---------------------------------------------------------------------------
# Line numbers
# ---------------------------------------------------------------------------


class TestLineNumbers:
    def test_line_is_one_based(self):
        code = "function MyComp() { return <div />; }"
        results = _extract(code)
        assert results[0]["line"] == 1

    def test_multiple_components_have_correct_lines(self):
        code = """\
function A() { return <div />; }
function B() { return <span />; }
"""
        results = _extract(code)
        a = _find(results, name="A")
        b = _find(results, name="B")
        assert a is not None and a["line"] == 1
        assert b is not None and b["line"] == 2


# ---------------------------------------------------------------------------
# File field
# ---------------------------------------------------------------------------


class TestFileField:
    def test_file_embedded_in_every_entry(self):
        code = """\
function A() { return <div />; }
function B() { return <span />; }
"""
        results = _extract(code, file_path="app/comps.tsx")
        assert all(r["file"] == "app/comps.tsx" for r in results)

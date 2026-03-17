"""
Tests for aica.repo_intelligence.ast.extractors.functions

Covers:
    extract() — function declarations, generators, arrow functions, class methods
    exported   — True only when directly wrapped in an export_statement
    async      — async keyword detection
    params     — type annotations stripped; rest params handled
    name       — identifier from declaration or bound variable_declarator
    kind       — "function" | "generator" | "arrow" | "method"
    line       — 1-based
    file field — embedded in every output dict
"""

from __future__ import annotations

import pytest

from aica.repo_intelligence.ast.extractors.functions import extract
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


class TestFunctionsExtractorBasic:
    def test_empty_file_returns_empty_list(self):
        assert _extract("") == []

    def test_returns_list(self):
        result = _extract("function foo() {}")
        assert isinstance(result, list)

    def test_no_functions_returns_empty(self):
        result = _extract("const x = 1;\nconst y = 'hello';")
        assert result == []


# ---------------------------------------------------------------------------
# Function declarations
# ---------------------------------------------------------------------------


class TestFunctionDeclaration:
    def test_name(self):
        result = _extract("function add(a, b) { return a + b; }")
        assert result[0]["name"] == "add"

    def test_kind(self):
        result = _extract("function foo() {}")
        assert result[0]["kind"] == "function"

    def test_not_async_by_default(self):
        result = _extract("function foo() {}")
        assert result[0]["async"] is False

    def test_async_function(self):
        result = _extract("async function fetch() {}")
        assert result[0]["async"] is True

    def test_async_kind_is_still_function(self):
        result = _extract("async function fetch() {}")
        assert result[0]["kind"] == "function"


# ---------------------------------------------------------------------------
# Exported function declarations
# ---------------------------------------------------------------------------


class TestExportedFunctions:
    def test_exported_named_function(self):
        result = _extract("export function foo() {}")
        assert result[0]["exported"] is True

    def test_non_exported_function(self):
        result = _extract("function bar() {}")
        assert result[0]["exported"] is False

    def test_exported_async_function(self):
        result = _extract("export async function fetchData() {}")
        assert result[0]["exported"] is True

    def test_export_default_function(self):
        result = _extract("export default function Page() {}")
        assert result[0]["exported"] is True


# ---------------------------------------------------------------------------
# Generator functions
# ---------------------------------------------------------------------------


class TestGeneratorFunction:
    def test_kind_is_generator(self):
        result = _extract("function* gen() { yield 1; }")
        assert result[0]["kind"] == "generator"

    def test_name_captured(self):
        result = _extract("function* myGen() { yield 'a'; }")
        assert result[0]["name"] == "myGen"

    def test_exported_generator(self):
        result = _extract("export function* gen() { yield 1; }")
        assert result[0]["exported"] is True


# ---------------------------------------------------------------------------
# Arrow functions
# ---------------------------------------------------------------------------


class TestArrowFunction:
    def test_kind_is_arrow(self):
        result = _extract("const greet = () => {};")
        entry = _find(result, kind="arrow")
        assert entry is not None

    def test_name_from_declarator(self):
        result = _extract("const greet = (name: string) => name;")
        entry = _find(result, kind="arrow")
        assert entry is not None
        assert entry["name"] == "greet"

    def test_async_arrow(self):
        result = _extract("const load = async () => {};")
        entry = _find(result, kind="arrow")
        assert entry is not None
        assert entry["async"] is True

    def test_exported_arrow(self):
        result = _extract("export const handler = () => {};")
        entry = _find(result, kind="arrow")
        assert entry is not None
        assert entry["exported"] is True

    def test_non_exported_arrow(self):
        result = _extract("const helper = () => {};")
        entry = _find(result, kind="arrow")
        assert entry is not None
        assert entry["exported"] is False


# ---------------------------------------------------------------------------
# Class method definitions
# ---------------------------------------------------------------------------


class TestMethodDefinition:
    def test_kind_is_method(self):
        result = _extract("class Foo { bar() {} }")
        entry = _find(result, kind="method")
        assert entry is not None

    def test_method_name(self):
        result = _extract("class Foo { bar() {} }")
        entry = _find(result, kind="method")
        assert entry["name"] == "bar"

    def test_method_not_exported(self):
        """Methods are never directly exported — class controls visibility."""
        result = _extract("class Foo { bar() {} }")
        entry = _find(result, kind="method")
        assert entry["exported"] is False

    def test_async_method(self):
        result = _extract("class Foo { async bar() {} }")
        entry = _find(result, kind="method")
        assert entry["async"] is True


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------


class TestParamExtraction:
    def test_plain_params(self):
        result = _extract("function add(a, b) {}")
        assert result[0]["params"] == ["a", "b"]

    def test_typed_params_annotations_stripped(self):
        result = _extract("function add(a: number, b: number): number {}")
        assert result[0]["params"] == ["a", "b"]

    def test_no_params(self):
        result = _extract("function empty() {}")
        assert result[0]["params"] == []

    def test_optional_param(self):
        result = _extract("function greet(name: string, title?: string) {}")
        assert "name" in result[0]["params"]
        assert "title" in result[0]["params"]

    def test_rest_param(self):
        result = _extract("function log(...args: string[]) {}")
        assert "args" in result[0]["params"]

    def test_arrow_params(self):
        result = _extract("const add = (a: number, b: number) => a + b;")
        entry = _find(result, kind="arrow")
        assert entry["params"] == ["a", "b"]


# ---------------------------------------------------------------------------
# Line numbers
# ---------------------------------------------------------------------------


class TestLineNumbers:
    def test_function_on_line_1(self):
        result = _extract("function foo() {}")
        assert result[0]["line"] == 1

    def test_second_function_correct_line(self):
        code = "function a() {}\nfunction b() {}"
        result = _extract(code)
        names = {e["name"]: e["line"] for e in result if e.get("kind") == "function"}
        assert names["a"] == 1
        assert names["b"] == 2

    def test_multiline_gap(self):
        code = "function a() {}\n\n\nfunction b() {}"
        result = _extract(code)
        names = {e["name"]: e["line"] for e in result if e.get("kind") == "function"}
        assert names["b"] == 4


# ---------------------------------------------------------------------------
# file field
# ---------------------------------------------------------------------------


class TestFileField:
    def test_file_embedded_in_every_entry(self):
        code = "function a() {}\nconst b = () => {};"
        result = _extract(code, file_path="src/utils.ts")
        assert all(e["file"] == "src/utils.ts" for e in result)

    def test_file_matches_argument(self):
        result = _extract("function x() {}", file_path="custom/path.ts")
        assert result[0]["file"] == "custom/path.ts"


# ---------------------------------------------------------------------------
# TSX — exported components (arrow function in .tsx)
# ---------------------------------------------------------------------------


class TestTSXArrowFunctions:
    def test_tsx_exported_arrow(self):
        code = "export const Button = ({ label }: { label: string }) => <span>{label}</span>;"
        result = _extract(code, lang="tsx")
        entry = _find(result, kind="arrow")
        assert entry is not None
        assert entry["name"] == "Button"
        assert entry["exported"] is True

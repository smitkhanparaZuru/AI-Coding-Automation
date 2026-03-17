"""
Tests for the types extractor (Task 3.5).
"""

from __future__ import annotations

import pytest

from aica.repo_intelligence.ast.extractors.types import extract
from aica.repo_intelligence.ast.parser import parse_code

_FILE = "src/test.ts"


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
# Basic
# ---------------------------------------------------------------------------


class TestTypesExtractorBasic:
    def test_empty_file_returns_empty_list(self):
        assert _extract("") == []

    def test_return_type_is_list(self):
        assert isinstance(_extract("const x = 1;"), list)

    def test_no_types_in_plain_code(self):
        assert _extract("function foo() { return 42; }") == []

    def test_variable_declaration_not_captured(self):
        assert _extract("const x: string = 'hello';") == []


# ---------------------------------------------------------------------------
# Interface declaration
# ---------------------------------------------------------------------------


class TestInterfaceDeclaration:
    def test_simple_interface(self):
        code = "interface Foo { bar: string; }"
        results = _extract(code)
        assert len(results) == 1
        assert results[0]["name"] == "Foo"
        assert results[0]["kind"] == "interface"

    def test_interface_not_exported_by_default(self):
        code = "interface Foo { bar: string; }"
        results = _extract(code)
        assert results[0]["exported"] is False

    def test_multiple_interfaces(self):
        code = """\
interface Alpha { a: number; }
interface Beta { b: string; }
"""
        results = _extract(code)
        names = [r["name"] for r in results]
        assert "Alpha" in names
        assert "Beta" in names

    def test_empty_interface(self):
        code = "interface Empty {}"
        results = _extract(code)
        assert results[0]["name"] == "Empty"
        assert results[0]["members"] == []


# ---------------------------------------------------------------------------
# Exported interface
# ---------------------------------------------------------------------------


class TestExportedInterface:
    def test_exported_interface(self):
        code = "export interface User { id: number; name: string; }"
        results = _extract(code)
        assert results[0]["exported"] is True

    def test_non_exported_interface(self):
        code = "interface Internal { x: number; }"
        results = _extract(code)
        assert results[0]["exported"] is False

    def test_export_type_interface(self):
        code = "export interface Config { debug: boolean; }"
        results = _extract(code)
        assert results[0]["exported"] is True


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------


class TestTypeAlias:
    def test_simple_type_alias(self):
        code = "type Id = string;"
        results = _extract(code)
        assert len(results) == 1
        assert results[0]["name"] == "Id"
        assert results[0]["kind"] == "type"

    def test_type_alias_not_exported(self):
        code = "type Local = number;"
        results = _extract(code)
        assert results[0]["exported"] is False

    def test_union_type_alias(self):
        code = "type Status = 'active' | 'inactive';"
        results = _extract(code)
        assert results[0]["name"] == "Status"
        assert results[0]["kind"] == "type"

    def test_multiple_type_aliases(self):
        code = """\
type A = string;
type B = number;
"""
        results = _extract(code)
        names = [r["name"] for r in results]
        assert "A" in names
        assert "B" in names


# ---------------------------------------------------------------------------
# Exported type alias
# ---------------------------------------------------------------------------


class TestExportedTypeAlias:
    def test_exported_type_alias(self):
        code = "export type Theme = 'light' | 'dark';"
        results = _extract(code)
        assert results[0]["exported"] is True

    def test_non_exported_type_alias(self):
        code = "type Hidden = boolean;"
        results = _extract(code)
        assert results[0]["exported"] is False


# ---------------------------------------------------------------------------
# Members extraction
# ---------------------------------------------------------------------------


class TestMembers:
    def test_interface_property_members(self):
        code = "interface User { id: number; name: string; email: string; }"
        results = _extract(code)
        assert results[0]["members"] == ["id", "name", "email"]

    def test_interface_method_signature(self):
        code = "interface Repo { fetch(): Promise<void>; save(item: any): void; }"
        results = _extract(code)
        members = results[0]["members"]
        assert "fetch" in members
        assert "save" in members

    def test_interface_mixed_members(self):
        code = """\
interface Service {
  name: string;
  run(): void;
  stop(): Promise<void>;
}
"""
        results = _extract(code)
        members = results[0]["members"]
        assert "name" in members
        assert "run" in members
        assert "stop" in members

    def test_empty_interface_has_no_members(self):
        code = "interface Empty {}"
        results = _extract(code)
        assert results[0]["members"] == []


# ---------------------------------------------------------------------------
# Type alias members
# ---------------------------------------------------------------------------


class TestTypeAliasMembers:
    def test_object_type_alias_has_members(self):
        code = "type Point = { x: number; y: number; };"
        results = _extract(code)
        assert results[0]["members"] == ["x", "y"]

    def test_union_type_has_no_members(self):
        code = "type Direction = 'north' | 'south' | 'east' | 'west';"
        results = _extract(code)
        assert results[0]["members"] == []

    def test_primitive_type_alias_no_members(self):
        code = "type ID = string;"
        results = _extract(code)
        assert results[0]["members"] == []

    def test_intersection_type_no_members(self):
        code = "type AB = A & B;"
        results = _extract(code)
        assert results[0]["members"] == []


# ---------------------------------------------------------------------------
# Mixed interface + type in same file
# ---------------------------------------------------------------------------


class TestMixedDeclarations:
    def test_interface_and_type_in_same_file(self):
        code = """\
interface Props { label: string; }
type Status = 'ok' | 'error';
"""
        results = _extract(code)
        assert len(results) == 2
        kinds = {r["kind"] for r in results}
        assert kinds == {"interface", "type"}

    def test_exported_and_non_exported_mixed(self):
        code = """\
export interface Public { id: number; }
interface Private { secret: string; }
"""
        results = _extract(code)
        pub = _find(results, name="Public")
        priv = _find(results, name="Private")
        assert pub is not None and pub["exported"] is True
        assert priv is not None and priv["exported"] is False


# ---------------------------------------------------------------------------
# Line numbers
# ---------------------------------------------------------------------------


class TestLineNumbers:
    def test_line_is_one_based(self):
        code = "interface Foo { x: number; }"
        results = _extract(code)
        assert results[0]["line"] == 1

    def test_line_tracks_position(self):
        code = """\
const x = 1;
interface Bar { y: string; }
"""
        results = _extract(code)
        assert results[0]["line"] == 2

    def test_multiple_lines(self):
        code = """\
interface A { a: number; }
type B = string;
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
interface A { x: number; }
type B = string;
"""
        results = _extract(code, file_path="src/types.ts")
        assert all(r["file"] == "src/types.ts" for r in results)

    def test_file_field_posix_path(self):
        code = "interface Foo { x: number; }"
        results = _extract(code, file_path="app/models/user.ts")
        assert results[0]["file"] == "app/models/user.ts"

"""
Tests for aica.repo_intelligence.ast.extractors.exports

Covers:
    extract() — named, default, re-export, namespace-reexport forms
    name       — public exported binding; "default" for default exports; None for wildcards
    local_name — original local symbol; None for wildcards, anonymous defaults, destructuring
    kind       — "named" | "default" | "re-export" | "namespace-reexport"
    type_only  — True for `export type { Foo }`, interface declarations, type aliases
    source     — from-clause specifier for re-exports; None for local exports
    line       — 1-based
    file field — embedded in every output dict
"""

from __future__ import annotations

import pytest

from aica.repo_intelligence.ast.extractors.exports import extract
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


class TestExportsExtractorBasic:
    def test_empty_file_returns_empty_list(self):
        assert _extract("") == []

    def test_returns_list(self):
        result = _extract("export const x = 1;")
        assert isinstance(result, list)

    def test_non_export_code_returns_empty_list(self):
        result = _extract("const x = 1;\nfunction foo() {}")
        assert result == []

    def test_import_only_file_returns_empty(self):
        result = _extract("import React from 'react';")
        assert result == []


# ---------------------------------------------------------------------------
# Named export clause: export { a, b as c }
# ---------------------------------------------------------------------------


class TestNamedExportClause:
    def test_single_named_export(self):
        result = _extract("export { foo };")
        assert len(result) == 1
        assert result[0]["name"] == "foo"
        assert result[0]["local_name"] == "foo"

    def test_kind_is_named(self):
        result = _extract("export { foo };")
        assert result[0]["kind"] == "named"

    def test_source_is_none_for_local_export(self):
        result = _extract("export { foo };")
        assert result[0]["source"] is None

    def test_alias_export(self):
        result = _extract("export { foo as bar };")
        assert result[0]["name"] == "bar"
        assert result[0]["local_name"] == "foo"

    def test_multiple_specifiers(self):
        result = _extract("export { foo, bar, baz };")
        names = [e["name"] for e in result]
        assert names == ["foo", "bar", "baz"]

    def test_multiple_with_alias(self):
        result = _extract("export { foo as a, bar as b };")
        assert _find(result, name="a", local_name="foo") is not None
        assert _find(result, name="b", local_name="bar") is not None

    def test_type_only_export_clause(self):
        result = _extract("export type { Foo };")
        assert result[0]["type_only"] is True

    def test_non_type_export_clause(self):
        result = _extract("export { foo };")
        assert result[0]["type_only"] is False

    def test_file_field_embedded(self):
        result = _extract("export { foo };", file_path="src/utils.ts")
        assert result[0]["file"] == "src/utils.ts"

    def test_line_number_first_line(self):
        result = _extract("export { foo };")
        assert result[0]["line"] == 1

    def test_line_number_later_line(self):
        code = "const x = 1;\nexport { x };"
        result = _extract(code)
        assert result[0]["line"] == 2

    def test_empty_export_clause(self):
        result = _extract("export {};")
        assert result == []


# ---------------------------------------------------------------------------
# Inline declaration exports
# ---------------------------------------------------------------------------


class TestInlineDeclarationExports:
    def test_export_function(self):
        result = _extract("export function foo() {}")
        assert _find(result, name="foo", kind="named") is not None

    def test_export_function_local_name_matches(self):
        result = _extract("export function foo() {}")
        entry = result[0]
        assert entry["local_name"] == "foo"

    def test_export_generator_function(self):
        result = _extract("export function* gen() { yield 1; }")
        assert _find(result, name="gen", kind="named") is not None

    def test_export_async_function(self):
        result = _extract("export async function fetchData() {}")
        assert _find(result, name="fetchData", kind="named") is not None

    def test_export_const(self):
        result = _extract("export const API_URL = 'https://example.com';")
        assert _find(result, name="API_URL", kind="named") is not None

    def test_export_let(self):
        result = _extract("export let counter = 0;")
        assert _find(result, name="counter", kind="named") is not None

    def test_export_class(self):
        result = _extract("export class MyService {}")
        assert _find(result, name="MyService", kind="named") is not None

    def test_export_class_not_type_only(self):
        result = _extract("export class MyService {}")
        assert result[0]["type_only"] is False

    def test_export_interface_type_only(self):
        result = _extract("export interface UserProps { name: string; }")
        assert result[0]["type_only"] is True

    def test_export_interface_kind_is_named(self):
        result = _extract("export interface UserProps { name: string; }")
        assert result[0]["kind"] == "named"

    def test_export_interface_name(self):
        result = _extract("export interface UserProps { name: string; }")
        assert result[0]["name"] == "UserProps"

    def test_export_type_alias_type_only(self):
        result = _extract("export type UserId = string;")
        assert result[0]["type_only"] is True

    def test_export_type_alias_name(self):
        result = _extract("export type UserId = string;")
        assert result[0]["name"] == "UserId"

    def test_export_enum(self):
        result = _extract("export enum Direction { Up, Down, Left, Right }")
        assert _find(result, name="Direction", kind="named") is not None

    def test_export_enum_not_type_only(self):
        result = _extract("export enum Direction { Up, Down }")
        assert result[0]["type_only"] is False

    def test_export_multiple_const_declarators(self):
        result = _extract("export const a = 1, b = 2;")
        names = [e["name"] for e in result]
        assert "a" in names
        assert "b" in names

    def test_export_destructured_const_emits_null_name(self):
        result = _extract("export const { x, y } = obj;")
        assert len(result) == 1
        assert result[0]["name"] is None
        assert result[0]["local_name"] is None

    def test_inline_source_is_none(self):
        result = _extract("export function foo() {}")
        assert result[0]["source"] is None


# ---------------------------------------------------------------------------
# Default exports
# ---------------------------------------------------------------------------


class TestDefaultExports:
    def test_kind_is_default(self):
        result = _extract("export default foo;")
        assert result[0]["kind"] == "default"

    def test_name_is_default_string(self):
        result = _extract("export default foo;")
        assert result[0]["name"] == "default"

    def test_identifier_local_name(self):
        result = _extract("export default foo;")
        assert result[0]["local_name"] == "foo"

    def test_named_function_local_name(self):
        result = _extract("export default function Page() {}")
        assert result[0]["local_name"] == "Page"

    def test_anonymous_function_local_name_is_none(self):
        result = _extract("export default function() {}")
        assert result[0]["local_name"] is None

    def test_named_class_local_name(self):
        result = _extract("export default class Button {}")
        assert result[0]["local_name"] == "Button"

    def test_anonymous_class_local_name_is_none(self):
        result = _extract("export default class {}")
        assert result[0]["local_name"] is None

    def test_object_local_name_is_none(self):
        result = _extract("export default { key: 'value' };")
        assert result[0]["local_name"] is None

    def test_default_not_type_only(self):
        result = _extract("export default foo;")
        assert result[0]["type_only"] is False

    def test_default_source_is_none(self):
        result = _extract("export default foo;")
        assert result[0]["source"] is None

    def test_default_file_field(self):
        result = _extract("export default foo;", file_path="src/page.tsx")
        assert result[0]["file"] == "src/page.tsx"

    def test_default_line_number(self):
        code = "\nexport default foo;"
        result = _extract(code)
        assert result[0]["line"] == 2

    def test_generator_default(self):
        result = _extract("export default function* gen() { yield 1; }")
        assert result[0]["kind"] == "default"
        assert result[0]["local_name"] == "gen"


# ---------------------------------------------------------------------------
# Re-exports (from clause)
# ---------------------------------------------------------------------------


class TestReExports:
    def test_named_reexport_kind(self):
        result = _extract("export { foo } from './module';")
        assert result[0]["kind"] == "re-export"

    def test_named_reexport_source(self):
        result = _extract("export { foo } from './module';")
        assert result[0]["source"] == "./module"

    def test_named_reexport_name(self):
        result = _extract("export { foo } from './module';")
        assert result[0]["name"] == "foo"

    def test_named_reexport_local_name(self):
        result = _extract("export { foo } from './module';")
        assert result[0]["local_name"] == "foo"

    def test_aliased_reexport(self):
        result = _extract("export { foo as bar } from './module';")
        assert result[0]["name"] == "bar"
        assert result[0]["local_name"] == "foo"

    def test_wildcard_reexport_kind(self):
        result = _extract("export * from './module';")
        assert result[0]["kind"] == "re-export"

    def test_wildcard_reexport_name_is_none(self):
        result = _extract("export * from './module';")
        assert result[0]["name"] is None

    def test_wildcard_reexport_local_name_is_none(self):
        result = _extract("export * from './module';")
        assert result[0]["local_name"] is None

    def test_wildcard_reexport_source(self):
        result = _extract("export * from './module';")
        assert result[0]["source"] == "./module"

    def test_namespace_reexport_kind(self):
        result = _extract("export * as ns from './module';")
        assert result[0]["kind"] == "namespace-reexport"

    def test_namespace_reexport_name(self):
        result = _extract("export * as ns from './module';")
        assert result[0]["name"] == "ns"

    def test_namespace_reexport_local_name_is_none(self):
        result = _extract("export * as ns from './module';")
        assert result[0]["local_name"] is None

    def test_namespace_reexport_source(self):
        result = _extract("export * as ns from './module';")
        assert result[0]["source"] == "./module"

    def test_type_only_reexport(self):
        result = _extract("export type { Foo } from './types';")
        assert result[0]["type_only"] is True
        assert result[0]["source"] == "./types"

    def test_external_package_source(self):
        result = _extract("export * from 'react';")
        assert result[0]["source"] == "react"

    def test_alias_package_source(self):
        result = _extract("export { foo } from '@/utils';")
        assert result[0]["source"] == "@/utils"


# ---------------------------------------------------------------------------
# Multiple exports and ordering
# ---------------------------------------------------------------------------


class TestMultipleExports:
    def test_order_preserved(self):
        code = "export const a = 1;\nexport const b = 2;\nexport const c = 3;"
        result = _extract(code)
        assert [e["name"] for e in result] == ["a", "b", "c"]

    def test_mixed_kinds_in_one_file(self):
        code = "\n".join([
            "export const x = 1;",
            "export default MyComponent;",
            "export { foo } from './foo';",
            "export * from './bar';",
        ])
        result = _extract(code)
        kinds = [e["kind"] for e in result]
        assert "named" in kinds
        assert "default" in kinds
        assert "re-export" in kinds

    def test_count_matches_exports(self):
        code = "export { a, b, c };"
        result = _extract(code)
        assert len(result) == 3

    def test_tsx_file_works(self):
        code = "export default function Page() { return <div />; }"
        result = _extract(code, lang="tsx")
        assert result[0]["kind"] == "default"
        assert result[0]["local_name"] == "Page"

    def test_line_numbers_are_correct(self):
        code = "export const a = 1;\n\nexport const b = 2;"
        result = _extract(code)
        assert result[0]["line"] == 1
        assert result[1]["line"] == 3

    def test_no_duplicate_entries(self):
        code = "export { foo };export { bar };"
        result = _extract(code)
        names = [e["name"] for e in result]
        assert len(names) == len(set(names))

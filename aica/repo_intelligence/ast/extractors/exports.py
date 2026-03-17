"""
Exports extractor — Task 3.3

Extracts export statements from a tree-sitter TypeScript/TSX Tree.

Contract::

    extract(tree: Tree, source: str, file_path: str) -> list[dict]

Output schema per entry::

    {
        "file":       str,                      # POSIX-relative source path
        "name":       str | None,               # public exported name; "default" for default exports;
                                                #   None for wildcard re-exports
        "local_name": str | None,               # original local symbol; None for wildcards /
                                                #   anonymous defaults / destructured patterns
        "kind":       "named" | "default" | "re-export" | "namespace-reexport",
        "type_only":  bool,                     # true for `export type { Foo }` / interface / type alias
        "source":     str | None,               # from-clause module specifier for re-exports; None otherwise
        "line":       int,                      # 1-based
    }

Supported forms
---------------
- ``export { a }``                     → kind ``"named"``,              source=None
- ``export { a as b }``                → kind ``"named"``,              name="b", local_name="a"
- ``export type { Foo }``              → kind ``"named"``,              type_only=True
- ``export function foo() {}``         → kind ``"named"``,              inline declaration
- ``export const foo = ...``           → kind ``"named"``,              inline lexical_declaration
- ``export class Foo {}``              → kind ``"named"``,              inline declaration
- ``export interface Foo {}``          → kind ``"named"``,              type_only=True
- ``export type Foo = ...``            → kind ``"named"``,              type_only=True
- ``export enum Foo { ... }``          → kind ``"named"``
- ``export default foo``               → kind ``"default"``,            name="default"
- ``export default function() {}``     → kind ``"default"``,            local_name=None
- ``export default function foo() {}`` → kind ``"default"``,            local_name="foo"
- ``export { foo } from './m'``        → kind ``"re-export"``,          source="./m"
- ``export * from './m'``              → kind ``"re-export"``,          name=None, source="./m"
- ``export * as ns from './m'``        → kind ``"namespace-reexport"``, source="./m"

Destructuring rule
------------------
``export const { a, b } = obj`` → emitted as ``{name: None, local_name: None}`` (one entry per
declarator whose pattern is not a plain identifier). This mirrors ``functions.py`` behaviour.

Scope
-----
Only top-level ``export_statement`` nodes are walked — exports are always top-level in ES modules.
No deep traversal is required.
"""

from __future__ import annotations

from tree_sitter import Tree

from aica.core.logging import get_logger

log = get_logger("repo.ast.extractors.exports")

_INLINE_DECL_TYPES: frozenset[str] = frozenset({
    "function_declaration",
    "generator_function_declaration",
    "class_declaration",
    "abstract_class_declaration",
    "lexical_declaration",
    "variable_declaration",
    "interface_declaration",
    "type_alias_declaration",
    "enum_declaration",
})

# These declaration types are always type-only at the semantic level
_TYPE_DECL_TYPES: frozenset[str] = frozenset({
    "interface_declaration",
    "type_alias_declaration",
})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _decode(node) -> str:
    return node.text.decode("utf-8") if node is not None else ""


def _strip_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] in ('"', "'", "`") and text[-1] == text[0]:
        return text[1:-1]
    return text


def _find_child(node, child_type: str):
    """Return the first direct child whose .type matches *child_type*, or None."""
    for child in node.children:
        if child.type == child_type:
            return child
    return None


def _is_type_only(node) -> bool:
    """Return True if the export_statement contains a top-level ``type`` keyword.

    Detects ``export type { ... }`` form only.  The ``export interface`` /
    ``export type Foo = ...`` forms are handled in ``_process_inline_declaration``
    via ``_TYPE_DECL_TYPES``.
    """
    for child in node.children:
        if child.type == "type":
            return True
    return False


def _get_source(node) -> str | None:
    """Extract the from-clause module specifier from an export_statement, or None.

    The specifier is always the last ``string`` child in the node.
    """
    specifier: str | None = None
    for child in node.children:
        if child.type == "string":
            specifier = _strip_quotes(_decode(child))
    return specifier


# ---------------------------------------------------------------------------
# Dispatch helpers
# ---------------------------------------------------------------------------


def _process_export_clause(
    clause_node,
    source: str | None,
    type_only: bool,
    file_path: str,
    line: int,
) -> list[dict]:
    """Process ``export { a, b as c }`` or ``export { a } from './m'``."""
    kind = "re-export" if source is not None else "named"
    results: list[dict] = []

    for child in clause_node.children:
        if child.type != "export_specifier":
            continue

        name_node = child.child_by_field_name("name")
        alias_node = child.child_by_field_name("alias")

        if name_node is None:
            # Fallback: collect identifiers in source order
            identifiers = [c for c in child.children if c.type == "identifier"]
            name_node = identifiers[0] if identifiers else None
            alias_node = identifiers[1] if len(identifiers) > 1 else None

        if name_node is None:
            continue

        local = _decode(name_node)
        exported = _decode(alias_node) if alias_node is not None else local

        results.append({
            "file": file_path,
            "name": exported,
            "local_name": local,
            "kind": kind,
            "type_only": type_only,
            "source": source,
            "line": line,
        })

    return results


def _process_inline_declaration(
    decl_node,
    type_only: bool,
    file_path: str,
    line: int,
) -> list[dict]:
    """Process ``export function foo() {}``, ``export const foo = ...``, etc."""
    decl_type = decl_node.type
    # Interface and type alias declarations are always type-only
    effective_type_only = type_only or (decl_type in _TYPE_DECL_TYPES)

    if decl_type in ("lexical_declaration", "variable_declaration"):
        results: list[dict] = []
        for child in decl_node.children:
            if child.type != "variable_declarator":
                continue
            name_node = child.child_by_field_name("name")
            if name_node is not None and name_node.type == "identifier":
                name: str | None = _decode(name_node)
            else:
                # Destructuring pattern — emit null name (consistent with functions.py)
                name = None
            results.append({
                "file": file_path,
                "name": name,
                "local_name": name,
                "kind": "named",
                "type_only": effective_type_only,
                "source": None,
                "line": line,
            })
        return results

    # function / generator / class / abstract_class / interface / type_alias / enum
    name_node = decl_node.child_by_field_name("name")
    name = _decode(name_node) if name_node is not None else None
    return [{
        "file": file_path,
        "name": name,
        "local_name": name,
        "kind": "named",
        "type_only": effective_type_only,
        "source": None,
        "line": line,
    }]


def _process_default(
    export_node,
    type_only: bool,
    file_path: str,
    line: int,
) -> list[dict]:
    """Process ``export default expr``."""
    local_name: str | None = None
    seen_default = False

    for child in export_node.children:
        if not seen_default:
            if child.type == "default":
                seen_default = True
            continue

        ctype = child.type
        if ctype == "identifier":
            local_name = _decode(child)
            break
        if ctype in (
            "function_declaration",
            "generator_function_declaration",
            "class_declaration",
            "abstract_class_declaration",
        ):
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                local_name = _decode(name_node)
            break
        # Any other expression (object literal, call expression, etc.) → None
        break

    return [{
        "file": file_path,
        "name": "default",
        "local_name": local_name,
        "kind": "default",
        "type_only": type_only,
        "source": None,
        "line": line,
    }]


def _process_namespace_reexport(
    ns_node,
    source: str | None,
    type_only: bool,
    file_path: str,
    line: int,
) -> list[dict]:
    """Process ``export * as ns from './m'``."""
    # namespace_export node: `* as name`
    alias_node = ns_node.child_by_field_name("name")
    if alias_node is None:
        # Fallback: last identifier child
        identifiers = [c for c in ns_node.children if c.type == "identifier"]
        alias_node = identifiers[-1] if identifiers else None

    name = _decode(alias_node) if alias_node is not None else None
    return [{
        "file": file_path,
        "name": name,
        "local_name": None,
        "kind": "namespace-reexport",
        "type_only": type_only,
        "source": source,
        "line": line,
    }]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(tree: Tree, source: str, file_path: str) -> list[dict]:
    """Extract all export statements from *tree*.

    Args:
        tree: Parsed tree-sitter :class:`~tree_sitter.Tree`.
        source: Original source string (accepted for API consistency, not used).
        file_path: POSIX-relative path of the source file — embedded in every
            output dict as ``"file"``.

    Returns:
        A list of export dicts ordered by source position.
    """
    results: list[dict] = []

    for node in tree.root_node.children:
        if node.type != "export_statement":
            continue

        line = node.start_point[0] + 1
        type_only = _is_type_only(node)
        source_mod = _get_source(node)

        # ── namespace re-export: `export * as ns from '...'` ──────────────
        ns_node = _find_child(node, "namespace_export")
        if ns_node is not None:
            results.extend(
                _process_namespace_reexport(ns_node, source_mod, type_only, file_path, line)
            )
            continue

        # ── wildcard re-export: `export * from '...'` ─────────────────────
        if any(c.type == "*" for c in node.children):
            results.append({
                "file": file_path,
                "name": None,
                "local_name": None,
                "kind": "re-export",
                "type_only": type_only,
                "source": source_mod,
                "line": line,
            })
            continue

        # ── named/re-export clause: `export { a }` or `export { a } from` ──
        clause = _find_child(node, "export_clause")
        if clause is not None:
            results.extend(
                _process_export_clause(clause, source_mod, type_only, file_path, line)
            )
            continue

        # ── default export: `export default ...` ──────────────────────────
        if any(c.type == "default" for c in node.children):
            results.extend(_process_default(node, type_only, file_path, line))
            continue

        # ── inline declaration: `export function/const/class/...` ──────────
        for child in node.children:
            if child.type in _INLINE_DECL_TYPES:
                results.extend(
                    _process_inline_declaration(child, type_only, file_path, line)
                )
                break

    log.debug("exports.extracted", file=file_path, count=len(results))
    return results

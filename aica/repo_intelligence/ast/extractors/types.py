"""
Types extractor — Task 3.5

Extracts TypeScript interface and type alias declarations from a tree-sitter
TypeScript/TSX Tree.

Contract::

    extract(tree: Tree, source: str, file_path: str) -> list[dict]

Output schema per entry::

    {
        "file":     str,                    # POSIX-relative source path
        "name":     str,                    # type or interface name
        "kind":     "interface" | "type",   # which declaration form
        "exported": bool,                   # direct parent is export_statement
        "members":  list[str],              # property/method names in the body
        "line":     int,                    # 1-based
    }

Supported declarations
-----------------------
- ``interface Foo { bar: string; baz(): void; }``
  → kind ``"interface"``, members ``["bar", "baz"]``
- ``type Foo = { bar: string }``
  → kind ``"type"``, members ``["bar"]``
- ``type Foo = string | number``
  → kind ``"type"``, members ``[]``  (non-object alias)

Members extraction
------------------
For ``interface_declaration``: walk the ``object_type`` body looking for
``property_signature`` and ``method_signature`` children and read each
node's ``name`` named field (or first ``property_identifier`` child).

For ``type_alias_declaration``: inspect the ``value`` child node — if it is
``object_type``, apply the same member walk; otherwise ``members = []``.

Exported
--------
A declaration is considered ``exported`` when its immediate parent node's
type is ``"export_statement"``.  (Types and interfaces are always declared
at the top level in well-formed TypeScript, but the extractor performs a
full tree walk for correctness with nested module declarations.)

Scope
-----
Full depth-first tree walk — captures both top-level and namespace/module-
nested declarations.
"""

from __future__ import annotations

from tree_sitter import Tree

from aica.core.logging import get_logger

log = get_logger("repo.ast.extractors.types")

_MEMBER_NODE_TYPES: frozenset[str] = frozenset({
    "property_signature",
    "method_signature",
    "property_definition",
    "method_definition",
})

# Node types accepted as a member container body
_BODY_NODE_TYPES: frozenset[str] = frozenset({
    "object_type",    # type alias: `type Foo = { ... }`
    "interface_body", # interface declaration body in this grammar version
})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _walk(node):
    """Yield *node* and every descendant in depth-first order."""
    yield node
    for child in node.children:
        yield from _walk(child)


def _decode(node) -> str:
    return node.text.decode("utf-8") if node is not None else ""


def _member_name(node) -> str | None:
    """Return the name of a property_signature or method_signature node."""
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _decode(name_node)
    for child in node.children:
        if child.type in ("property_identifier", "identifier", "string"):
            return _decode(child)
    return None


def _extract_members(body_node) -> list[str]:
    """Walk an interface_body or object_type node and extract member names.

    Accepts both ``interface_body`` (interface declarations) and ``object_type``
    (object-typed type aliases) as valid container nodes.  Only direct children
    are considered — nested types are not recursed into.
    """
    if body_node is None:
        return []
    # Resolve the target: accept known body types directly; otherwise try to
    # find an object_type or interface_body one level down.
    if body_node.type in _BODY_NODE_TYPES:
        target = body_node
    else:
        target = None
        for child in body_node.children:
            if child.type in _BODY_NODE_TYPES:
                target = child
                break
        if target is None:
            return []
    names: list[str] = []
    for child in target.children:
        if child.type in _MEMBER_NODE_TYPES:
            name = _member_name(child)
            if name is not None:
                names.append(name)
    return names


def _is_exported(node) -> bool:
    """Return True if the immediate parent of *node* is an export_statement."""
    return node.parent is not None and node.parent.type == "export_statement"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(tree: Tree, source: str, file_path: str) -> list[dict]:
    """Extract all interface and type alias declarations from *tree*.

    Args:
        tree: Parsed tree-sitter :class:`~tree_sitter.Tree`.
        source: Original source string (accepted for API consistency, not used).
        file_path: POSIX-relative path of the source file — embedded in every
            output dict as ``"file"``.

    Returns:
        List of type descriptor dicts; empty list when no types found.
    """
    results: list[dict] = []
    seen: set[tuple[int, int]] = set()  # deduplicate by (row, col) start position

    for node in _walk(tree.root_node):
        pos = (node.start_point[0], node.start_point[1])
        if pos in seen:
            continue

        if node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _decode(name_node)
            body_node = node.child_by_field_name("body")
            seen.add(pos)
            results.append({
                "file": file_path,
                "name": name,
                "kind": "interface",
                "exported": _is_exported(node),
                "members": _extract_members(body_node),
                "line": node.start_point[0] + 1,
            })

        elif node.type == "type_alias_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _decode(name_node)
            value_node = node.child_by_field_name("value")
            seen.add(pos)
            results.append({
                "file": file_path,
                "name": name,
                "kind": "type",
                "exported": _is_exported(node),
                "members": _extract_members(value_node),
                "line": node.start_point[0] + 1,
            })

    log.debug(
        "repo.ast.extractors.types.extracted",
        file=file_path,
        types=len(results),
    )

    return results

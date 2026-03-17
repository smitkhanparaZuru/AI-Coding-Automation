"""
Hooks extractor — Task 3.5

Extracts React hook invocations from a tree-sitter TypeScript/TSX Tree.

Contract::

    extract(tree: Tree, source: str, file_path: str) -> list[dict]

Output schema per entry::

    {
        "file":       str,         # POSIX-relative source path
        "name":       str,         # hook name e.g. "useState", "useMyHook"
        "caller":     str | None,  # innermost enclosing named function; None = module-level
        "args_count": int,         # number of call arguments
        "line":       int,         # 1-based
    }

Detection rule
--------------
A ``call_expression`` is a hook call when its ``function`` child is an
``identifier`` whose text matches ``/^use[A-Z]/`` (i.e. ``use`` followed
immediately by an uppercase letter).  This follows the official React hooks
naming convention.

Caller resolution
-----------------
The ``caller`` field is the name of the innermost enclosing function-like node.
Anonymous arrows / function expressions without a bound variable → ``None``.
Module-level calls (outside any function) → ``None``.
Resolution algorithm is identical to ``calls.py``.

Scope
-----
Every ``call_expression`` at any nesting depth is considered — including
hooks called inside callbacks, other hooks, or JSX props.
"""

from __future__ import annotations

import re

from tree_sitter import Tree

from aica.core.logging import get_logger

log = get_logger("repo.ast.extractors.hooks")

_HOOK_RE = re.compile(r"^use[A-Z]")

_FUNCTION_NODE_TYPES: frozenset[str] = frozenset({
    "function_declaration",
    "generator_function_declaration",
    "function_expression",
    "generator_function",
    "arrow_function",
    "method_definition",
})


# ---------------------------------------------------------------------------
# Private helpers (shared pattern from calls.py)
# ---------------------------------------------------------------------------


def _walk(node):
    """Yield *node* and every descendant in depth-first order."""
    yield node
    for child in node.children:
        yield from _walk(child)


def _decode(node) -> str:
    """Decode a tree-sitter node's bytes to str."""
    return node.text.decode("utf-8") if node is not None else ""


def _node_name(node) -> str | None:
    """Return the name of a function-like *node*, following naming conventions.

    - ``function_declaration`` / ``generator_function_declaration``:
      use the ``name`` named field.
    - ``arrow_function`` / ``function_expression`` / ``generator_function``:
      walk up to the nearest ``variable_declarator`` (up to 4 levels) and
      read its ``name`` field.
    - ``method_definition``:
      use the ``name`` named field or first ``property_identifier`` child.
    """
    t = node.type

    if t in ("function_declaration", "generator_function_declaration"):
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return _decode(name_node)
        for child in node.children:
            if child.type == "identifier":
                return _decode(child)
        return None

    if t in ("arrow_function", "function_expression", "generator_function"):
        parent = node.parent
        depth = 0
        while parent is not None and depth < 4:
            if parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node is not None and name_node.type == "identifier":
                    return _decode(name_node)
                for child in parent.children:
                    if child.type == "identifier":
                        return _decode(child)
            parent = parent.parent
            depth += 1
        return None

    if t == "method_definition":
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return _decode(name_node)
        for child in node.children:
            if child.type == "property_identifier":
                return _decode(child)
        return None

    return None


def _enclosing_caller(node) -> str | None:
    """Walk up the ancestor chain and return the name of the innermost enclosing
    function-like node, or ``None`` if the call is at module level or inside an
    anonymous function.
    """
    parent = node.parent
    while parent is not None:
        if parent.type in _FUNCTION_NODE_TYPES:
            return _node_name(parent)
        parent = parent.parent
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(tree: Tree, source: str, file_path: str) -> list[dict]:
    """Extract all React hook call sites from *tree*.

    Args:
        tree: Parsed tree-sitter :class:`~tree_sitter.Tree`.
        source: Original source string (accepted for API consistency, not used).
        file_path: POSIX-relative path of the source file — embedded in every
            output dict as ``"file"``.

    Returns:
        Flat list of hook call descriptor dicts; empty list when no hooks found.
    """
    results: list[dict] = []
    seen: set[tuple[int, int]] = set()  # deduplicate by (row, col) start position

    for node in _walk(tree.root_node):
        if node.type != "call_expression":
            continue

        func_node = node.child_by_field_name("function")
        if func_node is None or func_node.type != "identifier":
            continue

        name = _decode(func_node)
        if not _HOOK_RE.match(name):
            continue

        pos = (node.start_point[0], node.start_point[1])
        if pos in seen:
            continue
        seen.add(pos)

        # Count arguments from the arguments child
        args_node = node.child_by_field_name("arguments")
        args_count = 0
        if args_node is not None:
            args_count = sum(
                1
                for child in args_node.children
                if child.type not in ("(", ")", ",")
            )

        results.append({
            "file": file_path,
            "name": name,
            "caller": _enclosing_caller(node),
            "args_count": args_count,
            "line": node.start_point[0] + 1,
        })

    log.debug(
        "repo.ast.extractors.hooks.extracted",
        file=file_path,
        hooks=len(results),
    )

    return results

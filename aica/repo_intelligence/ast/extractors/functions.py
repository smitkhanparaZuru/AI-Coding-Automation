"""
Functions extractor — Task 3.2

Extracts function definitions from a tree-sitter TypeScript/TSX Tree.

Contract::

    extract(tree: Tree, source: str, file_path: str) -> list[dict]

Output schema per entry::

    {
        "file":     str,                                # POSIX-relative source path
        "name":     str | None,                         # None for anonymous arrows
        "kind":     "function" | "arrow" | "method" | "generator",
        "async":    bool,
        "params":   list[str],                          # type annotations stripped
        "line":     int,                                # 1-based
        "exported": bool,                               # directly exported
    }

Supported node types
--------------------
- ``function_declaration``         → kind ``"function"``
- ``generator_function_declaration`` → kind ``"generator"``
- ``arrow_function``               → kind ``"arrow"``
- ``method_definition``            → kind ``"method"``

Scope
-----
Top-level declarations and class methods are captured.  Deeply nested
callbacks (e.g. arrow functions inside object literals or JSX props) are
also walked but will have ``name=None`` unless they are bound to a
``const``/``let``/``var`` declarator.

``exported`` rules
------------------
- ``function_declaration`` / ``generator_function_declaration``: direct
  parent is ``export_statement``.
- ``arrow_function``: ``export_statement`` found within 4 ancestor levels.
- ``method_definition``: always ``False`` (class controls visibility).
"""

from __future__ import annotations

from tree_sitter import Tree

from aica.core.logging import get_logger

log = get_logger("repo.ast.extractors.functions")

_FUNCTION_KINDS: dict[str, str] = {
    "function_declaration": "function",
    "generator_function_declaration": "generator",
    "arrow_function": "arrow",
    "method_definition": "method",
}


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


def _is_async(node) -> bool:
    """Return True if the function node has an ``async`` keyword child."""
    return any(c.type == "async" for c in node.children)


def _param_name(node) -> str | None:
    """Extract a single parameter name from a variably-typed parameter node."""
    if node.type == "identifier":
        return _decode(node)

    if node.type in ("required_parameter", "optional_parameter"):
        # pattern field holds the binding; often just an identifier
        pattern = node.child_by_field_name("pattern")
        if pattern is not None:
            if pattern.type == "identifier":
                return _decode(pattern)
            if pattern.type in ("rest_pattern", "rest_element"):
                # ...args  →  identifier inside the rest node
                for child in pattern.children:
                    if child.type == "identifier":
                        return _decode(child)
        # Fallback: first identifier child
        for child in node.children:
            if child.type == "identifier":
                return _decode(child)

    if node.type in ("rest_pattern", "rest_element"):
        # bare rest node (when not wrapped in required_parameter)
        for child in node.children:
            if child.type == "identifier":
                return _decode(child)

    if node.type == "assignment_pattern":
        # a = default  →  left side
        left = node.child_by_field_name("left")
        if left is not None and left.type == "identifier":
            return _decode(left)
        for child in node.children:
            if child.type == "identifier":
                return _decode(child)

    return None  # skip destructured / complex patterns


def _get_params(node) -> list[str]:
    """Extract parameter names from *node*'s ``formal_parameters`` child."""
    params_node = node.child_by_field_name("parameters")
    if params_node is None:
        # Arrow with a single unparenthesised identifier param
        for child in node.children:
            if child.type == "identifier":
                return [_decode(child)]
        return []

    return [
        name
        for child in params_node.children
        if (name := _param_name(child)) is not None
    ]


def _name_from_declaration(node) -> str | None:
    """Return the name field of a function/generator declaration node."""
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _decode(name_node)
    # Fallback: first identifier child
    for child in node.children:
        if child.type == "identifier":
            return _decode(child)
    return None


def _arrow_name(node) -> str | None:
    """Walk up ancestors to find a ``variable_declarator`` and return its binding name."""
    parent = node.parent
    depth = 0
    while parent is not None and depth < 4:
        if parent.type == "variable_declarator":
            name_node = parent.child_by_field_name("name")
            if name_node is not None and name_node.type == "identifier":
                return _decode(name_node)
            # Fallback: first identifier child of the declarator
            for child in parent.children:
                if child.type == "identifier":
                    return _decode(child)
        parent = parent.parent
        depth += 1
    return None


def _method_name(node) -> str | None:
    """Return the method name from a ``method_definition`` node."""
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _decode(name_node)
    for child in node.children:
        if child.type == "property_identifier":
            return _decode(child)
    return None


def _is_exported(node, kind: str) -> bool:
    """Return True if *node* is directly wrapped in an ``export_statement``."""
    if kind == "method":
        return False
    parent = node.parent
    depth = 0
    while parent is not None and depth < 4:
        if parent.type == "export_statement":
            return True
        parent = parent.parent
        depth += 1
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(tree: Tree, source: str, file_path: str) -> list[dict]:
    """Extract all function definitions from *tree*.

    Args:
        tree: Parsed tree-sitter :class:`~tree_sitter.Tree`.
        source: Original source string (accepted for API consistency, not used).
        file_path: POSIX-relative path of the source file — embedded in every
            output dict as ``"file"``.

    Returns:
        List of function descriptor dicts; empty list when no functions found.
    """
    results: list[dict] = []
    seen: set[tuple[int, int]] = set()  # deduplicate by (row, col) start position

    for node in _walk(tree.root_node):
        kind_str = _FUNCTION_KINDS.get(node.type)
        if kind_str is None:
            continue

        pos = (node.start_point[0], node.start_point[1])
        if pos in seen:
            continue
        seen.add(pos)

        if kind_str in ("function", "generator"):
            name = _name_from_declaration(node)
        elif kind_str == "arrow":
            name = _arrow_name(node)
        else:  # method
            name = _method_name(node)

        results.append({
            "file": file_path,
            "name": name,
            "kind": kind_str,
            "async": _is_async(node),
            "params": _get_params(node),
            "line": node.start_point[0] + 1,
            "exported": _is_exported(node, kind_str),
        })

    log.debug("functions.extracted", file=file_path, count=len(results))
    return results

"""
Components extractor — Task 3.5

Extracts React component definitions from a tree-sitter TypeScript/TSX Tree.

Contract::

    extract(tree: Tree, source: str, file_path: str) -> list[dict]

Output schema per entry::

    {
        "file":     str,                             # POSIX-relative source path
        "name":     str,                             # component name (PascalCase)
        "kind":     "function" | "arrow" | "class",  # declaration form
        "props":    list[str],                       # names from first-param object destructuring
        "exported": bool,                            # directly wrapped in export_statement
        "line":     int,                             # 1-based
    }

Detection rules
---------------
**Function / generator declarations** (``function_declaration``,
``generator_function_declaration``):

- Name starts with an uppercase letter
- Body subtree contains at least one JSX node (``jsx_element`` or
  ``jsx_self_closing_element``)

**Arrow functions** (``arrow_function``):

- Name resolved from the nearest ``variable_declarator`` ancestor (same lookup
  as ``functions.py``, up to 4 levels)
- Name starts with an uppercase letter
- Body subtree contains at least one JSX node

**Class declarations** (``class_declaration``):

- Name starts with an uppercase letter
- Has an ``extends`` clause whose text contains ``Component`` (covers both
  ``extends Component`` and ``extends React.Component``)
- No JSX scan required for class form

Props extraction
----------------
Inspects the first parameter of ``formal_parameters``.  If that parameter
(or its ``pattern`` field for typed params) is an ``object_pattern``, the
property names are extracted:

- ``shorthand_property_identifier_pattern`` (e.g. ``{ name }``) → ``"name"``
- ``pair_pattern``, ``object_assignment_pattern`` key side → identifier text

``exported`` rules
------------------
Same ancestor scan as ``functions.py``:

- ``function_declaration`` / ``generator_function_declaration`` / ``class_declaration``:
  direct parent is ``export_statement``.
- ``arrow_function``: ``export_statement`` found within 4 ancestor levels.
"""

from __future__ import annotations

from tree_sitter import Tree

from aica.core.logging import get_logger

log = get_logger("repo.ast.extractors.components")

_JSX_NODE_TYPES: frozenset[str] = frozenset({
    "jsx_element",
    "jsx_self_closing_element",
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


def _is_uppercase_start(name: str) -> bool:
    return bool(name) and name[0].isupper()


def _has_jsx(node) -> bool:
    """Return True if the subtree rooted at *node* contains any JSX node."""
    for descendant in _walk(node):
        if descendant.type in _JSX_NODE_TYPES:
            return True
    return False


def _extract_props(params_node) -> list[str]:
    """Extract property names from an object-destructured first parameter.

    Inspects only the first non-punctuation child of ``formal_parameters``.
    Returns an empty list when the first param is not an object pattern.
    """
    if params_node is None:
        return []

    # Collect actual parameter children (skip punctuation)
    param_children = [
        c for c in params_node.children
        if c.type not in ("(", ")", ",")
    ]
    if not param_children:
        return []

    first = param_children[0]

    # Typed params wrap the pattern in required_parameter / optional_parameter
    if first.type in ("required_parameter", "optional_parameter"):
        pattern_node = first.child_by_field_name("pattern")
        if pattern_node is not None:
            first = pattern_node

    if first.type != "object_pattern":
        return []

    names: list[str] = []
    for child in first.children:
        if child.type == "shorthand_property_identifier_pattern":
            names.append(_decode(child))
        elif child.type in ("pair_pattern", "object_assignment_pattern"):
            # key: value or key = default
            key = child.child_by_field_name("key")
            if key is not None and key.type == "property_identifier":
                names.append(_decode(key))
            else:
                # Fallback: first property_identifier or identifier child
                for c in child.children:
                    if c.type in ("property_identifier", "identifier"):
                        names.append(_decode(c))
                        break
    return names


def _name_from_declaration(node) -> str | None:
    """Return name from a function/class/generator declaration node."""
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _decode(name_node)
    for child in node.children:
        if child.type == "identifier":
            return _decode(child)
    return None


def _arrow_name(node) -> str | None:
    """Walk up ancestors to find a variable_declarator and return its binding name."""
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


def _is_exported(node) -> bool:
    """Return True if *node* is directly wrapped in an export_statement (up to 4 levels)."""
    parent = node.parent
    depth = 0
    while parent is not None and depth < 4:
        if parent.type == "export_statement":
            return True
        parent = parent.parent
        depth += 1
    return False


def _extends_component(node) -> bool:
    """Return True if the class_declaration extends a React Component base class."""
    # Look for class_heritage → extends_clause → identifier or member_expression
    for child in node.children:
        if child.type == "class_heritage":
            text = _decode(child)
            return "Component" in text
    return False


def _body_node(node) -> object | None:
    """Return the body child of a function/arrow/class node."""
    body = node.child_by_field_name("body")
    if body is not None:
        return body
    # Arrow functions with expression body have no named 'body' field in some grammars;
    # fall back to scanning children for statement_block or non-parameter/identifier children
    for child in node.children:
        if child.type in (
            "statement_block",
            "parenthesized_expression",
            "jsx_element",
            "jsx_self_closing_element",
            "jsx_fragment",
        ):
            return child
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(tree: Tree, source: str, file_path: str) -> list[dict]:
    """Extract all React component definitions from *tree*.

    Args:
        tree: Parsed tree-sitter :class:`~tree_sitter.Tree`.
        source: Original source string (accepted for API consistency, not used).
        file_path: POSIX-relative path of the source file — embedded in every
            output dict as ``"file"``.

    Returns:
        List of component descriptor dicts; empty list when no components found.
    """
    results: list[dict] = []
    seen: set[tuple[int, int]] = set()  # deduplicate by (row, col) start position

    for node in _walk(tree.root_node):
        pos = (node.start_point[0], node.start_point[1])
        if pos in seen:
            continue

        if node.type in ("function_declaration", "generator_function_declaration"):
            name = _name_from_declaration(node)
            if name is None or not _is_uppercase_start(name):
                continue
            body = _body_node(node)
            if body is None or not _has_jsx(body):
                continue
            seen.add(pos)
            params_node = node.child_by_field_name("parameters")
            results.append({
                "file": file_path,
                "name": name,
                "kind": "function",
                "props": _extract_props(params_node),
                "exported": _is_exported(node),
                "line": node.start_point[0] + 1,
            })

        elif node.type == "arrow_function":
            name = _arrow_name(node)
            if name is None or not _is_uppercase_start(name):
                continue
            body = _body_node(node)
            if body is None or not _has_jsx(body):
                continue
            seen.add(pos)
            params_node = node.child_by_field_name("parameters")
            results.append({
                "file": file_path,
                "name": name,
                "kind": "arrow",
                "props": _extract_props(params_node),
                "exported": _is_exported(node),
                "line": node.start_point[0] + 1,
            })

        elif node.type == "class_declaration":
            name = _name_from_declaration(node)
            if name is None or not _is_uppercase_start(name):
                continue
            if not _extends_component(node):
                continue
            seen.add(pos)
            results.append({
                "file": file_path,
                "name": name,
                "kind": "class",
                "props": [],
                "exported": _is_exported(node),
                "line": node.start_point[0] + 1,
            })

    log.debug(
        "repo.ast.extractors.components.extracted",
        file=file_path,
        components=len(results),
    )

    return results

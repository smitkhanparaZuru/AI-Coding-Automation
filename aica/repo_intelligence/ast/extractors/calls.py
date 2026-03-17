"""
Calls extractor — Task 3.4

Extracts function call sites from a tree-sitter TypeScript/TSX Tree.

Contract::

    extract(tree: Tree, source: str, file_path: str) -> list[dict]

Output schema per entry::

    {
        "file":          str,            # POSIX-relative source path
        "caller":        str | None,     # enclosing named function; None = module-level / anonymous
        "callee":        str,            # name of the called function or method
        "callee_object": str | None,     # receiver object for method calls (obj for obj.bar())
        "kind":          "call" | "new", # "new" for `new Foo()` constructor calls
        "line":          int,            # 1-based
    }

Supported call forms
---------------------
- ``foo()``             → callee="foo",   callee_object=None,  kind="call"
- ``obj.bar()``         → callee="bar",   callee_object="obj", kind="call"
- ``a.b.c()``           → callee="c",     callee_object="a.b", kind="call"
- ``new Foo()``         → callee="Foo",   callee_object=None,  kind="new"
- ``new ns.Bar()``      → callee="Bar",   callee_object="ns",  kind="new"

Caller resolution
-----------------
The ``caller`` field is the name of the innermost enclosing function-like node.
Anonymous arrows and function expressions without a bound variable → ``None``.
Module-level calls (outside any function) → ``None``.

Scope
-----
Every ``call_expression`` and ``new_expression`` at any nesting depth is
captured — including calls inside callbacks, IIFE bodies, JSX props, and
template expressions.

Public helpers
--------------
``build_call_graph(calls)`` transforms the flat extractor output into a
per-file grouped structure suitable for JSON serialisation::

    [
      {
        "file": "src/foo.ts",
        "functions": [
          {
            "name": "myFn" | null,
            "calls": [
              {"callee": "bar", "callee_object": null, "kind": "call", "line": 42}
            ]
          }
        ]
      }
    ]
"""

from __future__ import annotations

from tree_sitter import Tree

from aica.core.logging import get_logger

log = get_logger("repo.ast.extractors.calls")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FUNCTION_NODE_TYPES: frozenset[str] = frozenset({
    "function_declaration",
    "generator_function_declaration",
    "function_expression",
    "generator_function",
    "arrow_function",
    "method_definition",
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


def _extract_callee(func_node) -> tuple[str | None, str | None]:
    """Return ``(callee, callee_object)`` from the *function* or *constructor* child
    of a ``call_expression`` / ``new_expression``.

    - Plain identifier ``foo``       → ("foo", None)
    - Member expression ``obj.bar``  → ("bar", "obj")
    - Anything unresolvable          → (None, None) — skipped by caller
    """
    if func_node is None:
        return None, None

    if func_node.type == "identifier":
        return _decode(func_node), None

    if func_node.type == "member_expression":
        prop = func_node.child_by_field_name("property")
        obj = func_node.child_by_field_name("object")
        if prop is None:
            return None, None
        callee = _decode(prop)
        callee_object = _decode(obj) if obj is not None else None
        return callee, callee_object

    return None, None


# ---------------------------------------------------------------------------
# Public API — extractor
# ---------------------------------------------------------------------------


def extract(tree: Tree, source: str, file_path: str) -> list[dict]:
    """Extract all call sites from *tree*.

    Args:
        tree: Parsed tree-sitter :class:`~tree_sitter.Tree`.
        source: Original source string (accepted for API consistency, not used).
        file_path: POSIX-relative path of the source file — embedded in every
            output dict as ``"file"``.

    Returns:
        Flat list of call-site descriptor dicts; empty list when no calls found.
    """
    results: list[dict] = []
    seen: set[tuple[int, int]] = set()  # deduplicate by (row, col) start position

    for node in _walk(tree.root_node):
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            callee, callee_object = _extract_callee(func_node)
            kind = "call"
        elif node.type == "new_expression":
            ctor_node = node.child_by_field_name("constructor")
            callee, callee_object = _extract_callee(ctor_node)
            kind = "new"
        else:
            continue

        if callee is None:
            continue

        pos = (node.start_point[0], node.start_point[1])
        if pos in seen:
            continue
        seen.add(pos)

        caller = _enclosing_caller(node)
        line = node.start_point[0] + 1  # 1-based

        results.append({
            "file": file_path,
            "caller": caller,
            "callee": callee,
            "callee_object": callee_object,
            "kind": kind,
            "line": line,
        })

    log.debug(
        "repo.ast.extractors.calls.extracted",
        file=file_path,
        calls=len(results),
    )

    return results


# ---------------------------------------------------------------------------
# Public API — grouper
# ---------------------------------------------------------------------------


def build_call_graph(calls: list[dict]) -> list[dict]:
    """Transform a flat list of call-site records into a per-file grouped structure.

    The output groups entries by ``file``, then by ``caller`` (including
    ``None`` for module-level / anonymous calls).

    Args:
        calls: Flat list as returned by :func:`extract` (possibly merged from
            multiple files).

    Returns:
        List of ``{"file": ..., "functions": [...]}`` dicts, sorted
        alphabetically by file path.  Within each file, function groups are
        ordered: named callers first (alphabetically), ``null`` caller last.
    """
    # Phase 1: bucket by file → caller
    # structure: {file: {caller: [call_entry, ...]}}
    by_file: dict[str, dict[str | None, list[dict]]] = {}

    for entry in calls:
        file_key = entry["file"]
        caller = entry["caller"]  # may be None
        call_row = {
            "callee": entry["callee"],
            "callee_object": entry["callee_object"],
            "kind": entry["kind"],
            "line": entry["line"],
        }
        by_file.setdefault(file_key, {}).setdefault(caller, []).append(call_row)

    # Phase 2: serialise — sort files, sort callers (None last)
    result: list[dict] = []
    for file_key in sorted(by_file):
        caller_map = by_file[file_key]

        # Named callers first (alphabetical), None last
        named_callers = sorted(k for k in caller_map if k is not None)
        ordered_callers: list[str | None] = named_callers
        if None in caller_map:
            ordered_callers.append(None)

        functions_list = [
            {
                "name": caller,
                "calls": caller_map[caller],
            }
            for caller in ordered_callers
        ]

        result.append({
            "file": file_key,
            "functions": functions_list,
        })

    return result

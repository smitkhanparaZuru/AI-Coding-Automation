"""
Imports extractor — Task 3.2

Extracts all import statements from a tree-sitter TypeScript/TSX Tree.

Contract::

    extract(tree: Tree, source: str, file_path: str) -> list[dict]

Output schema per entry::

    {
        "file":        str,                             # POSIX-relative source path
        "source":      str,                             # module specifier, e.g. "react"
        "import_kind": "external" | "relative" | "alias",
        "default":     str | None,                      # default import binding
        "named":       list[{"name": str, "alias": str | None}],
        "namespace":   str | None,                      # * as X → "X"
        "type_only":   bool,                            # import type { ... }
        "side_effect": bool,                            # import './styles.css'
        "line":        int,                             # 1-based
    }

``import_kind`` rules
---------------------
- ``"relative"``  — specifier starts with ``./`` or ``../``
- ``"alias"``     — specifier starts with ``@`` or ``~`` (path-alias convention)
- ``"external"``  — everything else (npm package or bare specifier)
"""

from __future__ import annotations

from tree_sitter import Tree

from aica.core.logging import get_logger

log = get_logger("repo.ast.extractors.imports")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _walk(node):
    """Yield *node* and every descendant in depth-first order."""
    yield node
    for child in node.children:
        yield from _walk(child)


def _strip_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] in ('"', "'", "`") and text[-1] == text[0]:
        return text[1:-1]
    return text


def _classify_source(source: str) -> str:
    if source.startswith("./") or source.startswith("../"):
        return "relative"
    if source.startswith("@") or source.startswith("~"):
        return "alias"
    return "external"


def _decode(node) -> str:
    """Decode node bytes to str."""
    return node.text.decode("utf-8") if node is not None else ""


def _extract_named(named_imports_node) -> list[dict]:
    """Return ``[{"name": ..., "alias": ...}]`` for every ``import_specifier``."""
    result: list[dict] = []
    for child in named_imports_node.children:
        if child.type != "import_specifier":
            continue

        # Prefer tree-sitter named fields (most reliable)
        name_node = child.child_by_field_name("name")
        alias_node = child.child_by_field_name("alias")

        if name_node is None:
            # Fallback: collect all identifier children in order
            identifiers = [c for c in child.children if c.type == "identifier"]
            if not identifiers:
                continue
            name_node = identifiers[0]
            alias_node = identifiers[1] if len(identifiers) > 1 else None

        result.append({
            "name": _decode(name_node),
            "alias": _decode(alias_node) if alias_node is not None else None,
        })
    return result


def _extract_namespace(namespace_import_node) -> str | None:
    """Return the alias name from ``* as X``."""
    # Prefer named field
    alias_node = namespace_import_node.child_by_field_name("alias")
    if alias_node is not None:
        return _decode(alias_node)
    # Fallback: last identifier child
    identifiers = [c for c in namespace_import_node.children if c.type == "identifier"]
    return _decode(identifiers[-1]) if identifiers else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(tree: Tree, source: str, file_path: str) -> list[dict]:
    """Extract all import statements from *tree*.

    Args:
        tree: Parsed tree-sitter :class:`~tree_sitter.Tree`.
        source: Original source string (accepted for API consistency, not used).
        file_path: POSIX-relative path of the source file — embedded in every
            output dict as ``"file"``.

    Returns:
        List of import descriptor dicts; empty list when no imports found.
    """
    results: list[dict] = []

    for node in tree.root_node.children:
        if node.type != "import_statement":
            continue

        # ── type_only: `import type { ... }` ──────────────────────────────
        type_only = any(c.type == "type" for c in node.children)

        # ── module specifier ───────────────────────────────────────────────
        source_text = ""
        for child in node.children:
            if child.type == "string":
                source_text = _strip_quotes(_decode(child))
                break

        import_kind = _classify_source(source_text)

        # ── import_clause (None → side-effect import) ─────────────────────
        import_clause = next(
            (c for c in node.children if c.type == "import_clause"), None
        )

        if import_clause is None:
            results.append({
                "file": file_path,
                "source": source_text,
                "import_kind": import_kind,
                "default": None,
                "named": [],
                "namespace": None,
                "type_only": type_only,
                "side_effect": True,
                "line": node.start_point[0] + 1,
            })
            continue

        # ── parse clause contents ──────────────────────────────────────────
        default_name: str | None = None
        named: list[dict] = []
        namespace: str | None = None

        for child in import_clause.children:
            if child.type == "identifier":
                default_name = _decode(child)
            elif child.type == "named_imports":
                named = _extract_named(child)
            elif child.type == "namespace_import":
                namespace = _extract_namespace(child)

        results.append({
            "file": file_path,
            "source": source_text,
            "import_kind": import_kind,
            "default": default_name,
            "named": named,
            "namespace": namespace,
            "type_only": type_only,
            "side_effect": False,
            "line": node.start_point[0] + 1,
        })

    log.debug("imports.extracted", file=file_path, count=len(results))
    return results

"""
Tree-sitter parser for TypeScript and TSX source files.

This module is the entry point for all AST-based code analysis in AICA.
It provides two public functions:

    parse_code(code, lang)  — parse a source-code string
    parse_file(file_path)   — read + parse a file, auto-detecting the grammar

Grammar selection
-----------------
*.tsx files use the TSX grammar (which understands JSX syntax).
All other files (.ts, .d.ts, etc.) use the TypeScript grammar.

The underlying Language objects are built once and cached for the lifetime
of the process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import tree_sitter_typescript as _tst
from tree_sitter import Language, Parser, Tree


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=2)
def _get_language(name: str) -> Language:
    """Return a cached tree-sitter :class:`Language` for TypeScript or TSX.

    Args:
        name: ``"typescript"`` or ``"tsx"``.

    Returns:
        Compiled :class:`tree_sitter.Language` instance.
    """
    if name == "tsx":
        return Language(_tst.language_tsx())
    return Language(_tst.language_typescript())


def _lang_for_file(path: Path) -> str:
    """Derive the grammar name from a file's extension.

    Args:
        path: File path (only the suffix is examined).

    Returns:
        ``"tsx"`` for ``.tsx`` files, ``"typescript"`` for everything else.
    """
    return "tsx" if path.suffix.lower() == ".tsx" else "typescript"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_code(code: str, lang: str = "typescript") -> Tree:
    """Parse TypeScript or TSX source code and return the tree-sitter Tree.

    Args:
        code: Source code as a plain string.
        lang: Grammar to use — ``"typescript"`` (default) or ``"tsx"``.

    Returns:
        :class:`tree_sitter.Tree` with a ``root_node`` of type ``"program"``.

    Example::

        from aica.repo_intelligence.ast.parser import parse_code

        tree = parse_code("const x: number = 1;")
        print(tree.root_node.type)   # program
    """
    language = _get_language(lang)
    parser = Parser(language)
    return parser.parse(bytes(code, "utf-8"))


def parse_file(file_path: str | Path) -> Tree:
    """Parse a ``.ts`` or ``.tsx`` file and return the tree-sitter Tree.

    The correct grammar (TypeScript vs TSX) is selected automatically from
    the file extension — no need to pass ``lang`` explicitly.

    Args:
        file_path: Absolute or relative path to the TypeScript/TSX source
            file. Accepts both :class:`str` and :class:`pathlib.Path`.

    Returns:
        :class:`tree_sitter.Tree` with a ``root_node`` of type ``"program"``.

    Raises:
        FileNotFoundError: If *file_path* does not exist on disk.

    Example::

        from aica.repo_intelligence.ast.parser import parse_file

        tree = parse_file("src/components/Button.tsx")
        print(tree.root_node.type)   # program
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    code = path.read_text(encoding="utf-8")
    lang = _lang_for_file(path)
    return parse_code(code, lang)

"""
Tests for aica.repo_intelligence.ast.parser

Covers:
    parse_code() — TypeScript and TSX source strings
    parse_file() — .ts and .tsx temp files, string paths, missing files
    _lang_for_file() — extension-to-grammar mapping
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.ast.parser import _lang_for_file, parse_code, parse_file

# ---------------------------------------------------------------------------
# Sample source snippets
# ---------------------------------------------------------------------------

TS_SNIPPET = """\
const greet = (name: string): string => {
    return `Hello, ${name}!`;
};

function add(a: number, b: number): number {
    return a + b;
}

interface User {
    id: number;
    name: string;
}
"""

TSX_SNIPPET = """\
import React from 'react';

interface GreetingProps {
    name: string;
}

const Greeting: React.FC<GreetingProps> = ({ name }) => {
    return <div className="greeting">Hello, {name}!</div>;
};

export default Greeting;
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_node_type(node, target: str) -> bool:
    """Recursively search the AST for a node whose type contains *target*."""
    if target in node.type:
        return True
    return any(_find_node_type(child, target) for child in node.children)


def _has_error(node) -> bool:
    """Return True if the tree contains any ERROR or MISSING nodes."""
    if node.type in ("ERROR", "MISSING"):
        return True
    return any(_has_error(child) for child in node.children)


# ---------------------------------------------------------------------------
# parse_code — TypeScript
# ---------------------------------------------------------------------------


class TestParseCodeTypeScript:
    def test_returns_tree(self):
        tree = parse_code(TS_SNIPPET, lang="typescript")
        assert tree is not None

    def test_root_node_is_program(self):
        tree = parse_code(TS_SNIPPET, lang="typescript")
        assert tree.root_node.type == "program"

    def test_no_parse_errors(self):
        tree = parse_code(TS_SNIPPET, lang="typescript")
        assert not _has_error(tree.root_node)

    def test_default_lang_is_typescript(self):
        """Calling parse_code without lang= should default to TypeScript."""
        tree = parse_code(TS_SNIPPET)
        assert tree.root_node.type == "program"
        assert not _has_error(tree.root_node)

    def test_contains_function_node(self):
        tree = parse_code(TS_SNIPPET, lang="typescript")
        assert _find_node_type(tree.root_node, "function")

    def test_empty_file_is_valid(self):
        tree = parse_code("", lang="typescript")
        assert tree.root_node.type == "program"
        assert tree.root_node.child_count == 0


# ---------------------------------------------------------------------------
# parse_code — TSX
# ---------------------------------------------------------------------------


class TestParseCodeTSX:
    def test_returns_tree(self):
        tree = parse_code(TSX_SNIPPET, lang="tsx")
        assert tree is not None

    def test_root_node_is_program(self):
        tree = parse_code(TSX_SNIPPET, lang="tsx")
        assert tree.root_node.type == "program"

    def test_no_parse_errors(self):
        tree = parse_code(TSX_SNIPPET, lang="tsx")
        assert not _has_error(tree.root_node)

    def test_contains_jsx_element(self):
        """The TSX grammar must produce jsx_element nodes for JSX syntax."""
        tree = parse_code(TSX_SNIPPET, lang="tsx")
        assert _find_node_type(tree.root_node, "jsx"), (
            "Expected a jsx_element node in the TSX parse tree"
        )


# ---------------------------------------------------------------------------
# _lang_for_file — grammar selection logic
# ---------------------------------------------------------------------------


class TestLangForFile:
    def test_tsx_extension_returns_tsx(self):
        assert _lang_for_file(Path("Component.tsx")) == "tsx"

    def test_ts_extension_returns_typescript(self):
        assert _lang_for_file(Path("utils.ts")) == "typescript"

    def test_tsx_is_case_insensitive(self):
        assert _lang_for_file(Path("Component.TSX")) == "tsx"

    def test_other_extensions_return_typescript(self):
        # .d.ts, .mts, unknown — all fall back to TypeScript grammar
        for name in ("types.d.ts", "module.mts", "data.json"):
            assert _lang_for_file(Path(name)) == "typescript"


# ---------------------------------------------------------------------------
# parse_file — file-level parsing
# ---------------------------------------------------------------------------


class TestParseFile:
    def test_parse_ts_file(self, tmp_path: Path):
        ts_file = tmp_path / "sample.ts"
        ts_file.write_text(TS_SNIPPET, encoding="utf-8")

        tree = parse_file(ts_file)
        assert tree.root_node.type == "program"
        assert not _has_error(tree.root_node)

    def test_parse_tsx_file(self, tmp_path: Path):
        tsx_file = tmp_path / "Greeting.tsx"
        tsx_file.write_text(TSX_SNIPPET, encoding="utf-8")

        tree = parse_file(tsx_file)
        assert tree.root_node.type == "program"
        assert not _has_error(tree.root_node)

    def test_tsx_auto_detects_jsx_grammar(self, tmp_path: Path):
        """parse_file on a .tsx file must route to the TSX grammar."""
        tsx_file = tmp_path / "Greeting.tsx"
        tsx_file.write_text(TSX_SNIPPET, encoding="utf-8")

        tree = parse_file(tsx_file)
        assert _find_node_type(tree.root_node, "jsx"), (
            ".tsx file should be parsed with the TSX grammar (jsx nodes expected)"
        )

    def test_accepts_string_path(self, tmp_path: Path):
        ts_file = tmp_path / "sample.ts"
        ts_file.write_text(TS_SNIPPET, encoding="utf-8")

        # Pass str, not Path
        tree = parse_file(str(ts_file))
        assert tree.root_node.type == "program"

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_file("this_file_absolutely_does_not_exist_aica.ts")

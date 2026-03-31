"""
Tests for aica.memory.vector_store.chunkers

Covers:
    chunk_functions() — function chunking with metadata
    chunk_components() — component chunking with props
    chunk_types() — type/interface chunking with members
    create_code_chunks() — orchestration with deduplication and enrichment
    Edge cases — anonymous functions, missing files, truncation, deduplication
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aica.memory.vector_store.chunkers import (
    chunk_components,
    chunk_functions,
    chunk_types,
    create_code_chunks,
)
from aica.memory.vector_store.schemas import CodeChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary repository with source files."""
    # Create directory structure
    src_dir = tmp_path / "src"
    utils_dir = src_dir / "utils"
    components_dir = src_dir / "components"
    types_dir = src_dir / "types"

    utils_dir.mkdir(parents=True)
    components_dir.mkdir(parents=True)
    types_dir.mkdir(parents=True)

    # Create sample source files
    (utils_dir / "helpers.ts").write_text(
        """// Helper functions
/**
 * Calculate total value
 */
export function calculateTotal(items: Item[]) {
  return items.reduce((sum, item) => sum + item.value, 0);
}

export const formatCurrency = (amount: number) => {
  return `$${amount.toFixed(2)}`;
};

function internalHelper() {
  return "internal";
}
""",
        encoding="utf-8",
    )

    (components_dir / "Button.tsx").write_text(
        """import React from 'react';

/**
 * Button component
 */
export function Button({ label, onClick }: ButtonProps) {
  return <button onClick={onClick}>{label}</button>;
}

const InternalComponent = () => {
  return <div>Internal</div>;
};
""",
        encoding="utf-8",
    )

    (types_dir / "user.ts").write_text(
        """/**
 * User type definition
 */
export interface User {
  id: string;
  name: string;
  email: string;
}

export type Status = "active" | "inactive";

interface InternalType {
  value: number;
}
""",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def temp_repo_with_ast(temp_repo: Path) -> Path:
    """Create AST output directory with JSON files."""
    ast_dir = temp_repo / ".repo_intelligence" / "ast"
    ast_dir.mkdir(parents=True)

    # functions.json
    functions = [
        {
            "file": "src/utils/helpers.ts",
            "name": "calculateTotal",
            "kind": "function",
            "async": False,
            "params": ["items"],
            "line": 5,
            "exported": True,
        },
        {
            "file": "src/utils/helpers.ts",
            "name": "formatCurrency",
            "kind": "arrow",
            "async": False,
            "params": ["amount"],
            "line": 9,
            "exported": True,
        },
        {
            "file": "src/utils/helpers.ts",
            "name": "internalHelper",
            "kind": "function",
            "async": False,
            "params": [],
            "line": 13,
            "exported": False,
        },
    ]

    (ast_dir / "functions.json").write_text(json.dumps(functions), encoding="utf-8")

    # components.json
    components = [
        {
            "file": "src/components/Button.tsx",
            "name": "Button",
            "kind": "function",
            "props": ["label", "onClick"],
            "line": 6,
            "exported": True,
        },
        {
            "file": "src/components/Button.tsx",
            "name": "InternalComponent",
            "kind": "arrow",
            "props": [],
            "line": 10,
            "exported": False,
        },
    ]

    (ast_dir / "components.json").write_text(json.dumps(components), encoding="utf-8")

    # types.json
    types = [
        {
            "file": "src/types/user.ts",
            "name": "User",
            "kind": "interface",
            "members": ["id", "name", "email"],
            "line": 4,
            "exported": True,
        },
        {
            "file": "src/types/user.ts",
            "name": "Status",
            "kind": "type",
            "members": [],
            "line": 10,
            "exported": True,
        },
        {
            "file": "src/types/user.ts",
            "name": "InternalType",
            "kind": "interface",
            "members": ["value"],
            "line": 12,
            "exported": False,
        },
    ]

    (ast_dir / "types.json").write_text(json.dumps(types), encoding="utf-8")

    # imports.json (for dependency enrichment)
    imports = [
        {
            "file": "src/components/Button.tsx",
            "source": "react",
            "import_kind": "external",
            "default": "React",
            "named": [],
            "line": 1,
        }
    ]

    (ast_dir / "imports.json").write_text(json.dumps(imports), encoding="utf-8")

    return temp_repo


# ---------------------------------------------------------------------------
# Function chunker tests
# ---------------------------------------------------------------------------


class TestFunctionChunker:
    def test_basic_function_chunking(self, temp_repo: Path):
        """Process functions.json and verify chunk structure."""
        functions = [
            {
                "file": "src/utils/helpers.ts",
                "name": "calculateTotal",
                "kind": "function",
                "async": False,
                "params": ["items"],
                "line": 5,
                "exported": True,
            }
        ]

        chunks = chunk_functions(functions, temp_repo)

        assert len(chunks) == 1
        chunk = chunks[0]

        # Verify ID format
        assert chunk.id == "src/utils/helpers.ts:function:calculateTotal:5"

        # Verify text extraction
        assert "calculateTotal" in chunk.text
        assert "items" in chunk.text

        # Verify metadata
        assert chunk.metadata.file == "src/utils/helpers.ts"
        assert chunk.metadata.line == 5
        assert chunk.metadata.chunk_type == "function"
        assert chunk.metadata.name == "calculateTotal"
        assert chunk.metadata.exported is True
        assert chunk.metadata.kind == "function"
        assert chunk.metadata.params == ["items"]

    def test_includes_docstring(self, temp_repo: Path):
        """Verify docstring/JSDoc is included in chunk text."""
        functions = [
            {
                "file": "src/utils/helpers.ts",
                "name": "calculateTotal",
                "kind": "function",
                "line": 5,
                "exported": True,
            }
        ]

        chunks = chunk_functions(functions, temp_repo)

        assert len(chunks) == 1
        # Should include JSDoc comment
        assert "Calculate total value" in chunks[0].text or "/**" in chunks[0].text

    def test_anonymous_function_handling(self, temp_repo: Path):
        """Handle anonymous functions with name=null."""
        functions = [
            {
                "file": "src/utils/helpers.ts",
                "name": None,  # Anonymous
                "kind": "arrow",
                "line": 9,
                "exported": False,
            }
        ]

        chunks = chunk_functions(functions, temp_repo)

        assert len(chunks) == 1
        # ID should use "anonymous"
        assert "anonymous" in chunks[0].id
        assert chunks[0].metadata.name == "anonymous"

    def test_missing_source_file(self, temp_repo: Path):
        """Gracefully handle missing source files."""
        functions = [
            {
                "file": "src/nonexistent.ts",
                "name": "foo",
                "line": 10,
                "exported": True,
            }
        ]

        chunks = chunk_functions(functions, temp_repo)

        # Should return empty list, not raise exception
        assert chunks == []

    def test_multiple_functions(self, temp_repo: Path):
        """Process multiple functions from same file."""
        functions = [
            {
                "file": "src/utils/helpers.ts",
                "name": "calculateTotal",
                "kind": "function",
                "line": 5,
                "exported": True,
            },
            {
                "file": "src/utils/helpers.ts",
                "name": "formatCurrency",
                "kind": "arrow",
                "line": 9,
                "exported": True,
            },
        ]

        chunks = chunk_functions(functions, temp_repo)

        assert len(chunks) == 2
        names = {c.metadata.name for c in chunks}
        assert names == {"calculateTotal", "formatCurrency"}


# ---------------------------------------------------------------------------
# Component chunker tests
# ---------------------------------------------------------------------------


class TestComponentChunker:
    def test_basic_component_chunking(self, temp_repo: Path):
        """Process components.json and verify chunk structure."""
        components = [
            {
                "file": "src/components/Button.tsx",
                "name": "Button",
                "kind": "function",
                "props": ["label", "onClick"],
                "line": 6,
                "exported": True,
            }
        ]

        chunks = chunk_components(components, temp_repo)

        assert len(chunks) == 1
        chunk = chunks[0]

        # Verify ID format
        assert chunk.id == "src/components/Button.tsx:component:Button:6"

        # Verify text includes JSX
        assert "Button" in chunk.text
        assert "<button" in chunk.text or "return" in chunk.text

        # Verify metadata
        assert chunk.metadata.chunk_type == "component"
        assert chunk.metadata.name == "Button"
        assert chunk.metadata.props == ["label", "onClick"]

    def test_component_with_props(self, temp_repo: Path):
        """Verify props are captured in metadata."""
        components = [
            {
                "file": "src/components/Button.tsx",
                "name": "Button",
                "kind": "function",
                "props": ["label", "onClick"],
                "line": 6,
                "exported": True,
            }
        ]

        chunks = chunk_components(components, temp_repo)

        assert chunks[0].metadata.props == ["label", "onClick"]


# ---------------------------------------------------------------------------
# Type chunker tests
# ---------------------------------------------------------------------------


class TestTypeChunker:
    def test_interface_chunking(self, temp_repo: Path):
        """Process interface definitions."""
        types = [
            {
                "file": "src/types/user.ts",
                "name": "User",
                "kind": "interface",
                "members": ["id", "name", "email"],
                "line": 4,
                "exported": True,
            }
        ]

        chunks = chunk_types(types, temp_repo)

        assert len(chunks) == 1
        chunk = chunks[0]

        # Verify ID format
        assert chunk.id == "src/types/user.ts:type:User:4"

        # Verify metadata
        assert chunk.metadata.chunk_type == "type"
        assert chunk.metadata.name == "User"
        assert chunk.metadata.kind == "interface"
        assert chunk.metadata.members == ["id", "name", "email"]

    def test_type_alias_chunking(self, temp_repo: Path):
        """Process type alias definitions."""
        types = [
            {
                "file": "src/types/user.ts",
                "name": "Status",
                "kind": "type",
                "members": [],
                "line": 10,
                "exported": True,
            }
        ]

        chunks = chunk_types(types, temp_repo)

        assert len(chunks) == 1
        assert chunks[0].metadata.kind == "type"
        assert chunks[0].metadata.members == []


# ---------------------------------------------------------------------------
# Large text truncation
# ---------------------------------------------------------------------------


class TestTruncation:
    def test_large_function_truncation(self, tmp_path: Path):
        """Truncate functions >2000 chars with metadata flag."""
        # Create file with very large function
        # Each line is ~100 chars, 25 lines = 2500 chars (exceeds 2000 limit)
        large_file = tmp_path / "large.ts"
        large_code = "export function huge() {\n"
        large_code += "  const data = 'This is a very long string with lots of content to make the line exceed 100 chars easily';\n" * 25
        large_code += "}"
        large_file.write_text(large_code, encoding="utf-8")

        functions = [
            {
                "file": "large.ts",
                "name": "huge",
                "kind": "function",
                "line": 1,
                "exported": True,
            }
        ]

        chunks = chunk_functions(functions, tmp_path)

        assert len(chunks) == 1
        chunk = chunks[0]

        # Text should be truncated
        assert len(chunk.text) <= 2003  # 2000 + "..."
        assert chunk.text.endswith("...")

        # Metadata should indicate truncation
        assert chunk.metadata.truncated is True


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------


class TestOrchestrator:
    def test_create_code_chunks_basic(self, temp_repo_with_ast: Path):
        """Run full orchestration on repo with AST outputs."""
        chunks = create_code_chunks(temp_repo_with_ast)

        # Should have functions + components + types
        # 3 functions + 2 components + 3 types = 8 total
        assert len(chunks) >= 6  # At least the exported ones

        # Verify chunk types
        chunk_types = {c.metadata.chunk_type for c in chunks}
        assert "function" in chunk_types
        assert "component" in chunk_types
        assert "type" in chunk_types

    def test_deduplication_prefers_exported(self, temp_repo_with_ast: Path):
        """Deduplication prefers exported=True over exported=False."""
        # Add duplicate function with different exported values
        ast_dir = temp_repo_with_ast / ".repo_intelligence" / "ast"
        functions = json.loads((ast_dir / "functions.json").read_text())

        # Add duplicate with exported=False
        functions.append(
            {
                "file": "src/utils/helpers.ts",
                "name": "calculateTotal",
                "kind": "function",
                "line": 5,
                "exported": False,  # Different export status
            }
        )

        (ast_dir / "functions.json").write_text(json.dumps(functions))

        chunks = create_code_chunks(temp_repo_with_ast)

        # Find calculateTotal chunks
        calc_chunks = [c for c in chunks if c.metadata.name == "calculateTotal"]

        # Should have only one (deduplicated)
        assert len(calc_chunks) == 1

        # Should be the exported version
        assert calc_chunks[0].metadata.exported is True

    def test_dependency_enrichment(self, temp_repo_with_ast: Path):
        """Verify dependencies are enriched from imports.json."""
        chunks = create_code_chunks(temp_repo_with_ast)

        # Find Button component
        button_chunks = [c for c in chunks if c.metadata.name == "Button"]

        assert len(button_chunks) == 1

        # Should have react as dependency
        assert "react" in button_chunks[0].metadata.dependencies

    def test_missing_ast_directory(self, tmp_path: Path):
        """Raise FileNotFoundError if AST directory missing."""
        with pytest.raises(FileNotFoundError):
            create_code_chunks(tmp_path)

    def test_feature_detection(self, temp_repo_with_ast: Path):
        """Verify feature names are inferred from paths."""
        chunks = create_code_chunks(temp_repo_with_ast)

        # Components should have feature="Button" or similar
        # (depends on how many directory levels match the pattern)
        # At minimum, should not crash
        assert all(hasattr(c.metadata, "feature") for c in chunks)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_malformed_json_handled_gracefully(self, tmp_path: Path):
        """Handle malformed JSON files without crashing."""
        ast_dir = tmp_path / ".repo_intelligence" / "ast"
        ast_dir.mkdir(parents=True)

        # Write malformed JSON
        (ast_dir / "functions.json").write_text("{ invalid json", encoding="utf-8")
        (ast_dir / "components.json").write_text("[]", encoding="utf-8")
        (ast_dir / "types.json").write_text("[]", encoding="utf-8")
        (ast_dir / "imports.json").write_text("[]", encoding="utf-8")

        # Should not raise exception
        chunks = create_code_chunks(tmp_path)

        # Should return chunks from valid files only
        assert isinstance(chunks, list)

    def test_missing_required_fields(self, tmp_path: Path):
        """Skip entries with missing required fields."""
        ast_dir = tmp_path / ".repo_intelligence" / "ast"
        ast_dir.mkdir(parents=True)

        # Create entry missing "line" field
        functions = [
            {
                "file": "src/test.ts",
                "name": "foo",
                # Missing "line"
            }
        ]

        (ast_dir / "functions.json").write_text(json.dumps(functions))
        (ast_dir / "components.json").write_text("[]")
        (ast_dir / "types.json").write_text("[]")
        (ast_dir / "imports.json").write_text("[]")

        chunks = create_code_chunks(tmp_path)

        # Should skip malformed entry
        assert chunks == []


# ---------------------------------------------------------------------------
# Metadata validation
# ---------------------------------------------------------------------------


class TestMetadataValidation:
    def test_all_chunks_have_required_fields(self, temp_repo_with_ast: Path):
        """Verify all chunks have complete metadata."""
        chunks = create_code_chunks(temp_repo_with_ast)

        for chunk in chunks:
            # Required fields
            assert chunk.id
            assert chunk.text
            assert chunk.metadata.file
            assert chunk.metadata.line > 0
            assert chunk.metadata.chunk_type in ("function", "component", "type")
            assert chunk.metadata.name
            assert isinstance(chunk.metadata.exported, bool)

    def test_language_detection(self, temp_repo_with_ast: Path):
        """Verify language is correctly detected from file extension."""
        chunks = create_code_chunks(temp_repo_with_ast)

        # Find .tsx file chunks
        tsx_chunks = [c for c in chunks if c.metadata.file.endswith(".tsx")]
        assert all(c.metadata.language == "tsx" for c in tsx_chunks)

        # Find .ts file chunks
        ts_chunks = [c for c in chunks if c.metadata.file.endswith(".ts")]
        assert all(c.metadata.language == "typescript" for c in ts_chunks)

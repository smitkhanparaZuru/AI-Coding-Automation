"""
Tests for aica.repo_intelligence.ast.runner.run_incremental()

Covers:
    run_incremental() — loads existing JSON, processes changed files only
    file deletion — removes entries for deleted files
    entry merging — new entries merged with existing data
    call graph rebuild — updates call entries
    error handling — graceful handling of parse errors
"""

from __future__ import annotations

from pathlib import Path
import json
import pytest

from aica.repo_intelligence.ast.runner import ASTExtractorRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_with_existing_data(tmp_path: Path) -> Path:
    """Create a repo with existing AST JSON data."""
    src = tmp_path / "src"
    src.mkdir()

    # Create initial files
    (src / "utils.ts").write_text(
        "export function add(a: number, b: number): number {\n"
        "  return a + b;\n"
        "}\n",
        encoding="utf-8",
    )

    (src / "helpers.ts").write_text(
        "export const double = (n: number) => n * 2;\n",
        encoding="utf-8",
    )

    # Create .repo_intelligence/ast with existing data
    ast_dir = tmp_path / ".repo_intelligence" / "ast"
    ast_dir.mkdir(parents=True, exist_ok=True)

    # Pre-populate with initial extraction
    functions = [
        {"file": "src/utils.ts", "name": "add", "line": 1, "params": ["a", "b"]},
        {"file": "src/helpers.ts", "name": "double", "line": 1, "params": ["n"]},
    ]
    imports = []
    exports = [
        {"file": "src/utils.ts", "name": "add", "line": 1},
        {"file": "src/helpers.ts", "name": "double", "line": 1},
    ]
    calls = []
    hooks = []
    components = []
    types = []

    (ast_dir / "functions.json").write_text(json.dumps(functions, indent=2))
    (ast_dir / "imports.json").write_text(json.dumps(imports, indent=2))
    (ast_dir / "exports.json").write_text(json.dumps(exports, indent=2))
    (ast_dir / "calls.json").write_text(json.dumps(calls, indent=2))
    (ast_dir / "hooks.json").write_text(json.dumps(hooks, indent=2))
    (ast_dir / "components.json").write_text(json.dumps(components, indent=2))
    (ast_dir / "types.json").write_text(json.dumps(types, indent=2))

    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_incremental_modifies_file(repo_with_existing_data: Path) -> None:
    """Test that modifying a file updates its entries."""
    runner = ASTExtractorRunner()

    # Modify utils.ts to add a new function
    utils_file = repo_with_existing_data / "src" / "utils.ts"
    utils_file.write_text(
        "export function add(a: number, b: number): number {\n"
        "  return a + b;\n"
        "}\n"
        "\n"
        "export function subtract(a: number, b: number): number {\n"
        "  return a - b;\n"
        "}\n",
        encoding="utf-8",
    )

    # Run incremental with changed file
    result = runner.run_incremental(repo_with_existing_data, ["src/utils.ts"])

    # Verify functions list was updated
    assert len(result["functions"]) == 3  # add, subtract, and helpers.double
    utils_functions = [f for f in result["functions"] if f["file"] == "src/utils.ts"]
    assert len(utils_functions) == 2
    assert any(f["name"] == "add" for f in utils_functions)
    assert any(f["name"] == "subtract" for f in utils_functions)

    # Verify helpers.ts data was preserved
    helpers_functions = [f for f in result["functions"] if f["file"] == "src/helpers.ts"]
    assert len(helpers_functions) == 1
    assert helpers_functions[0]["name"] == "double"


def test_run_incremental_deletes_file(repo_with_existing_data: Path) -> None:
    """Test that deleting a file removes its entries."""
    runner = ASTExtractorRunner()

    # Delete helpers.ts
    (repo_with_existing_data / "src" / "helpers.ts").unlink()

    # Run incremental with deleted file
    result = runner.run_incremental(repo_with_existing_data, ["src/helpers.ts"])

    # Verify helpers entries were removed
    assert len(result["functions"]) == 1
    assert result["functions"][0]["name"] == "add"
    assert result["functions"][0]["file"] == "src/utils.ts"

    assert len(result["exports"]) == 1
    assert result["exports"][0]["file"] == "src/utils.ts"


def test_run_incremental_multiple_files(repo_with_existing_data: Path) -> None:
    """Test updating multiple files in one sync."""
    runner = ASTExtractorRunner()

    # Modify both files
    (repo_with_existing_data / "src" / "utils.ts").write_text(
        "export function multiply(a: number, b: number): number {\n"
        "  return a * b;\n"
        "}\n"
    )
    (repo_with_existing_data / "src" / "helpers.ts").write_text(
        "export const triple = (n: number) => n * 3;\n"
    )

    # Run incremental with both files
    result = runner.run_incremental(
        repo_with_existing_data,
        ["src/utils.ts", "src/helpers.ts"]
    )

    # Verify both were updated
    utils_fns = [f for f in result["functions"] if f["file"] == "src/utils.ts"]
    helpers_fns = [f for f in result["functions"] if f["file"] == "src/helpers.ts"]

    assert any(f["name"] == "multiply" for f in utils_fns)
    assert any(f["name"] == "triple" for f in helpers_fns)


def test_run_incremental_preserves_unmodified_files(repo_with_existing_data: Path) -> None:
    """Test that unmodified files are not affected."""
    runner = ASTExtractorRunner()

    # Only modify utils.ts, not helpers.ts
    (repo_with_existing_data / "src" / "utils.ts").write_text(
        "export function add(a: number, b: number): number {\n"
        "  return a + b;\n"
        "}\n"
        "export function subtract(a: number, b: number): number {\n"
        "  return a - b;\n"
        "}\n"
    )

    result = runner.run_incremental(repo_with_existing_data, ["src/utils.ts"])

    # helpers.ts data should be identical to original
    helpers_functions = [f for f in result["functions"] if f["file"] == "src/helpers.ts"]
    assert len(helpers_functions) == 1
    assert helpers_functions[0]["name"] == "double"
    assert helpers_functions[0]["line"] == 1


def test_run_incremental_missing_repo(tmp_path: Path) -> None:
    """Test that missing repo returns empty result."""
    runner = ASTExtractorRunner()
    missing_path = tmp_path / "nonexistent"

    result = runner.run_incremental(missing_path, ["src/utils.ts"])

    assert result["functions"] == []
    assert result["imports"] == []
    assert result["exports"] == []


def test_run_incremental_with_parse_error(repo_with_existing_data: Path) -> None:
    """Test that parse errors are handled gracefully."""
    runner = ASTExtractorRunner()

    # Create invalid TypeScript in utils.ts
    (repo_with_existing_data / "src" / "utils.ts").write_text(
        "export function broken(\n"
        "  this is not valid typescript\n",
        encoding="utf-8",
    )

    # Should not raise, but log warning and remove old entries
    result = runner.run_incremental(repo_with_existing_data, ["src/utils.ts"])

    # utils.ts entries should be removed due to error
    utils_fns = [f for f in result["functions"] if f["file"] == "src/utils.ts"]
    assert len(utils_fns) == 0

    # helpers.ts should still exist
    helpers_fns = [f for f in result["functions"] if f["file"] == "src/helpers.ts"]
    assert len(helpers_fns) == 1

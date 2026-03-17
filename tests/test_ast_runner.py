"""
Tests for aica.repo_intelligence.ast.runner (ASTExtractorRunner)

Covers:
    run() — returns {"imports": list, "functions": list}
    file discovery — .ts and .tsx are both scanned
    exclusion — node_modules and other excluded dirs are skipped
    missing repo — graceful empty result
    file field — every record carries the correct POSIX-relative "file"
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.ast.runner import ASTExtractorRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_repo(tmp_path: Path) -> Path:
    """A minimal "repository" with two .ts files and one .tsx file."""
    src = tmp_path / "src"
    src.mkdir()

    # utils.ts — one named function, one named import
    (src / "utils.ts").write_text(
        "import { something } from 'lib';\n"
        "export function add(a: number, b: number): number {\n"
        "  return a + b;\n"
        "}\n",
        encoding="utf-8",
    )

    # helpers.ts — one arrow function, no imports
    (src / "helpers.ts").write_text(
        "export const double = (n: number) => n * 2;\n",
        encoding="utf-8",
    )

    # Button.tsx — one import, one arrow component
    (src / "Button.tsx").write_text(
        "import React from 'react';\n"
        "export const Button = () => <button>Click</button>;\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def repo_with_exclusions(tmp_path: Path) -> Path:
    """A repo where node_modules should be excluded."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function main() {}\n", encoding="utf-8")

    # node_modules — must be excluded
    nm = tmp_path / "node_modules" / "some-pkg"
    nm.mkdir(parents=True)
    (nm / "index.ts").write_text(
        "export function shouldBeIgnored() {}\n", encoding="utf-8"
    )

    # .next — must be excluded
    dot_next = tmp_path / ".next"
    dot_next.mkdir()
    (dot_next / "server.ts").write_text(
        "export function alsoIgnored() {}\n", encoding="utf-8"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Return value shape
# ---------------------------------------------------------------------------


class TestRunnerReturnShape:
    def test_returns_dict_with_imports_and_functions(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        assert isinstance(result, dict)
        assert "imports" in result
        assert "functions" in result

    def test_exports_key_present(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        assert "exports" in result

    def test_calls_key_present(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        assert "calls" in result

    def test_imports_is_list(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        assert isinstance(result["imports"], list)

    def test_functions_is_list(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        assert isinstance(result["functions"], list)

    def test_exports_is_list(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        assert isinstance(result["exports"], list)

    def test_calls_is_list(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        assert isinstance(result["calls"], list)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


class TestFileDiscovery:
    def test_ts_files_are_scanned(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        files = {e["file"] for e in result["functions"]}
        assert any("utils.ts" in f for f in files)
        assert any("helpers.ts" in f for f in files)

    def test_tsx_files_are_scanned(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        files = {e["file"] for e in result["functions"]}
        assert any("Button.tsx" in f for f in files)

    def test_correct_import_count(self, simple_repo: Path):
        """utils.ts has 1 import, Button.tsx has 1 import → total 2."""
        result = ASTExtractorRunner().run(simple_repo)
        assert len(result["imports"]) == 2

    def test_correct_function_count(self, simple_repo: Path):
        """utils.ts: 1 func decl; helpers.ts: 1 arrow; Button.tsx: 1 arrow → ≥ 3."""
        result = ASTExtractorRunner().run(simple_repo)
        assert len(result["functions"]) >= 3


# ---------------------------------------------------------------------------
# Directory exclusion
# ---------------------------------------------------------------------------


class TestExclusion:
    def test_node_modules_excluded(self, repo_with_exclusions: Path):
        result = ASTExtractorRunner().run(repo_with_exclusions)
        files = {e["file"] for e in result["functions"]}
        assert not any("node_modules" in f for f in files)

    def test_dot_next_excluded(self, repo_with_exclusions: Path):
        result = ASTExtractorRunner().run(repo_with_exclusions)
        files = {e["file"] for e in result["functions"]}
        assert not any(".next" in f for f in files)

    def test_src_files_not_excluded(self, repo_with_exclusions: Path):
        result = ASTExtractorRunner().run(repo_with_exclusions)
        files = {e["file"] for e in result["functions"]}
        assert any("app.ts" in f for f in files)


# ---------------------------------------------------------------------------
# Missing repository
# ---------------------------------------------------------------------------


class TestMissingRepo:
    def test_nonexistent_path_returns_empty(self, tmp_path: Path):
        bad_path = tmp_path / "does_not_exist"
        result = ASTExtractorRunner().run(bad_path)
        assert result == {
            "imports": [],
            "functions": [],
            "exports": [],
            "calls": [],
            "hooks": [],
            "components": [],
            "types": [],
        }


# ---------------------------------------------------------------------------
# file field in records
# ---------------------------------------------------------------------------


class TestFileField:
    def test_all_imports_have_file_field(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        for entry in result["imports"]:
            assert "file" in entry
            assert isinstance(entry["file"], str)

    def test_all_functions_have_file_field(self, simple_repo: Path):
        result = ASTExtractorRunner().run(simple_repo)
        for entry in result["functions"]:
            assert "file" in entry
            assert isinstance(entry["file"], str)

    def test_file_field_is_posix_relative(self, simple_repo: Path):
        """Paths must be relative (no leading /) and use forward slashes."""
        result = ASTExtractorRunner().run(simple_repo)
        for entry in result["imports"] + result["functions"]:
            path = entry["file"]
            assert not path.startswith("/")
            assert "\\" not in path


# ---------------------------------------------------------------------------
# Empty repository
# ---------------------------------------------------------------------------


class TestEmptyRepo:
    def test_empty_dir_returns_empty_lists(self, tmp_path: Path):
        result = ASTExtractorRunner().run(tmp_path)
        assert result["imports"] == []
        assert result["functions"] == []
        assert result["calls"] == []

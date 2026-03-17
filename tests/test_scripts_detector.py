from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.scripts import ScriptsDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def scripts_repo(tmp_path: Path) -> Path:
    """Repo with a scripts/ directory containing a dir entry and a plain file."""
    scripts_dir = tmp_path / "scripts"

    # Subdirectory-based script
    migrate_dir = scripts_dir / "migrateServerDB"
    migrate_dir.mkdir(parents=True)
    (migrate_dir / "index.ts").write_text("// migrate\n", encoding="utf-8")
    (migrate_dir / "docker.cjs").write_text("// docker\n", encoding="utf-8")
    (migrate_dir / "errorHint.js").write_text("// hint\n", encoding="utf-8")

    # Plain file script
    (scripts_dir / "countEnWord.ts").write_text("// count\n", encoding="utf-8")

    # Hidden file should be ignored
    (scripts_dir / ".DS_Store").write_text("", encoding="utf-8")

    return tmp_path


@pytest.fixture()
def empty_scripts_repo(tmp_path: Path) -> Path:
    """Repo without a scripts directory."""
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detects_dir_entry(scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(scripts_repo)
    names = {r["name"] for r in results}
    assert "migrateServerDB" in names


def test_detects_file_entry(scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(scripts_repo)
    names = {r["name"] for r in results}
    assert "countEnWord" in names


def test_dir_entry_type(scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(scripts_repo)
    migrate = next(r for r in results if r["name"] == "migrateServerDB")
    assert migrate["type"] == "dir"


def test_file_entry_type(scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(scripts_repo)
    count = next(r for r in results if r["name"] == "countEnWord")
    assert count["type"] == "file"


def test_dir_files_listed(scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(scripts_repo)
    migrate = next(r for r in results if r["name"] == "migrateServerDB")
    assert set(migrate["files"]) == {"index.ts", "docker.cjs", "errorHint.js"}


def test_file_entry_has_empty_files(scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(scripts_repo)
    count = next(r for r in results if r["name"] == "countEnWord")
    assert count["files"] == []


def test_path_is_relative(scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(scripts_repo)
    migrate = next(r for r in results if r["name"] == "migrateServerDB")
    assert migrate["path"] == "scripts/migrateServerDB"


def test_hidden_files_excluded(scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(scripts_repo)
    names = {r["name"] for r in results}
    assert ".DS_Store" not in names


def test_no_scripts_dir_returns_empty(empty_scripts_repo: Path) -> None:
    results = ScriptsDetector().detect(empty_scripts_repo)
    assert results == []

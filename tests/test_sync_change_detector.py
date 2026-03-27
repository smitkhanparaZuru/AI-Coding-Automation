from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from aica.execution.runner import RunResult
from aica.repo_intelligence.sync import (
    GitNotFoundError,
    NoChangesError,
    NotAGitRepositoryError,
    detect_real_changes,
    detect_repository_changes,
    get_changed_files,
    get_file_hash,
    load_cached_hashes,
    save_hashes,
)


def _run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        check=True,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    try:
        _run_git(tmp_path, "init")
    except FileNotFoundError:
        pytest.skip("git is not available in the test environment")

    _run_git(tmp_path, "config", "user.name", "AICA Tests")
    _run_git(tmp_path, "config", "user.email", "aica-tests@example.com")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.ts").write_text("export const answer = 42;\n", encoding="utf-8")
    (src_dir / "component.tsx").write_text(
        "export function Component() { return null; }\n",
        encoding="utf-8",
    )
    (src_dir / "notes.md").write_text("ignore me\n", encoding="utf-8")

    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "Initial commit")
    return tmp_path


def test_get_file_hash_changes_when_file_content_changes(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.ts"
    sample_file.write_text("export const x = 1;\n", encoding="utf-8")
    first_hash = get_file_hash(sample_file)

    sample_file.write_text("export const x = 2;\n", encoding="utf-8")
    second_hash = get_file_hash(sample_file)

    assert first_hash != second_hash


def test_save_and_load_cached_hashes_round_trip(tmp_path: Path) -> None:
    hashes = {"src/app.ts": "abc123", "src/component.tsx": "def456", "README.md": "skip"}

    save_hashes(tmp_path, hashes)
    loaded = load_cached_hashes(tmp_path)

    assert loaded == {
        "src/app.ts": "abc123",
        "src/component.tsx": "def456",
    }


def test_detect_real_changes_uses_cached_hashes(git_repo: Path) -> None:
    file_path = git_repo / "src" / "app.ts"
    unchanged_hash = get_file_hash(file_path)
    cached_hashes = {
        "src/app.ts": unchanged_hash,
        "src/component.tsx": "stale-hash",
    }

    real_changes = detect_real_changes(
        ["src/app.ts", "src/component.tsx"],
        cached_hashes,
        repo_path=git_repo,
    )

    assert real_changes == ["src/component.tsx"]


def test_get_changed_files_filters_to_typescript(git_repo: Path) -> None:
    (git_repo / "src" / "app.ts").write_text("export const answer = 43;\n", encoding="utf-8")
    (git_repo / "src" / "notes.md").write_text("still ignore me\n", encoding="utf-8")

    changed_files = get_changed_files(git_repo)

    assert changed_files == ["src/app.ts"]


def test_detect_repository_changes_tracks_real_changes_and_cache(git_repo: Path) -> None:
    (git_repo / "src" / "component.tsx").write_text(
        "export function Component() { return <div />; }\n",
        encoding="utf-8",
    )

    result = detect_repository_changes(git_repo)
    cached_hashes = load_cached_hashes(git_repo)

    assert result.changed_files == ["src/component.tsx"]
    assert result.real_changed_files == ["src/component.tsx"]
    assert result.deleted_files == []
    assert result.cache_path.is_file()
    assert "src/component.tsx" in cached_hashes


def test_detect_repository_changes_tracks_deleted_files(git_repo: Path) -> None:
    tracked_file = git_repo / "src" / "app.ts"
    save_hashes(git_repo, {"src/app.ts": get_file_hash(tracked_file)})
    tracked_file.unlink()

    result = detect_repository_changes(git_repo)
    cached_hashes = load_cached_hashes(git_repo)

    assert result.deleted_files == ["src/app.ts"]
    assert "src/app.ts" not in cached_hashes


def test_detect_repository_changes_raises_when_no_changes(git_repo: Path) -> None:
    with pytest.raises(NoChangesError):
        detect_repository_changes(git_repo)


def test_detect_repository_changes_raises_for_non_git_repo(tmp_path: Path) -> None:
    with pytest.raises(NotAGitRepositoryError):
        detect_repository_changes(tmp_path)


def test_get_changed_files_raises_when_git_is_missing(tmp_path: Path) -> None:
    mock_result = RunResult(
        command="git rev-parse --is-inside-work-tree",
        returncode=1,
        stdout="",
        stderr="'git' is not recognized as an internal or external command",
    )

    with patch(
        "aica.repo_intelligence.sync.change_detector.TerminalRunner.run",
        return_value=mock_result,
    ):
        with pytest.raises(GitNotFoundError):
            get_changed_files(tmp_path)
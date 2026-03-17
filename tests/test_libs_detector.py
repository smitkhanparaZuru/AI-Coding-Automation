from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.libs import LibsDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def libs_repo(tmp_path: Path) -> Path:
    """Repo with src/libs/ containing trpc and next-auth lib directories."""
    libs_dir = tmp_path / "src" / "libs"

    # trpc lib
    trpc_dir = libs_dir / "trpc"
    trpc_dir.mkdir(parents=True)
    for fname in ("client.ts", "server.ts", "middleware.ts"):
        (trpc_dir / fname).write_text("export const x = 1;\n", encoding="utf-8")
    # subdirectory (should not list its files in main_files)
    (trpc_dir / "helpers").mkdir()
    (trpc_dir / "helpers" / "index.ts").write_text("", encoding="utf-8")

    # next-auth lib
    na_dir = libs_dir / "next-auth"
    na_dir.mkdir(parents=True)
    (na_dir / "auth.ts").write_text("export const auth = {};\n", encoding="utf-8")

    # _internal dir (should be skipped)
    skip_dir = libs_dir / ".hidden"
    skip_dir.mkdir()
    (skip_dir / "index.ts").write_text("", encoding="utf-8")

    return tmp_path


@pytest.fixture()
def empty_libs_repo(tmp_path: Path) -> Path:
    """Repo without a libs directory."""
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detects_both_libs(libs_repo: Path) -> None:
    results = LibsDetector().detect(libs_repo)
    names = {r["lib"] for r in results}
    assert "trpc" in names
    assert "next-auth" in names


def test_lib_path_is_relative(libs_repo: Path) -> None:
    results = LibsDetector().detect(libs_repo)
    trpc = next(r for r in results if r["lib"] == "trpc")
    assert trpc["path"] == "src/libs/trpc"


def test_main_files_listed(libs_repo: Path) -> None:
    results = LibsDetector().detect(libs_repo)
    trpc = next(r for r in results if r["lib"] == "trpc")
    assert set(trpc["main_files"]) == {"client.ts", "server.ts", "middleware.ts"}


def test_subdir_files_not_in_main_files(libs_repo: Path) -> None:
    """Files inside subdirectories of a lib should not appear in main_files."""
    results = LibsDetector().detect(libs_repo)
    trpc = next(r for r in results if r["lib"] == "trpc")
    assert "index.ts" not in trpc["main_files"]


def test_hidden_dirs_skipped(libs_repo: Path) -> None:
    results = LibsDetector().detect(libs_repo)
    names = {r["lib"] for r in results}
    assert ".hidden" not in names


def test_no_libs_dir_returns_empty(empty_libs_repo: Path) -> None:
    results = LibsDetector().detect(empty_libs_repo)
    assert results == []


def test_next_auth_files(libs_repo: Path) -> None:
    results = LibsDetector().detect(libs_repo)
    na = next(r for r in results if r["lib"] == "next-auth")
    assert "auth.ts" in na["main_files"]


def test_fallback_to_src_lib(tmp_path: Path) -> None:
    """Detector should also find libs under src/lib/ when src/libs/ doesn't exist."""
    lib_dir = tmp_path / "src" / "lib" / "trpc"
    lib_dir.mkdir(parents=True)
    (lib_dir / "client.ts").write_text("export const x = 1;\n", encoding="utf-8")

    results = LibsDetector().detect(tmp_path)
    names = {r["lib"] for r in results}
    assert "trpc" in names

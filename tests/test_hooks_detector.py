from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.hooks import HooksDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def hooks_repo(tmp_path: Path) -> Path:
    """Repo with a src/hooks/ directory containing several custom hooks."""
    hooks_dir = tmp_path / "src" / "hooks"
    hooks_dir.mkdir(parents=True)

    (hooks_dir / "useIsMobile.ts").write_text(
        "import { useState } from 'react';\n"
        "export function useIsMobile(breakpoint: number) {\n"
        "  return useState(false);\n"
        "}\n",
        encoding="utf-8",
    )

    (hooks_dir / "useTheme.ts").write_text(
        "export const useTheme = (defaultTheme: string, fallback: string) => {\n"
        "  return defaultTheme;\n"
        "};\n",
        encoding="utf-8",
    )

    # Not a hook (doesn't start with use + uppercase)
    (hooks_dir / "helpers.ts").write_text(
        "export function getColor() {}\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def empty_hooks_repo(tmp_path: Path) -> Path:
    """Repo without a hooks directory."""
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detects_function_hook(hooks_repo: Path) -> None:
    results = HooksDetector().detect(hooks_repo)
    names = {r["name"] for r in results}
    assert "useIsMobile" in names


def test_detects_const_hook(hooks_repo: Path) -> None:
    results = HooksDetector().detect(hooks_repo)
    names = {r["name"] for r in results}
    assert "useTheme" in names


def test_non_hook_functions_ignored(hooks_repo: Path) -> None:
    results = HooksDetector().detect(hooks_repo)
    names = {r["name"] for r in results}
    assert "getColor" not in names


def test_hook_file_path_is_relative(hooks_repo: Path) -> None:
    results = HooksDetector().detect(hooks_repo)
    mobile = next(r for r in results if r["name"] == "useIsMobile")
    assert mobile["file"] == "src/hooks/useIsMobile.ts"


def test_function_hook_parameters_extracted(hooks_repo: Path) -> None:
    results = HooksDetector().detect(hooks_repo)
    mobile = next(r for r in results if r["name"] == "useIsMobile")
    assert "breakpoint" in mobile["parameters"]


def test_const_hook_parameters_extracted(hooks_repo: Path) -> None:
    results = HooksDetector().detect(hooks_repo)
    theme = next(r for r in results if r["name"] == "useTheme")
    assert "defaultTheme" in theme["parameters"]
    assert "fallback" in theme["parameters"]


def test_no_hooks_dir_returns_empty(empty_hooks_repo: Path) -> None:
    results = HooksDetector().detect(empty_hooks_repo)
    assert results == []


def test_deduplication(tmp_path: Path) -> None:
    """Same hook name exported twice from different files should not duplicate."""
    hooks_dir = tmp_path / "src" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "a.ts").write_text("export function useData() {}\n", encoding="utf-8")
    (hooks_dir / "b.ts").write_text("export function useData() {}\n", encoding="utf-8")

    results = HooksDetector().detect(tmp_path)
    names = [r["name"] for r in results]
    assert names.count("useData") == 1

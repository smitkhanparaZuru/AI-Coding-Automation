from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.stores import ZustandStoreDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def store_repo_slices_dir(tmp_path: Path) -> Path:
    """Repo with a Zustand store using the explicit slices/ subdirectory pattern."""
    store_dir = tmp_path / "src" / "store" / "user"
    slices_dir = store_dir / "slices"
    slices_dir.mkdir(parents=True)

    # Slice subdirectories inside slices/
    for slice_name in ("auth", "credits", "modelList", "preference"):
        sd = slices_dir / slice_name
        sd.mkdir()
        (sd / "action.ts").write_text(
            "export const setUser = () => {};\n", encoding="utf-8"
        )
        (sd / "initialState.ts").write_text(
            "export const initialState = {};\n", encoding="utf-8"
        )
        (sd / "selectors.ts").write_text(
            "export const selectUser = (s: any) => s;\n", encoding="utf-8"
        )

    # Store index file with middleware
    (store_dir / "index.ts").write_text(
        "import { create } from 'zustand';\n"
        "import { devtools, subscribeWithSelector } from 'zustand/middleware';\n"
        "const useUserStore = create(devtools(subscribeWithSelector(() => ({}))));\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def store_repo_subdir_pattern(tmp_path: Path) -> Path:
    """Repo with a Zustand store using subdirectory-per-slice (no slices/ folder)."""
    agent_dir = tmp_path / "src" / "store" / "agent"
    agent_dir.mkdir(parents=True)

    # Sub-slices detected via action/initialState marker files
    for slice_name in ("config", "runtime"):
        sd = agent_dir / slice_name
        sd.mkdir()
        (sd / "action.ts").write_text("export {};\n", encoding="utf-8")
        (sd / "initialState.ts").write_text("export {};\n", encoding="utf-8")

    (agent_dir / "index.ts").write_text(
        "import { create } from 'zustand';\nimport { persist } from 'zustand/middleware';\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def empty_store_repo(tmp_path: Path) -> Path:
    """Repo without any store/ directory."""
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detect_slices_dir_pattern(store_repo_slices_dir: Path) -> None:
    results = ZustandStoreDetector().detect(store_repo_slices_dir)
    assert len(results) == 1
    store = results[0]
    assert store["store"] == "user"
    assert set(store["slices"]) == {"auth", "credits", "modelList", "preference"}


def test_detect_middleware(store_repo_slices_dir: Path) -> None:
    results = ZustandStoreDetector().detect(store_repo_slices_dir)
    assert len(results) == 1
    middleware = set(results[0]["middleware"])
    assert "devtools" in middleware
    assert "subscribeWithSelector" in middleware


def test_detect_subdir_slices(store_repo_subdir_pattern: Path) -> None:
    results = ZustandStoreDetector().detect(store_repo_subdir_pattern)
    assert len(results) == 1
    store = results[0]
    assert store["store"] == "agent"
    assert set(store["slices"]) == {"config", "runtime"}


def test_detect_persist_middleware(store_repo_subdir_pattern: Path) -> None:
    results = ZustandStoreDetector().detect(store_repo_subdir_pattern)
    assert "persist" in results[0]["middleware"]


def test_no_store_dir_returns_empty(empty_store_repo: Path) -> None:
    results = ZustandStoreDetector().detect(empty_store_repo)
    assert results == []


def test_path_is_relative_to_repo(store_repo_slices_dir: Path) -> None:
    results = ZustandStoreDetector().detect(store_repo_slices_dir)
    assert results[0]["path"] == "src/store/user"


def test_multiple_store_modules(tmp_path: Path) -> None:
    """Multiple store modules are all detected."""
    for module in ("chat", "global", "session"):
        store_dir = tmp_path / "src" / "store" / module
        store_dir.mkdir(parents=True)
        (store_dir / "index.ts").write_text(
            "import { create } from 'zustand';\n", encoding="utf-8"
        )

    results = ZustandStoreDetector().detect(tmp_path)
    names = {r["store"] for r in results}
    assert names == {"chat", "global", "session"}

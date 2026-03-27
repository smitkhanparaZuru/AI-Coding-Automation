from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from aica.memory.graph_store.incremental_builder import GraphUpdateSummary
from aica.repo_intelligence.sync.orchestrator import (
    ChangeDetectionResult,
    sync_repository,
)


def _make_change_result(repo_path: Path, changed: list[str], deleted: list[str]) -> ChangeDetectionResult:
    return ChangeDetectionResult(
        changed_files=changed,
        real_changed_files=changed,
        deleted_files=deleted,
        base_ref="HEAD",
        cache_path=repo_path / ".repo_intelligence" / ".cache" / "file_hashes.json",
        duration_seconds=0.01,
    )


def test_sync_repository_uses_incremental_mode_below_threshold(
    monkeypatch,
    tmp_path: Path,
) -> None:
    change_result = _make_change_result(tmp_path, ["src/app.ts"], [])

    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator.detect_repository_changes",
        lambda repo_path, base_ref="HEAD": change_result,
    )
    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator._count_ts_tsx_files",
        lambda _: 100,
    )

    incremental_mock = MagicMock(
        return_value=(
            {"functions": 1, "imports": 1, "components": 0, "calls": 1},
            GraphUpdateSummary(
                nodes_deleted=0,
                nodes_created=3,
                edges_created=2,
                files_affected=["src/app.ts"],
                duration_seconds=0.1,
            ),
        )
    )
    full_mock = MagicMock()

    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator._run_incremental_pipeline",
        incremental_mock,
    )
    monkeypatch.setattr("aica.repo_intelligence.sync.orchestrator._run_full_pipeline", full_mock)

    result = sync_repository(tmp_path)

    assert result.mode == "incremental"
    incremental_mock.assert_called_once()
    full_mock.assert_not_called()


def test_sync_repository_falls_back_to_full_mode_above_threshold(
    monkeypatch,
    tmp_path: Path,
) -> None:
    change_result = _make_change_result(tmp_path, [f"src/f{i}.ts" for i in range(25)], [])

    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator.detect_repository_changes",
        lambda repo_path, base_ref="HEAD": change_result,
    )
    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator._count_ts_tsx_files",
        lambda _: 100,
    )

    full_mock = MagicMock(
        return_value=(
            {"functions": 10, "imports": 5, "components": 2, "calls": 7},
            GraphUpdateSummary(
                nodes_deleted=0,
                nodes_created=20,
                edges_created=15,
                files_affected=change_result.real_changed_files,
                duration_seconds=0.2,
            ),
        )
    )
    incremental_mock = MagicMock()

    monkeypatch.setattr("aica.repo_intelligence.sync.orchestrator._run_full_pipeline", full_mock)
    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator._run_incremental_pipeline",
        incremental_mock,
    )

    result = sync_repository(tmp_path)

    assert result.mode == "full"
    full_mock.assert_called_once()
    incremental_mock.assert_not_called()


def test_sync_repository_force_full_overrides_threshold(monkeypatch, tmp_path: Path) -> None:
    change_result = _make_change_result(tmp_path, ["src/app.ts"], [])

    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator.detect_repository_changes",
        lambda repo_path, base_ref="HEAD": change_result,
    )
    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator._count_ts_tsx_files",
        lambda _: 100,
    )

    full_mock = MagicMock(
        return_value=(
            {"functions": 3, "imports": 2, "components": 1, "calls": 4},
            GraphUpdateSummary(
                nodes_deleted=0,
                nodes_created=12,
                edges_created=8,
                files_affected=change_result.real_changed_files,
                duration_seconds=0.15,
            ),
        )
    )
    incremental_mock = MagicMock()

    monkeypatch.setattr("aica.repo_intelligence.sync.orchestrator._run_full_pipeline", full_mock)
    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator._run_incremental_pipeline",
        incremental_mock,
    )

    result = sync_repository(tmp_path, force_full=True)

    assert result.mode == "full"
    full_mock.assert_called_once()
    incremental_mock.assert_not_called()


def test_sync_repository_uses_custom_threshold(monkeypatch, tmp_path: Path) -> None:
    change_result = _make_change_result(tmp_path, [f"src/f{i}.ts" for i in range(15)], [])

    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator.detect_repository_changes",
        lambda repo_path, base_ref="HEAD": change_result,
    )
    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator._count_ts_tsx_files",
        lambda _: 100,
    )

    full_mock = MagicMock(
        return_value=(
            {"functions": 5, "imports": 4, "components": 1, "calls": 3},
            GraphUpdateSummary(
                nodes_deleted=0,
                nodes_created=12,
                edges_created=6,
                files_affected=change_result.real_changed_files,
                duration_seconds=0.12,
            ),
        )
    )
    incremental_mock = MagicMock()

    monkeypatch.setattr("aica.repo_intelligence.sync.orchestrator._run_full_pipeline", full_mock)
    monkeypatch.setattr(
        "aica.repo_intelligence.sync.orchestrator._run_incremental_pipeline",
        incremental_mock,
    )

    result = sync_repository(tmp_path, fallback_threshold=0.10)

    assert result.mode == "full"
    full_mock.assert_called_once()
    incremental_mock.assert_not_called()

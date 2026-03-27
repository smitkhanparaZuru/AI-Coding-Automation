from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Literal

from aica.config import get_settings
from aica.core.logging import get_logger
from aica.memory.graph_store.incremental_builder import GraphUpdateSummary, update_graph_for_files
from aica.memory.graph_store.graph_builder import build_dependency_graph
from aica.repo_intelligence.ast.extractors import build_call_graph
from aica.repo_intelligence.ast.runner import ASTExtractorRunner
from aica.repo_intelligence.ast.writer import ASTWriter
from aica.repo_intelligence.scanner import scan_repository
from aica.repo_intelligence.scanner.incremental import run_incremental_scan
from aica.repo_intelligence.scanner.summarizer import RepoSummaryGenerator
from aica.repo_intelligence.scanner.writers import OutputWriter
from aica.repo_intelligence.sync.change_detector import (
    collect_git_changes,
    detect_real_changes,
    get_cache_path,
    get_file_hash,
    load_cached_hashes,
    save_hashes,
)
from aica.repo_intelligence.sync.exceptions import NoChangesError, SyncError

log = get_logger("repo.sync.orchestrator")

_TS_EXTENSIONS = frozenset({".ts", ".tsx"})
_EXCLUDE_DIRS = frozenset({
    "node_modules",
    ".next",
    "dist",
    "build",
    "out",
    ".git",
    ".aica",
    ".repo_intelligence",
})


@dataclass(frozen=True)
class ChangeDetectionResult:
    """Structured result for Phase 1 repository change detection."""

    changed_files: list[str]
    real_changed_files: list[str]
    deleted_files: list[str]
    base_ref: str
    cache_path: Path
    duration_seconds: float


@dataclass(frozen=True)
class SyncResult:
    """Result of repository sync operation."""

    changed_files: list[str]
    deleted_files: list[str]
    mode: Literal["incremental", "full"]
    base_ref: str
    ast_summary: dict[str, int]
    graph_summary: GraphUpdateSummary
    duration_seconds: float


def detect_repository_changes(repo_path: Path, base_ref: str = "HEAD") -> ChangeDetectionResult:
    """Detect changed TypeScript files and update the local hash cache."""
    started_at = perf_counter()
    cached_hashes = load_cached_hashes(repo_path)
    git_changes = collect_git_changes(repo_path, base_ref=base_ref)

    missing_from_disk = sorted(
        relative_path
        for relative_path in cached_hashes
        if relative_path not in git_changes.changed_files
        and not (repo_path / relative_path).exists()
    )
    deleted_files = sorted(set(git_changes.deleted_files) | set(missing_from_disk))
    real_changed_files = detect_real_changes(
        git_changes.changed_files,
        cached_hashes,
        repo_path=repo_path,
    )

    if not real_changed_files and not deleted_files:
        raise NoChangesError("No relevant TypeScript changes detected")

    updated_hashes = dict(cached_hashes)
    for deleted_file in deleted_files:
        updated_hashes.pop(deleted_file, None)

    for changed_file in real_changed_files:
        updated_hashes[changed_file] = get_file_hash(repo_path / changed_file)

    save_hashes(repo_path, updated_hashes)

    duration_seconds = perf_counter() - started_at
    result = ChangeDetectionResult(
        changed_files=git_changes.changed_files,
        real_changed_files=real_changed_files,
        deleted_files=deleted_files,
        base_ref=base_ref,
        cache_path=get_cache_path(repo_path),
        duration_seconds=duration_seconds,
    )

    log.info(
        "repo.sync.detect.done",
        path=str(repo_path),
        changed=len(result.changed_files),
        real_changed=len(result.real_changed_files),
        deleted=len(result.deleted_files),
        duration_seconds=round(result.duration_seconds, 3),
    )
    return result


def _count_ts_tsx_files(repo_path: Path) -> int:
    """Count TypeScript files used for sync fallback percentage decisions."""
    total = 0
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in _TS_EXTENSIONS:
            continue
        try:
            relative = file_path.relative_to(repo_path)
        except ValueError:
            continue
        if any(part in _EXCLUDE_DIRS for part in relative.parts):
            continue
        total += 1
    return total


def _ast_summary_from_result(ast_result: dict) -> dict[str, int]:
    """Build a compact AST update summary for CLI rendering."""
    return {
        "imports": len(ast_result.get("imports", [])),
        "functions": len(ast_result.get("functions", [])),
        "exports": len(ast_result.get("exports", [])),
        "calls": len(ast_result.get("calls", [])),
        "hooks": len(ast_result.get("hooks", [])),
        "components": len(ast_result.get("components", [])),
        "types": len(ast_result.get("types", [])),
    }


def _write_scan_outputs(repo_path: Path, scan_data: dict) -> None:
    """Persist scanner artifacts for full sync mode."""
    writer = OutputWriter()
    writer.write(scan_data.get("routes", []), repo_path, "routes.json")
    writer.write(scan_data.get("components", []), repo_path, "components.json")
    writer.write(scan_data.get("services", []), repo_path, "services.json")
    writer.write(scan_data.get("database", []), repo_path, "database.json")
    writer.write(scan_data.get("packages", {}), repo_path, "packages.json")
    writer.write(scan_data.get("stores", []), repo_path, "stores.json")
    writer.write(scan_data.get("trpc_routers", []), repo_path, "trpc_routers.json")
    writer.write(scan_data.get("i18n", {}), repo_path, "i18n.json")
    writer.write(scan_data.get("auth", {}), repo_path, "auth.json")
    writer.write(scan_data.get("server_modules", []), repo_path, "server_modules.json")
    writer.write(scan_data.get("agent_runtime", {}), repo_path, "agent_runtime.json")
    writer.write(scan_data.get("env_vars", {}), repo_path, "env_vars.json")
    writer.write(scan_data.get("hooks", []), repo_path, "hooks.json")
    writer.write(scan_data.get("scripts", []), repo_path, "scripts.json")
    writer.write(scan_data.get("libs", []), repo_path, "libs.json")
    writer.write(scan_data, repo_path, "structure.json")

    summary = RepoSummaryGenerator.from_scan_data(scan_data)
    writer.write(summary, repo_path, "repo_summary.json")


def _write_ast_outputs(repo_path: Path, ast_result: dict) -> None:
    """Persist AST artifacts for incremental or full sync mode."""
    writer = ASTWriter()
    writer.write(ast_result.get("imports", []), repo_path, "imports.json", mode="merge")
    writer.write(ast_result.get("functions", []), repo_path, "functions.json", mode="merge")
    writer.write(ast_result.get("exports", []), repo_path, "exports.json", mode="merge")
    writer.write(build_call_graph(ast_result.get("calls", [])), repo_path, "call_graph.json", mode="merge")
    writer.write(ast_result.get("hooks", []), repo_path, "hooks.json", mode="merge")
    writer.write(ast_result.get("components", []), repo_path, "components.json", mode="merge")
    writer.write(ast_result.get("types", []), repo_path, "types.json", mode="merge")


def _run_incremental_pipeline(
    repo_path: Path,
    changed_files: list[str],
    deleted_files: list[str],
) -> tuple[dict[str, int], GraphUpdateSummary]:
    """Run incremental AST + graph updates for changed and deleted files."""
    affected_files = sorted(set(changed_files) | set(deleted_files))

    try:
        run_incremental_scan(repo_path, affected_files)
    except ValueError as exc:
        raise SyncError(str(exc)) from exc

    ast_result = ASTExtractorRunner().run_incremental(repo_path, affected_files)
    _write_ast_outputs(repo_path, ast_result)

    graph_summary = update_graph_for_files(
        repo_path,
        affected_files,
        deleted_files=deleted_files,
    )

    return _ast_summary_from_result(ast_result), graph_summary


def _run_full_pipeline(
    repo_path: Path,
    changed_files: list[str],
) -> tuple[dict[str, int], GraphUpdateSummary]:
    """Run full scanner + AST + graph rebuild and normalize summaries."""
    scan_data = scan_repository(str(repo_path))
    if "error" in scan_data:
        error = str(scan_data["error"])
        raise SyncError(error)

    _write_scan_outputs(repo_path, scan_data)

    ast_result = ASTExtractorRunner().run(repo_path)
    _write_ast_outputs(repo_path, ast_result)
    ast_summary = _ast_summary_from_result(ast_result)

    full_graph_summary = build_dependency_graph(repo_path)
    nodes_created = (
        full_graph_summary.files
        + full_graph_summary.functions
        + full_graph_summary.components
        + full_graph_summary.types
        + full_graph_summary.hooks
        + full_graph_summary.routes
        + full_graph_summary.services
        + full_graph_summary.stores
    )
    edges_created = (
        full_graph_summary.import_edges
        + full_graph_summary.call_edges
        + full_graph_summary.hook_edges
    )
    graph_summary = GraphUpdateSummary(
        nodes_deleted=0,
        nodes_created=nodes_created,
        edges_created=edges_created,
        files_affected=changed_files,
        duration_seconds=0.0,
    )
    return ast_summary, graph_summary


def sync_repository(
    repo_path: Path,
    base_ref: str = "HEAD",
    force_full: bool = False,
    fallback_threshold: float | None = None,
) -> SyncResult:
    """Intelligent repository sync with automatic fallback to full rebuild."""
    started_at = perf_counter()
    change_result = detect_repository_changes(repo_path, base_ref=base_ref)

    settings = get_settings()
    configured_threshold = settings.sync_fallback_threshold
    threshold = configured_threshold if fallback_threshold is None else fallback_threshold
    if threshold < 0 or threshold > 1:
        raise SyncError("Fallback threshold must be between 0.0 and 1.0")

    total_files = _count_ts_tsx_files(repo_path)
    changed_total = len(set(change_result.real_changed_files) | set(change_result.deleted_files))
    change_percentage = (changed_total / total_files) if total_files > 0 else 1.0

    run_full = force_full or change_percentage > threshold
    mode: Literal["incremental", "full"] = "full" if run_full else "incremental"

    if run_full:
        ast_summary, graph_summary = _run_full_pipeline(
            repo_path,
            changed_files=change_result.real_changed_files,
        )
    else:
        ast_summary, graph_summary = _run_incremental_pipeline(
            repo_path,
            changed_files=change_result.real_changed_files,
            deleted_files=change_result.deleted_files,
        )

    duration_seconds = perf_counter() - started_at
    result = SyncResult(
        changed_files=change_result.real_changed_files,
        deleted_files=change_result.deleted_files,
        mode=mode,
        base_ref=base_ref,
        ast_summary=ast_summary,
        graph_summary=GraphUpdateSummary(
            nodes_deleted=graph_summary.nodes_deleted,
            nodes_created=graph_summary.nodes_created,
            edges_created=graph_summary.edges_created,
            files_affected=graph_summary.files_affected,
            duration_seconds=duration_seconds,
        ),
        duration_seconds=duration_seconds,
    )

    log.info(
        "repo.sync.orchestrated",
        path=str(repo_path),
        mode=mode,
        changed=len(result.changed_files),
        deleted=len(result.deleted_files),
        total_files=total_files,
        threshold=round(threshold, 4),
        change_percentage=round(change_percentage, 4),
        duration_seconds=round(duration_seconds, 3),
    )
    return result
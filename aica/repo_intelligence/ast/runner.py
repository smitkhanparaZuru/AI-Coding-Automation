"""
AST Extractor Runner — coordinates imports + functions extractors across a repo.

Walks all ``.ts`` and ``.tsx`` files under a repository root, runs both
extractors on each file, and returns the aggregated results.

Excluded directories (never descended into)::

    node_modules  .next  dist  build  out  .git  .aica  .repo_intelligence
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from aica.core.logging import get_logger
from aica.repo_intelligence.ast.extractors import (
    extract_calls,
    extract_components,
    extract_exports,
    extract_functions,
    extract_hooks,
    extract_imports,
    extract_types,
)
from aica.repo_intelligence.ast.parser import parse_file

log = get_logger("repo.ast.runner")

_EXCLUDE: frozenset[str] = frozenset({
    "node_modules",
    ".next",
    "dist",
    "build",
    "out",
    ".git",
    ".aica",
    ".repo_intelligence",
})


def _is_excluded(path: Path, repo_path: Path) -> bool:
    """Return True if any component of *path* relative to *repo_path* is in ``_EXCLUDE``."""
    try:
        rel = path.relative_to(repo_path)
    except ValueError:
        return False
    return any(part in _EXCLUDE for part in rel.parts)


def _load_existing_json(repo_path: Path) -> dict:
    """Load all 7 existing JSON files from .repo_intelligence/ast/.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        Dict with keys: imports, functions, exports, calls, hooks, components, types.
        If files don't exist, returns empty lists for all keys.
    """
    ast_dir = repo_path / ".repo_intelligence" / "ast"
    keys = ["imports", "functions", "exports", "calls", "hooks", "components", "types"]
    data: dict = {key: [] for key in keys}

    for key in keys:
        file_path = ast_dir / f"{key}.json"
        if file_path.exists():
            try:
                data[key] = json.loads(file_path.read_text(encoding="utf-8"))
                log.debug("ast.loader.loaded", file=f"{key}.json", count=len(data[key]))
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("ast.loader.load_error", file=f"{key}.json", error=str(exc))
                data[key] = []
        else:
            log.debug("ast.loader.file_not_found", file=f"{key}.json")

    return data


def _remove_file_entries(data: dict, file_path: str) -> dict:
    """Remove all entries for a specific file from all 7 lists.

    Args:
        data: Merged data dict with keys: imports, functions, exports, calls,
            hooks, components, types.
        file_path: Relative file path (e.g., 'src/components/Button.tsx').

    Returns:
        Cleaned data dict with entries for file_path removed from all lists.
    """
    keys = ["imports", "functions", "exports", "calls", "hooks", "components", "types"]

    for key in keys:
        if key in data:
            original_count = len(data[key])
            data[key] = [x for x in data[key] if x.get("file") != file_path]
            removed = original_count - len(data[key])
            if removed > 0:
                log.debug("ast.remover.removed_entries", file=file_path, key=key, count=removed)

    return data


def _rebuild_call_graph(data: dict) -> list[dict]:
    """Rebuild the call graph from partially updated data.

    Args:
        data: Merged data dict with all extracted information.

    Returns:
        Updated calls list. Currently returns unchanged (calls already have file references).
    """
    # For now, calls are already correct in data['calls'] since each call entry
    # has a file reference and the import/function data has been refreshed.
    calls = cast(list[dict], data.get("calls", []))
    log.debug("ast.graph_builder.rebuilt_calls", count=len(calls))
    return calls


class ASTExtractorRunner:
    """Run all AST extractors across all TypeScript/TSX files."""

    def run(self, repo_path: Path) -> dict:
        """Extract all code intelligence from all ``.ts``/``.tsx`` files under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            Dict with keys: ``imports``, ``functions``, ``exports``, ``calls``,
            ``hooks``, ``components``, ``types``.
        """
        if not repo_path.exists():
            log.error("ast.runner.repo_not_found", path=str(repo_path))
            return {
                "imports": [],
                "functions": [],
                "exports": [],
                "calls": [],
                "hooks": [],
                "components": [],
                "types": [],
            }

        log.info("ast.runner.start", path=str(repo_path))

        ts_files = sorted(
            p
            for p in (
                list(repo_path.rglob("*.ts")) + list(repo_path.rglob("*.tsx"))
            )
            if p.is_file() and not _is_excluded(p, repo_path)
        )

        all_imports: list[dict] = []
        all_functions: list[dict] = []
        all_exports: list[dict] = []
        all_calls: list[dict] = []
        all_hooks: list[dict] = []
        all_components: list[dict] = []
        all_types: list[dict] = []

        for file_path in ts_files:
            rel = file_path.relative_to(repo_path).as_posix()
            try:
                tree = parse_file(file_path)
                source = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                log.warning("ast.runner.read_error", file=rel, error=str(exc))
                continue

            file_imports = extract_imports(tree, source, rel)
            file_functions = extract_functions(tree, source, rel)
            file_exports = extract_exports(tree, source, rel)
            file_calls = extract_calls(tree, source, rel)
            file_hooks = extract_hooks(tree, source, rel)
            file_components = extract_components(tree, source, rel)
            file_types = extract_types(tree, source, rel)

            all_imports.extend(file_imports)
            all_functions.extend(file_functions)
            all_exports.extend(file_exports)
            all_calls.extend(file_calls)
            all_hooks.extend(file_hooks)
            all_components.extend(file_components)
            all_types.extend(file_types)

            log.debug(
                "ast.runner.file",
                path=rel,
                imports=len(file_imports),
                functions=len(file_functions),
                exports=len(file_exports),
                calls=len(file_calls),
                hooks=len(file_hooks),
                components=len(file_components),
                types=len(file_types),
            )

        log.info(
            "ast.runner.done",
            files=len(ts_files),
            imports=len(all_imports),
            functions=len(all_functions),
            exports=len(all_exports),
            calls=len(all_calls),
            hooks=len(all_hooks),
            components=len(all_components),
            types=len(all_types),
        )

        return {
            "imports": all_imports,
            "functions": all_functions,
            "exports": all_exports,
            "calls": all_calls,
            "hooks": all_hooks,
            "components": all_components,
            "types": all_types,
        }

    def run_incremental(self, repo_path: Path, changed_files: list[str]) -> dict:
        """Incrementally update AST extraction for changed files only.

        Loads existing JSON files from .repo_intelligence/ast/, removes old entries
        for changed files, extracts new entries, and rebuilds the call graph.

        Args:
            repo_path: Absolute path to the repository root.
            changed_files: List of relative file paths that have changed
                (e.g., ['src/utils.ts', 'src/hooks/useAuth.ts']).

        Returns:
            Dict with keys: ``imports``, ``functions``, ``exports``, ``calls``,
            ``hooks``, ``components``, ``types`` (merged with existing data).
        """
        if not repo_path.exists():
            log.error("ast.runner.repo_not_found", path=str(repo_path))
            return {
                "imports": [],
                "functions": [],
                "exports": [],
                "calls": [],
                "hooks": [],
                "components": [],
                "types": [],
            }

        log.info(
            "ast.runner.incremental_start",
            path=str(repo_path),
            changed_files_count=len(changed_files),
        )

        # Load existing data from JSON files
        data = _load_existing_json(repo_path)

        # Process each changed file
        for file_rel_path in changed_files:
            file_abs_path = repo_path / file_rel_path

            # If file was deleted, remove its entries
            if not file_abs_path.exists():
                log.debug("ast.runner.file_deleted", file=file_rel_path)
                data = _remove_file_entries(data, file_rel_path)
                continue

            # If file exists, reparse and update
            try:
                tree = parse_file(file_abs_path)
                source = file_abs_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                log.warning("ast.runner.read_error", file=file_rel_path, error=str(exc))
                data = _remove_file_entries(data, file_rel_path)
                continue

            # Remove old entries for this file
            data = _remove_file_entries(data, file_rel_path)

            # Extract new data from the file
            file_imports = extract_imports(tree, source, file_rel_path)
            file_functions = extract_functions(tree, source, file_rel_path)
            file_exports = extract_exports(tree, source, file_rel_path)
            file_calls = extract_calls(tree, source, file_rel_path)
            file_hooks = extract_hooks(tree, source, file_rel_path)
            file_components = extract_components(tree, source, file_rel_path)
            file_types = extract_types(tree, source, file_rel_path)

            # Merge new entries into data
            data["imports"].extend(file_imports)
            data["functions"].extend(file_functions)
            data["exports"].extend(file_exports)
            data["calls"].extend(file_calls)
            data["hooks"].extend(file_hooks)
            data["components"].extend(file_components)
            data["types"].extend(file_types)

            log.debug(
                "ast.runner.file_updated",
                file=file_rel_path,
                imports=len(file_imports),
                functions=len(file_functions),
                exports=len(file_exports),
                calls=len(file_calls),
                hooks=len(file_hooks),
                components=len(file_components),
                types=len(file_types),
            )

        # Rebuild call graph with updated imports
        data["calls"] = _rebuild_call_graph(data)

        log.info(
            "ast.runner.incremental_done",
            changed_files=len(changed_files),
            imports=len(data["imports"]),
            functions=len(data["functions"]),
            exports=len(data["exports"]),
            calls=len(data["calls"]),
            hooks=len(data["hooks"]),
            components=len(data["components"]),
            types=len(data["types"]),
        )

        return data

"""
AST Extractor Runner — coordinates imports + functions extractors across a repo.

Walks all ``.ts`` and ``.tsx`` files under a repository root, runs both
extractors on each file, and returns the aggregated results.

Excluded directories (never descended into)::

    node_modules  .next  dist  build  out  .git  .aica  .repo_intelligence
"""

from __future__ import annotations

from pathlib import Path

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
            return {"imports": [], "functions": [], "exports": [], "calls": [], "hooks": [], "components": [], "types": []}

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

from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.scripts")

# Files/dirs to skip inside scripts/
_SKIP_NAMES = frozenset({"node_modules", "__pycache__", ".cache"})

# Script root candidates
_SCRIPT_ROOTS = ("scripts", "script")


class ScriptsDetector:
    """Inventory the top-level ``scripts/`` directory.

    Each immediate child of the scripts directory becomes one entry.
    Sub-directories list their contained files; plain files are listed as-is.

    Output per entry::

        {
            "name": "migrateServerDB",
            "path": "scripts/migrateServerDB",
            "type": "dir",
            "files": ["index.ts", "docker.cjs", "errorHint.js"]
        }

    or, for a plain script file::

        {"name": "countEnWord", "path": "scripts/countEnWord.ts", "type": "file", "files": []}
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return an inventory of all entries in the scripts directory.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of script descriptor dicts.  Empty list when no scripts dir found.
        """
        log.info("scripts.start", path=str(repo_path))
        scripts_dir = self._locate_scripts_dir(repo_path)
        if scripts_dir is None:
            log.info("scripts.no_dir", path=str(repo_path))
            return []

        results: list[dict] = []
        for child in sorted(scripts_dir.iterdir()):
            if child.name.startswith(".") or child.name in _SKIP_NAMES:
                continue
            rel_path = child.relative_to(repo_path).as_posix()
            if child.is_dir():
                files = sorted(
                    f.name
                    for f in child.iterdir()
                    if f.is_file() and not f.name.startswith(".")
                )
                results.append({"name": child.name, "path": rel_path, "type": "dir", "files": files})
            else:
                results.append({"name": child.stem, "path": rel_path, "type": "file", "files": []})

        log.info("scripts.done", count=len(results))
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _locate_scripts_dir(self, repo_path: Path) -> Path | None:
        for candidate in _SCRIPT_ROOTS:
            d = repo_path / candidate
            if d.is_dir():
                return d
        return None

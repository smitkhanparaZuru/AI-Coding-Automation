from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.server_modules")

# Matches: export class Foo / export function bar / export const baz
_RE_EXPORT = re.compile(
    r"export\s+(?:default\s+)?(?:abstract\s+)?(?:class|function|const|async\s+function)\s+"
    r"([A-Za-z_$][\w$]*)"
)

# Candidates for the server modules root directory
_MODULE_ROOTS = (
    "src/server/modules",
    "server/modules",
)


class ServerModulesDetector:
    """Detect server-side module directories under ``src/server/modules/``.

    Each immediate subdirectory is treated as one server module.  The detector
    lists the ``.ts`` files inside it and extracts any exported symbols from
    the first 80 lines of each file.

    Output per module::

        {
            "module": "AgentRuntime",
            "path": "src/server/modules/AgentRuntime",
            "files": ["index.ts", "types.ts"],
            "exports": ["AgentRuntime", "createAgentRuntime"]
        }
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return one entry per server module found under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of module descriptor dicts.  Empty list when nothing detected.
        """
        log.info("server_modules.start", path=str(repo_path))
        modules_dir = self._locate_modules_dir(repo_path)
        if modules_dir is None:
            log.info("server_modules.no_dir", path=str(repo_path))
            return []

        results: list[dict] = []
        for subdir in sorted(modules_dir.iterdir()):
            if not subdir.is_dir() or subdir.name.startswith((".", "_")):
                continue
            entry = self._scan_module(subdir, repo_path)
            results.append(entry)

        log.info("server_modules.done", count=len(results))
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _locate_modules_dir(self, repo_path: Path) -> Path | None:
        for candidate in _MODULE_ROOTS:
            d = repo_path / candidate
            if d.is_dir():
                return d
        return None

    def _scan_module(self, module_dir: Path, repo_path: Path) -> dict:
        ts_files = sorted(
            f.name for f in module_dir.glob("*.ts") if not f.name.startswith("_")
        )
        # Also include sub-level index files (e.g. submodule/index.ts)
        exports: list[str] = []
        seen_exports: set[str] = set()
        for ts_file in module_dir.glob("**/*.ts"):
            if ts_file.name.startswith("_"):
                continue
            exports.extend(self._extract_exports(ts_file, seen_exports))

        rel_path = module_dir.relative_to(repo_path).as_posix()
        return {
            "module": module_dir.name,
            "path": rel_path,
            "files": ts_files,
            "exports": sorted(seen_exports),
        }

    @staticmethod
    def _extract_exports(file_path: Path, seen: set[str]) -> list[str]:
        """Return new exported symbol names from the first 80 lines of *file_path*."""
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()[:80]
            content = "\n".join(lines)
        except OSError:
            return []
        found: list[str] = []
        for m in _RE_EXPORT.finditer(content):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                found.append(name)
        return found

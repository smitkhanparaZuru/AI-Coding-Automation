from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.libs")

# Directories to skip when enumerating lib subdirectories
_SKIP_DIRS = frozenset({"node_modules", "__pycache__", ".cache", "dist", "build"})

# libs root candidates (src/-prefixed preferred)
_LIB_ROOTS = (
    "src/libs",
    "src/lib",
    "libs",
    "lib",
)

# Maximum number of top-level .ts/.tsx files to list per lib entry
_MAX_FILES = 10


class LibsDetector:
    """Inventory of third-party integration libraries under ``src/libs/``.

    Each immediate subdirectory of ``src/libs/`` becomes one library entry.
    Only the top-level ``.ts`` / ``.tsx`` files inside each lib dir are listed
    (not recursive), keeping the output concise.

    Output per lib::

        {
            "lib": "trpc",
            "path": "src/libs/trpc",
            "main_files": ["client.ts", "server.ts", "middleware.ts"]
        }
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return one entry per lib sub-directory under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of lib descriptor dicts.  Empty list when no libs dir found.
        """
        log.info("libs.start", path=str(repo_path))
        libs_dir = self._locate_libs_dir(repo_path)
        if libs_dir is None:
            log.info("libs.no_dir", path=str(repo_path))
            return []

        results: list[dict] = []
        for subdir in sorted(libs_dir.iterdir()):
            if not subdir.is_dir() or subdir.name in _SKIP_DIRS or subdir.name.startswith("."):
                continue
            main_files = sorted(
                f.name
                for f in subdir.iterdir()
                if f.is_file() and f.suffix in (".ts", ".tsx") and not f.name.startswith("_")
            )[:_MAX_FILES]
            rel_path = subdir.relative_to(repo_path).as_posix()
            results.append({
                "lib": subdir.name,
                "path": rel_path,
                "main_files": main_files,
            })

        log.info("libs.done", count=len(results))
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _locate_libs_dir(self, repo_path: Path) -> Path | None:
        for candidate in _LIB_ROOTS:
            d = repo_path / candidate
            if d.is_dir():
                return d
        return None

from __future__ import annotations

import json
from pathlib import Path

from aica.core.logging import get_logger
from aica.repo_intelligence.scanner.writers import OutputWriter

log = get_logger("repo.scanner.summarizer")

_OUTPUT_DIR = ".repo_intelligence"


class RepoSummaryGenerator:
    """Combine scanner artifact files into a single high-level repo summary.

    Two ways to build the summary:

    1. :meth:`generate` — reads individual ``.repo_intelligence/*.json`` files
       already written to disk by *scan-next* (or a prior run) and writes
       ``repo_summary.json`` back to the same directory.

    2. :meth:`from_scan_data` — classmethod that derives the summary dict
       directly from an already-scanned in-memory ``dict`` (no disk I/O
       except the final write).  Used by *scan-next* to avoid a disk
       round-trip.
    """

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(self, repo_path: Path) -> dict:
        """Read existing ``.repo_intelligence/*.json`` files and write summary.

        Args:
            repo_path: Repository root that already contains a
                       ``.repo_intelligence/`` directory.

        Returns:
            The summary dict (also written to
            ``{repo_path}/.repo_intelligence/repo_summary.json``).
        """
        log.info("summarizer.generate.start", path=str(repo_path))

        artifact_dir = repo_path / _OUTPUT_DIR

        routes = self._load_list(artifact_dir / "routes.json")
        components = self._load_list(artifact_dir / "components.json")
        services = self._load_list(artifact_dir / "services.json")
        database = self._load_list(artifact_dir / "database.json")
        structure = self._load_dict(artifact_dir / "structure.json")

        summary = self._build(
            framework=structure.get("framework", "unknown"),
            language=structure.get("language", "unknown"),
            routes=routes,
            components=components,
            services=services,
            database=database,
        )

        out_path = OutputWriter().write(summary, repo_path, "repo_summary.json")
        log.info("summarizer.generate.done", output=str(out_path))
        return summary

    @classmethod
    def from_scan_data(cls, scan_data: dict) -> dict:
        """Derive a summary dict from an in-memory scan result.

        Args:
            scan_data: The dict returned by :func:`scan_repository` /
                       :meth:`RepositoryScanner.scan`.

        Returns:
            The summary dict. Does **not** write to disk — the caller is
            responsible for persisting via :class:`OutputWriter`.
        """
        log.info("summarizer.from_scan_data.start")
        summary = cls._build(
            framework=scan_data.get("framework", "unknown"),
            language=scan_data.get("language", "unknown"),
            routes=scan_data.get("routes", []),
            components=scan_data.get("components", []),
            services=scan_data.get("services", []),
            database=scan_data.get("database", []),
        )
        log.info(
            "summarizer.from_scan_data.done",
            routes=summary["routes_count"],
            components=summary["components_count"],
            services=summary["services_count"],
            database=summary["database"],
        )
        return summary

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build(
        *,
        framework: str,
        language: str,
        routes: list,
        components: list,
        services: list,
        database: list,
    ) -> dict:
        orm: str | None = database[0]["orm"] if database else None
        return {
            "framework": framework,
            "language": language,
            "routes_count": len(routes),
            "components_count": len(components),
            "services_count": len(services),
            "database": orm,
        }

    @staticmethod
    def _load_list(path: Path) -> list:
        """Return parsed JSON list from *path*, or ``[]`` if missing/invalid."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("summarizer.load_list.failed", path=str(path), error=str(exc))
            return []

    @staticmethod
    def _load_dict(path: Path) -> dict:
        """Return parsed JSON dict from *path*, or ``{}`` if missing/invalid."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("summarizer.load_dict.failed", path=str(path), error=str(exc))
            return {}

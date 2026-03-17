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
        stores = self._load_list(artifact_dir / "stores.json")
        trpc_routers = self._load_list(artifact_dir / "trpc_routers.json")
        i18n = self._load_dict(artifact_dir / "i18n.json")
        auth = self._load_dict(artifact_dir / "auth.json")
        server_modules = self._load_list(artifact_dir / "server_modules.json")
        agent_runtime = self._load_dict(artifact_dir / "agent_runtime.json")
        env_vars = self._load_dict(artifact_dir / "env_vars.json")
        hooks = self._load_list(artifact_dir / "hooks.json")
        scripts = self._load_list(artifact_dir / "scripts.json")
        libs = self._load_list(artifact_dir / "libs.json")

        summary = self._build(
            framework=structure.get("framework", "unknown"),
            language=structure.get("language", "unknown"),
            routes=routes,
            components=components,
            services=services,
            database=database,
            stores=stores,
            trpc_routers=trpc_routers,
            i18n=i18n,
            auth=auth,
            server_modules=server_modules,
            agent_runtime=agent_runtime,
            env_vars=env_vars,
            hooks=hooks,
            scripts=scripts,
            libs=libs,
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
            stores=scan_data.get("stores", []),
            trpc_routers=scan_data.get("trpc_routers", []),
            i18n=scan_data.get("i18n", {}),
            auth=scan_data.get("auth", {}),
            server_modules=scan_data.get("server_modules", []),
            agent_runtime=scan_data.get("agent_runtime", {}),
            env_vars=scan_data.get("env_vars", {}),
            hooks=scan_data.get("hooks", []),
            scripts=scan_data.get("scripts", []),
            libs=scan_data.get("libs", []),
        )
        log.info(
            "summarizer.from_scan_data.done",
            routes=summary["routes_count"],
            components=summary["components_count"],
            services=summary["services_count"],
            database=summary["database"],
            stores=summary["stores_count"],
            trpc_routers=summary["trpc_routers_count"],
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
        stores: list | None = None,
        trpc_routers: list | None = None,
        i18n: dict | None = None,
        auth: dict | None = None,
        server_modules: list | None = None,
        agent_runtime: dict | None = None,
        env_vars: dict | None = None,
        hooks: list | None = None,
        scripts: list | None = None,
        libs: list | None = None,
    ) -> dict:
        orm: str | None = database[0]["orm"] if database else None
        i18n = i18n or {}
        auth = auth or {}
        agent_runtime = agent_runtime or {}
        env_vars = env_vars or {}
        trpc_procedures = sum(len(r.get("procedures", [])) for r in (trpc_routers or []))
        db_models_count = len((database[0] if database else {}).get("db_models", []))
        return {
            "framework": framework,
            "language": language,
            "routes_count": len(routes),
            "components_count": len(components),
            "services_count": len(services),
            "database": orm,
            "stores_count": len(stores or []),
            "trpc_routers_count": len(trpc_routers or []),
            "trpc_procedures_count": trpc_procedures,
            "i18n_source_lang": i18n.get("source_lang"),
            "i18n_namespace_count": i18n.get("namespace_count", 0),
            "auth_providers": auth.get("providers", []),
            "server_modules_count": len(server_modules or []),
            "ai_providers_count": len(agent_runtime.get("llm_providers", [])),
            "sso_providers_count": len(agent_runtime.get("sso_providers", [])),
            "hooks_count": len(hooks or []),
            "scripts_count": len(scripts or []),
            "env_vars_total": env_vars.get("total", 0),
            "libs_count": len(libs or []),
            "db_models_count": db_models_count,
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

from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger
from aica.repo_intelligence.scanner.detectors.components import ComponentDetector
from aica.repo_intelligence.scanner.detectors.database import DatabaseDetector
from aica.repo_intelligence.scanner.detectors.framework import FrameworkDetector
from aica.repo_intelligence.scanner.detectors.packages import PackageDetector
from aica.repo_intelligence.scanner.detectors.routes import RouteDetector
from aica.repo_intelligence.scanner.detectors.services import ServiceDetector
from aica.repo_intelligence.scanner.detectors.structure import StructureDetector

log = get_logger("repo.scanner.core")


class RepositoryScanner:
    """Orchestrate all detectors and produce a merged repository metadata dict."""

    def __init__(self) -> None:
        self._framework = FrameworkDetector()
        self._structure = StructureDetector()
        self._routes = RouteDetector()
        self._components = ComponentDetector()
        self._services = ServiceDetector()
        self._database = DatabaseDetector()
        self._packages = PackageDetector()

    def scan(self, repo_path: Path) -> dict:
        """Scan *repo_path* and return merged metadata.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            Merged dict containing framework info and source structure suitable
            for serialisation to ``.repo_intelligence/structure.json``.
        """
        if not repo_path.exists():
            log.error("scanner.repo_not_found", path=str(repo_path))
            return {"error": f"Repository path does not exist: {repo_path}"}

        log.info("scanner.start", path=str(repo_path))

        framework_meta = self._framework.detect(repo_path)
        structure_meta = self._structure.detect(repo_path)
        routes_list = self._routes.detect(repo_path)
        components_list = self._components.detect(repo_path)
        services_list = self._services.detect(repo_path)
        database_list = self._database.detect(repo_path)
        packages_meta = self._packages.detect(repo_path)

        result: dict = {
            **framework_meta,
            **structure_meta,
            "routes": routes_list,
            "components": components_list,
            "services": services_list,
            "database": database_list,
            "packages": packages_meta,
            "repo_path": str(repo_path),
        }

        log.info(
            "scanner.done",
            framework=framework_meta.get("framework"),
            language=framework_meta.get("language"),
            app_router=framework_meta.get("app_router"),
            src_dirs=len(structure_meta.get("src_structure", {})),
            routes=len(routes_list),
            components=len(components_list),
            services=len(services_list),
            database=len(database_list),
            pkg_framework=packages_meta.get("framework"),
        )
        return result


def scan_repository(repo_path: str) -> dict:
    """Top-level convenience function — scan *repo_path* and return metadata.

    Args:
        repo_path: Path to the repository root (string).

    Returns:
        Merged metadata dict from all detectors.
    """
    return RepositoryScanner().scan(Path(repo_path))

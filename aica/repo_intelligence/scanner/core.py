from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger
from aica.repo_intelligence.scanner.detectors.agent_runtime import AgentRuntimeDetector
from aica.repo_intelligence.scanner.detectors.auth import AuthDetector
from aica.repo_intelligence.scanner.detectors.components import ComponentDetector
from aica.repo_intelligence.scanner.detectors.database import DatabaseDetector
from aica.repo_intelligence.scanner.detectors.env_vars import EnvVarsDetector
from aica.repo_intelligence.scanner.detectors.framework import FrameworkDetector
from aica.repo_intelligence.scanner.detectors.hooks import HooksDetector
from aica.repo_intelligence.scanner.detectors.i18n import I18nDetector
from aica.repo_intelligence.scanner.detectors.libs import LibsDetector
from aica.repo_intelligence.scanner.detectors.packages import PackageDetector
from aica.repo_intelligence.scanner.detectors.routes import RouteDetector
from aica.repo_intelligence.scanner.detectors.scripts import ScriptsDetector
from aica.repo_intelligence.scanner.detectors.server_modules import ServerModulesDetector
from aica.repo_intelligence.scanner.detectors.services import ServiceDetector
from aica.repo_intelligence.scanner.detectors.stores import ZustandStoreDetector
from aica.repo_intelligence.scanner.detectors.structure import StructureDetector
from aica.repo_intelligence.scanner.detectors.trpc import TRPCRouterDetector

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
        self._stores = ZustandStoreDetector()
        self._trpc = TRPCRouterDetector()
        self._i18n = I18nDetector()
        self._auth = AuthDetector()
        self._server_modules = ServerModulesDetector()
        self._agent_runtime = AgentRuntimeDetector()
        self._env_vars = EnvVarsDetector()
        self._hooks = HooksDetector()
        self._scripts = ScriptsDetector()
        self._libs = LibsDetector()

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
        stores_list = self._stores.detect(repo_path)
        trpc_list = self._trpc.detect(repo_path)
        i18n_meta = self._i18n.detect(repo_path)
        auth_meta = self._auth.detect(repo_path)
        server_modules_list = self._server_modules.detect(repo_path)
        agent_runtime_meta = self._agent_runtime.detect(repo_path)
        env_vars_meta = self._env_vars.detect(repo_path)
        hooks_list = self._hooks.detect(repo_path)
        scripts_list = self._scripts.detect(repo_path)
        libs_list = self._libs.detect(repo_path)

        result: dict = {
            **framework_meta,
            **structure_meta,
            "routes": routes_list,
            "components": components_list,
            "services": services_list,
            "database": database_list,
            "packages": packages_meta,
            "stores": stores_list,
            "trpc_routers": trpc_list,
            "i18n": i18n_meta,
            "auth": auth_meta,
            "server_modules": server_modules_list,
            "agent_runtime": agent_runtime_meta,
            "env_vars": env_vars_meta,
            "hooks": hooks_list,
            "scripts": scripts_list,
            "libs": libs_list,
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
            stores=len(stores_list),
            trpc_routers=len(trpc_list),
            i18n_namespaces=i18n_meta.get("namespace_count", 0),
            auth_providers=len(auth_meta.get("providers", [])),
            pkg_framework=packages_meta.get("framework"),
            server_modules=len(server_modules_list),
            llm_providers=len(agent_runtime_meta.get("llm_providers", [])),
            hooks=len(hooks_list),
            scripts=len(scripts_list),
            libs=len(libs_list),
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
